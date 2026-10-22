"""Unit/component tests derived from the C05 Detailed Design of Confirm Reservation.

Each test names the DD decision it verifies (DD-x in ``docs/architecture-and-decisions.md``,
section "C05 Detailed Design"). Behaviour already covered by older tests is not repeated
here; the DD test table in the docs points to those tests instead.
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from ..models import Reservation, Resource
from ..services import ReservationError, cancel_reservation, confirm_reservation, create_draft, ensure_can_allocate
from ..services.lifecycle import allocate


class ConfirmationDesignTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.user = users.create_user(username="alice", password="password12345")
        self.other_user = users.create_user(username="bob", password="password12345")
        self.desk = Resource.objects.create(name="A01", resource_type=Resource.ResourceType.DESK)
        self.parking = Resource.objects.create(name="P01", resource_type=Resource.ResourceType.PARKING_SPOT)
        self.today = date.today()

    def _confirmed(self, user, resource, reservation_date=None):
        return Reservation.objects.create(
            user=user,
            resource=resource,
            reservation_date=reservation_date or self.today,
            status=Reservation.Status.CONFIRMED,
        )

    # DD-2: ensure_can_allocate only answers, it never changes anything.
    def test_rule_check_passes_without_changing_the_reservation(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        ensure_can_allocate(draft)

        draft.refresh_from_db()
        self.assertEqual(draft.status, Reservation.Status.DRAFT)
        self.assertEqual(Reservation.objects.count(), 1)

    # DD-3: the checks run in a fixed order, the first failing one is reported.
    def test_inactive_resource_is_reported_before_the_parking_rule(self):
        draft = create_draft(user=self.user, resource=self.parking, reservation_date=self.today)
        self.parking.is_active = False
        self.parking.save()
        draft.refresh_from_db()

        with self.assertRaisesMessage(ReservationError, "no longer active"):
            ensure_can_allocate(draft)

    # DD-3: a taken parking spot is reported as taken, even when the desk is missing too
    # (OP-03 activity diagram: conflict is checked before BR-04).
    def test_conflict_is_reported_before_the_parking_rule(self):
        self._confirmed(self.other_user, self.parking)
        draft = create_draft(user=self.user, resource=self.parking, reservation_date=self.today)

        with self.assertRaisesMessage(ReservationError, "already confirmed"):
            ensure_can_allocate(draft)

    # DD-3 / BR-04 boundary: only the user's own CONFIRMED desk on the same day counts.
    def test_parking_rule_ignores_desks_that_do_not_count(self):
        tomorrow = self.today + timedelta(days=1)
        self._confirmed(self.other_user, self.desk)  # someone else's desk
        own_desk = Resource.objects.create(name="A02", resource_type=Resource.ResourceType.DESK)
        self._confirmed(self.user, own_desk, tomorrow)  # own desk, other day
        Reservation.objects.create(  # own desk, same day, only requested
            user=self.user,
            resource=Resource.objects.create(name="A03", resource_type=Resource.ResourceType.DESK),
            reservation_date=self.today,
            status=Reservation.Status.PENDING_APPROVAL,
        )
        draft = create_draft(user=self.user, resource=self.parking, reservation_date=self.today)

        with self.assertRaisesMessage(ReservationError, "Parking requires"):
            ensure_can_allocate(draft)

    # DD-4: rules run before the approval branch, so a taken resource cannot even be requested.
    def test_taken_resource_cannot_be_requested_for_approval(self):
        self.desk.requires_approval = True
        self.desk.save()
        self._confirmed(self.other_user, self.desk)
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        with self.assertRaisesMessage(ReservationError, "already confirmed"):
            confirm_reservation(draft)

        draft.refresh_from_db()
        self.assertEqual(draft.status, Reservation.Status.DRAFT)

    # DD-1 precondition: only DRAFT may be confirmed; other states stay untouched.
    def test_only_a_draft_can_be_confirmed(self):
        for status in (
            Reservation.Status.PENDING_APPROVAL,
            Reservation.Status.CONFIRMED,
            Reservation.Status.REJECTED,
            Reservation.Status.EXPIRED,
            Reservation.Status.CANCELLED,
        ):
            with self.subTest(status=status):
                reservation = Reservation.objects.create(
                    user=self.user, resource=self.desk, reservation_date=self.today + timedelta(days=7), status=status
                )

                with self.assertRaisesMessage(ReservationError, "Only draft"):
                    confirm_reservation(reservation)

                reservation.refresh_from_db()
                self.assertEqual(reservation.status, status)
                reservation.delete()

    # BR-06 / C02 evidence finding 2: expiry is bookkeeping and survives a refused change.
    def test_expiry_survives_a_refused_confirmation_and_cancellation(self):
        stale = Reservation.objects.create(
            user=self.other_user,
            resource=self.desk,
            reservation_date=self.today - timedelta(days=1),
            status=Reservation.Status.PENDING_APPROVAL,
        )
        rejected = Reservation.objects.create(
            user=self.user, resource=self.desk, reservation_date=self.today, status=Reservation.Status.REJECTED
        )

        with self.assertRaises(ReservationError):
            confirm_reservation(rejected)
        stale.refresh_from_db()
        self.assertEqual(stale.status, Reservation.Status.EXPIRED)

        stale.status = Reservation.Status.PENDING_APPROVAL
        stale.save()
        with self.assertRaises(ReservationError):
            cancel_reservation(rejected, actor=self.user)
        stale.refresh_from_db()
        self.assertEqual(stale.status, Reservation.Status.EXPIRED)

    # DD-5: when two confirmations race past the rule check, the DB index decides
    # and the loser gets the same ReservationError, not a database error.
    def test_allocate_turns_a_lost_race_into_a_reservation_error(self):
        self._confirmed(self.other_user, self.desk)
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        with self.assertRaisesMessage(ReservationError, "already confirmed"):
            with transaction.atomic():
                allocate(draft)  # skips ensure_can_allocate on purpose, like the second request in a race

        self.assertEqual(
            Reservation.objects.filter(resource=self.desk, status=Reservation.Status.CONFIRMED).count(), 1
        )

    # DD-6: the notification is sent only after the state change is committed.
    def test_notification_waits_for_the_commit(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        with mock.patch("reservations.services.lifecycle.notify_reservation_event") as notify:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                confirm_reservation(draft)

            notify.assert_not_called()
            for callback in callbacks:
                callback()

        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[0], "confirmed")

    # DD-6: nothing is announced when the transaction is rolled back.
    def test_rolled_back_confirmation_is_not_announced(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        with mock.patch("reservations.services.lifecycle.notify_reservation_event") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        confirm_reservation(draft)
                        raise RuntimeError("commit failed")
                except RuntimeError:
                    pass

        notify.assert_not_called()
        draft.refresh_from_db()
        self.assertEqual(draft.status, Reservation.Status.DRAFT)

    # DD-6 / D3: a failing notification does not change the confirmed result.
    def test_failed_notification_keeps_the_reservation_confirmed(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        with mock.patch("reservations.integrations.notifications._send", side_effect=ConnectionError("down")):
            with self.assertLogs("reservations.integrations.notifications", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    confirm_reservation(draft)

        draft.refresh_from_db()
        self.assertEqual(draft.status, Reservation.Status.CONFIRMED)

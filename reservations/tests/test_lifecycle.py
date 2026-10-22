from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..availability import available_resources_for_date
from ..models import Reservation, Resource
from ..services import (
    ReservationError,
    cancel_reservation,
    confirm_reservation,
    create_draft,
    create_reservation,
)


class ReservationServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.other_user = get_user_model().objects.create_user(username="bob", password="password12345")
        self.desk = Resource.objects.create(name="A12", resource_type=Resource.ResourceType.DESK)
        self.parking = Resource.objects.create(name="P4", resource_type=Resource.ResourceType.PARKING_SPOT)
        self.today = date.today()
        self.tomorrow = self.today + timedelta(days=1)

    def test_create_and_confirm_desk_reservation(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)
        confirmed = confirm_reservation(draft)

        self.assertEqual(confirmed.status, Reservation.Status.CONFIRMED)
        self.assertTrue(
            Reservation.objects.filter(resource=self.desk, reservation_date=self.today, status=Reservation.Status.CONFIRMED).exists()
        )

    def test_parking_requires_confirmed_desk(self):
        draft = create_draft(user=self.user, resource=self.parking, reservation_date=self.today)

        with self.assertRaises(ReservationError):
            confirm_reservation(draft)

    def test_parking_can_be_confirmed_after_desk(self):
        desk_draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)
        confirm_reservation(desk_draft)
        parking_draft = create_draft(user=self.user, resource=self.parking, reservation_date=self.today)

        confirmed_parking = confirm_reservation(parking_draft)
        self.assertEqual(confirmed_parking.status, Reservation.Status.CONFIRMED)

    def test_cannot_confirm_overlapping_resource(self):
        confirmed = Reservation.objects.create(
            user=self.other_user,
            resource=self.desk,
            reservation_date=self.tomorrow,
            status=Reservation.Status.CONFIRMED,
        )
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.tomorrow)

        with self.assertRaises(ReservationError):
            confirm_reservation(draft)
        confirmed.refresh_from_db()
        self.assertEqual(confirmed.status, Reservation.Status.CONFIRMED)

    def test_only_owner_can_cancel(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)
        confirmed = confirm_reservation(draft)

        with self.assertRaises(ReservationError):
            cancel_reservation(confirmed, actor=self.other_user)


class CreateReservationTests(TestCase):
    """One action reserves the resource; no draft step is needed (v0.3 flow)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.other_user = get_user_model().objects.create_user(username="bob", password="password12345")
        self.desk = Resource.objects.create(name="A12", resource_type=Resource.ResourceType.DESK)
        self.reserved_desk = Resource.objects.create(
            name="VED-01", resource_type=Resource.ResourceType.DESK, requires_approval=True
        )
        self.parking = Resource.objects.create(name="P4", resource_type=Resource.ResourceType.PARKING_SPOT)
        self.today = date.today()

    def test_one_action_creates_a_confirmed_reservation(self):
        reservation = create_reservation(user=self.user, resource=self.desk, reservation_date=self.today)

        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
        self.assertNotIn(self.desk, available_resources_for_date(self.today))

    def test_flagged_resource_results_in_a_request_instead(self):
        reservation = create_reservation(user=self.user, resource=self.reserved_desk, reservation_date=self.today)

        self.assertEqual(reservation.status, Reservation.Status.PENDING_APPROVAL)
        self.assertIn(self.reserved_desk, available_resources_for_date(self.today))

    def test_nothing_is_left_behind_when_the_check_fails(self):
        Reservation.objects.create(
            user=self.other_user,
            resource=self.desk,
            reservation_date=self.today,
            status=Reservation.Status.CONFIRMED,
        )

        with self.assertRaises(ReservationError):
            create_reservation(user=self.user, resource=self.desk, reservation_date=self.today)

        self.assertFalse(Reservation.objects.filter(user=self.user).exists())

    def test_parking_still_requires_a_confirmed_desk(self):
        with self.assertRaises(ReservationError):
            create_reservation(user=self.user, resource=self.parking, reservation_date=self.today)

        self.assertFalse(Reservation.objects.filter(user=self.user).exists())

    def test_inactive_resource_cannot_be_reserved(self):
        inactive = Resource.objects.create(
            name="A99", resource_type=Resource.ResourceType.DESK, is_active=False
        )

        with self.assertRaises(ReservationError):
            create_reservation(user=self.user, resource=inactive, reservation_date=self.today)


class CancellationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.desk = Resource.objects.create(name="A12", resource_type=Resource.ResourceType.DESK)
        self.today = date.today()

    def test_draft_can_be_cancelled(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        cancelled = cancel_reservation(draft, actor=self.user)

        self.assertEqual(cancelled.status, Reservation.Status.CANCELLED)

    def test_cancelling_confirmed_frees_the_resource(self):
        confirmed = confirm_reservation(
            create_draft(user=self.user, resource=self.desk, reservation_date=self.today)
        )
        self.assertNotIn(self.desk, available_resources_for_date(self.today))

        cancel_reservation(confirmed, actor=self.user)

        self.assertIn(self.desk, available_resources_for_date(self.today))

    def test_already_cancelled_reservation_is_rejected(self):
        confirmed = confirm_reservation(
            create_draft(user=self.user, resource=self.desk, reservation_date=self.today)
        )
        cancel_reservation(confirmed, actor=self.user)

        with self.assertRaises(ReservationError):
            cancel_reservation(confirmed, actor=self.user)

    def test_finished_state_cannot_be_cancelled(self):
        rejected = Reservation.objects.create(
            user=self.user,
            resource=self.desk,
            reservation_date=self.today,
            status=Reservation.Status.REJECTED,
        )

        with self.assertRaises(ReservationError):
            cancel_reservation(rejected, actor=self.user)

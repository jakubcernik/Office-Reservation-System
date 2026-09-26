from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Reservation, Resource
from .services import (
    MANAGER_GROUP_NAME,
    ReservationError,
    available_resources_for_date,
    cancel_reservation,
    confirm_reservation,
    create_draft,
    create_reservation,
    decide_approval,
    expire_stale_approvals,
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


class RegistrationViewTests(TestCase):
    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "charlie",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("reservations:availability"))
        self.assertTrue(get_user_model().objects.filter(username="charlie").exists())
        self.assertIsNotNone(self.client.session.get("_auth_user_id"))


class AvailabilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.other_user = get_user_model().objects.create_user(username="bob", password="password12345")
        self.desk = Resource.objects.create(name="A12", resource_type=Resource.ResourceType.DESK)
        self.inactive_desk = Resource.objects.create(
            name="A13", resource_type=Resource.ResourceType.DESK, is_active=False
        )
        self.today = date.today()

    def test_confirmed_reservation_removes_resource_from_availability(self):
        Reservation.objects.create(
            user=self.other_user,
            resource=self.desk,
            reservation_date=self.today,
            status=Reservation.Status.CONFIRMED,
        )

        self.assertNotIn(self.desk, available_resources_for_date(self.today))

    def test_draft_does_not_block_availability(self):
        create_draft(user=self.other_user, resource=self.desk, reservation_date=self.today)

        self.assertIn(self.desk, available_resources_for_date(self.today))

    def test_pending_approval_does_not_block_availability(self):
        Reservation.objects.create(
            user=self.other_user,
            resource=self.desk,
            reservation_date=self.today,
            status=Reservation.Status.PENDING_APPROVAL,
        )

        self.assertIn(self.desk, available_resources_for_date(self.today))

    def test_inactive_resource_is_never_offered(self):
        self.assertNotIn(self.inactive_desk, available_resources_for_date(self.today))


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


class ApprovalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.other_user = get_user_model().objects.create_user(username="bob", password="password12345")
        self.manager = get_user_model().objects.create_user(
            username="manager", password="password12345", is_staff=True
        )
        self.reserved_desk = Resource.objects.create(
            name="VED-01", resource_type=Resource.ResourceType.DESK, requires_approval=True
        )
        self.parking = Resource.objects.create(
            name="P-VIP", resource_type=Resource.ResourceType.PARKING_SPOT, requires_approval=True
        )
        self.today = date.today()

    def test_confirm_creates_a_request_instead_of_a_confirmation(self):
        draft = create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)

        requested = confirm_reservation(draft)

        self.assertEqual(requested.status, Reservation.Status.PENDING_APPROVAL)
        self.assertIn(self.reserved_desk, available_resources_for_date(self.today))

    def test_manager_approves_the_request(self):
        request = confirm_reservation(
            create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)
        )

        approved = decide_approval(request, actor=self.manager, approve=True)

        self.assertEqual(approved.status, Reservation.Status.CONFIRMED)
        self.assertNotIn(self.reserved_desk, available_resources_for_date(self.today))

    def test_manager_rejects_the_request(self):
        request = confirm_reservation(
            create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)
        )

        rejected = decide_approval(request, actor=self.manager, approve=False)

        self.assertEqual(rejected.status, Reservation.Status.REJECTED)
        self.assertIn(self.reserved_desk, available_resources_for_date(self.today))

    def test_request_expires_when_its_day_is_over(self):
        request = Reservation.objects.create(
            user=self.user,
            resource=self.reserved_desk,
            reservation_date=self.today - timedelta(days=1),
            status=Reservation.Status.PENDING_APPROVAL,
        )

        expire_stale_approvals()
        request.refresh_from_db()

        self.assertEqual(request.status, Reservation.Status.EXPIRED)

    def test_expired_request_cannot_be_approved(self):
        request = Reservation.objects.create(
            user=self.user,
            resource=self.reserved_desk,
            reservation_date=self.today - timedelta(days=1),
            status=Reservation.Status.PENDING_APPROVAL,
        )

        with self.assertRaises(ReservationError):
            decide_approval(request, actor=self.manager, approve=True)
        request.refresh_from_db()
        self.assertEqual(request.status, Reservation.Status.EXPIRED)

    def test_second_request_for_the_same_resource_and_day_cannot_be_approved(self):
        first = confirm_reservation(
            create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)
        )
        second = confirm_reservation(
            create_draft(user=self.other_user, resource=self.reserved_desk, reservation_date=self.today)
        )
        decide_approval(first, actor=self.manager, approve=True)

        with self.assertRaises(ReservationError):
            decide_approval(second, actor=self.manager, approve=True)
        second.refresh_from_db()
        self.assertEqual(second.status, Reservation.Status.PENDING_APPROVAL)

    def test_approval_rechecks_the_parking_rule(self):
        desk = Resource.objects.create(name="A12", resource_type=Resource.ResourceType.DESK)
        desk_reservation = confirm_reservation(
            create_draft(user=self.user, resource=desk, reservation_date=self.today)
        )
        parking_request = confirm_reservation(
            create_draft(user=self.user, resource=self.parking, reservation_date=self.today)
        )
        self.assertEqual(parking_request.status, Reservation.Status.PENDING_APPROVAL)
        cancel_reservation(desk_reservation, actor=self.user)

        with self.assertRaises(ReservationError):
            decide_approval(parking_request, actor=self.manager, approve=True)
        parking_request.refresh_from_db()
        self.assertEqual(parking_request.status, Reservation.Status.PENDING_APPROVAL)

    def test_regular_user_cannot_decide_about_approval(self):
        request = confirm_reservation(
            create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)
        )

        with self.assertRaises(ReservationError):
            decide_approval(request, actor=self.user, approve=True)

    def test_member_of_the_office_manager_group_can_decide(self):
        group = Group.objects.create(name=MANAGER_GROUP_NAME)
        member = get_user_model().objects.create_user(username="hana", password="password12345")
        member.groups.add(group)
        request = confirm_reservation(
            create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)
        )

        approved = decide_approval(request, actor=member, approve=True)

        self.assertEqual(approved.status, Reservation.Status.CONFIRMED)

    def test_owner_can_withdraw_a_pending_request(self):
        request = confirm_reservation(
            create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)
        )

        withdrawn = cancel_reservation(request, actor=self.user)

        self.assertEqual(withdrawn.status, Reservation.Status.CANCELLED)


class ApprovalViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.manager = get_user_model().objects.create_user(
            username="manager", password="password12345", is_staff=True
        )
        self.reserved_desk = Resource.objects.create(
            name="VED-01", resource_type=Resource.ResourceType.DESK, requires_approval=True
        )
        self.today = date.today()

    def _create_request(self):
        return confirm_reservation(
            create_draft(user=self.user, resource=self.reserved_desk, reservation_date=self.today)
        )

    def test_approvals_page_lists_waiting_requests(self):
        self._create_request()
        self.client.force_login(self.manager)

        response = self.client.get(reverse("reservations:approvals"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VED-01")
        self.assertContains(response, "alice")

    def test_approvals_page_is_forbidden_for_regular_users(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("reservations:approvals"))

        self.assertEqual(response.status_code, 403)

    def test_manager_approves_a_request_through_the_page(self):
        request = self._create_request()
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("reservations:decide_approval", args=[request.pk]), {"decision": "approve"}
        )

        self.assertRedirects(response, reverse("reservations:approvals"))
        request.refresh_from_db()
        self.assertEqual(request.status, Reservation.Status.CONFIRMED)

    def test_unknown_decision_is_rejected(self):
        request = self._create_request()
        self.client.force_login(self.manager)

        self.client.post(reverse("reservations:decide_approval", args=[request.pk]), {"decision": "maybe"})

        request.refresh_from_db()
        self.assertEqual(request.status, Reservation.Status.PENDING_APPROVAL)

    def test_availability_marks_resources_that_need_approval(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("reservations:availability"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approval needed")

    def test_my_reservations_offers_withdrawing_a_request(self):
        self._create_request()
        self.client.force_login(self.user)

        response = self.client.get(reverse("reservations:my_reservations"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Withdraw request")
        self.assertNotContains(response, ">Confirm<")


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


class AvailabilityActionViewTests(TestCase):
    """The availability page offers the follow-up action right where the draft was created."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.desk = Resource.objects.create(name="A12", resource_type=Resource.ResourceType.DESK)
        self.today = date.today()
        self.availability_url = f"{reverse('reservations:availability')}?date={self.today.isoformat()}"
        self.client.force_login(self.user)

    def test_availability_page_offers_the_reserve_action(self):
        response = self.client.get(reverse("reservations:availability"), {"date": self.today})

        self.assertContains(response, ">Reserve<")

    def test_reserve_button_creates_a_confirmed_reservation(self):
        response = self.client.post(
            reverse("reservations:create_reservation"),
            {"resource_id": self.desk.pk, "reservation_date": self.today.isoformat()},
        )

        self.assertRedirects(response, self.availability_url)
        self.assertTrue(
            Reservation.objects.filter(
                user=self.user, resource=self.desk, status=Reservation.Status.CONFIRMED
            ).exists()
        )

    def test_reserve_button_turns_a_flagged_resource_into_a_request(self):
        flagged = Resource.objects.create(
            name="VED-01", resource_type=Resource.ResourceType.DESK, requires_approval=True
        )

        self.client.post(
            reverse("reservations:create_reservation"),
            {"resource_id": flagged.pk, "reservation_date": self.today.isoformat()},
        )

        self.assertTrue(
            Reservation.objects.filter(
                user=self.user, resource=flagged, status=Reservation.Status.PENDING_APPROVAL
            ).exists()
        )

    def test_availability_page_offers_confirming_a_draft(self):
        create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        response = self.client.get(reverse("reservations:availability"), {"date": self.today})

        self.assertContains(response, ">Confirm<")
        self.assertNotContains(response, "Request approval")

    def test_availability_page_offers_requesting_approval_for_flagged_resources(self):
        flagged = Resource.objects.create(
            name="VED-01", resource_type=Resource.ResourceType.DESK, requires_approval=True
        )
        create_draft(user=self.user, resource=flagged, reservation_date=self.today)

        response = self.client.get(reverse("reservations:availability"), {"date": self.today})

        self.assertContains(response, "Request approval")

    def test_confirm_returns_to_the_availability_page(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        response = self.client.post(
            reverse("reservations:confirm_reservation", args=[draft.pk]), {"next": self.availability_url}
        )

        self.assertRedirects(response, self.availability_url)
        draft.refresh_from_db()
        self.assertEqual(draft.status, Reservation.Status.CONFIRMED)

    def test_cancel_returns_to_the_availability_page(self):
        confirmed = confirm_reservation(
            create_draft(user=self.user, resource=self.desk, reservation_date=self.today)
        )

        response = self.client.post(
            reverse("reservations:cancel_reservation", args=[confirmed.pk]), {"next": self.availability_url}
        )

        self.assertRedirects(response, self.availability_url)

    def test_next_target_outside_the_site_is_ignored(self):
        draft = create_draft(user=self.user, resource=self.desk, reservation_date=self.today)

        response = self.client.post(
            reverse("reservations:confirm_reservation", args=[draft.pk]),
            {"next": "https://example.com/steal"},
        )

        self.assertRedirects(response, reverse("reservations:my_reservations"))



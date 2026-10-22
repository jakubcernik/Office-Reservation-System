from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from ..availability import available_resources_for_date
from ..models import Reservation, Resource
from ..services import (
    MANAGER_GROUP_NAME,
    ReservationError,
    cancel_reservation,
    confirm_reservation,
    create_draft,
    decide_approval,
    expire_stale_approvals,
)


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

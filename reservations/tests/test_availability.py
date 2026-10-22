from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..availability import available_resources_for_date
from ..models import Reservation, Resource
from ..services import create_draft


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

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..availability import active_resources, available_resources_for_date, floor_plan_spots
from ..models import Reservation, Resource
from ..services import create_reservation


class FloorPlanTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.other_user = get_user_model().objects.create_user(username="bob", password="password12345")
        self.free_desk = Resource.objects.create(name="A01", resource_type=Resource.ResourceType.DESK)
        self.my_desk = Resource.objects.create(name="A02", resource_type=Resource.ResourceType.DESK)
        self.taken_desk = Resource.objects.create(name="A03", resource_type=Resource.ResourceType.DESK)
        self.manager_desk = Resource.objects.create(
            name="VED-01", resource_type=Resource.ResourceType.DESK, requires_approval=True
        )
        self.unplaced_desk = Resource.objects.create(name="Z99", resource_type=Resource.ResourceType.DESK)
        self.today = date.today()
        create_reservation(user=self.user, resource=self.my_desk, reservation_date=self.today)
        create_reservation(user=self.other_user, resource=self.taken_desk, reservation_date=self.today)

    def test_spots_are_painted_by_their_state(self):
        spots = floor_plan_spots(
            active_resources(),
            available_resources_for_date(self.today).values_list("pk", flat=True),
            Reservation.objects.filter(user=self.user, reservation_date=self.today),
        )
        states = {spot["resource"].name: spot["state"] for spot in spots}

        self.assertEqual(
            states,
            {"A01": "free", "A02": "mine", "A03": "taken", "VED-01": "approval"},
        )

    def test_availability_page_renders_floor_plan(self):
        self.client.login(username="alice", password="password12345")
        response = self.client.get(reverse("reservations:availability"))

        self.assertContains(response, 'class="floor-plan"')
        self.assertContains(response, 'data-name="A01"')
        self.assertNotContains(response, 'data-name="Z99"')

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Reservation, Resource
from ..services import confirm_reservation, create_draft, decide_approval


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

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Reservation, Resource
from ..services import cancel_reservation, confirm_reservation, create_draft, create_reservation


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


class ReservationPageRuleTests(TestCase):
    """Verification examples from C02 that are checked through HTTP."""

    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="alice", password="password12345")
        self.stranger = get_user_model().objects.create_user(username="bob", password="password12345")
        self.desk = Resource.objects.create(name="A12", resource_type=Resource.ResourceType.DESK)
        self.today = date.today()

    # OP-03: "cizí rezervace → přístup odmítnut (403), stav beze změny"
    def test_confirming_someone_elses_reservation_is_forbidden(self):
        draft = create_draft(user=self.owner, resource=self.desk, reservation_date=self.today)
        self.client.force_login(self.stranger)

        response = self.client.post(reverse("reservations:confirm_reservation", args=[draft.pk]))

        self.assertEqual(response.status_code, 403)
        draft.refresh_from_db()
        self.assertEqual(draft.status, Reservation.Status.DRAFT)

    # OP-02: "neplatné datum → použije se dnešní den"
    def test_invalid_date_falls_back_to_today(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("reservations:availability") + "?date=not-a-date")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_date"], self.today)

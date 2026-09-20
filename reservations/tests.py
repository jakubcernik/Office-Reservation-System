from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Reservation, Resource
from .services import ReservationError, cancel_reservation, confirm_reservation, create_draft


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



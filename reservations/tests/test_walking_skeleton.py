"""CP1 walking skeleton check (README, "CP1 walking skeleton")."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Reservation, Resource


class WalkingSkeletonReservationCreateTests(TestCase):
    url = "/reservations"

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password12345")
        self.desk = Resource.objects.create(name="A01", resource_type=Resource.ResourceType.DESK)

    def _post(self, body):
        return self.client.post(self.url, data=json.dumps(body), content_type="application/json")

    def test_post_creates_reservation_and_returns_its_id(self):
        self.client.force_login(self.user)

        response = self._post({"resource_id": self.desk.pk, "reservation_date": "2026-09-21"})

        self.assertEqual(response.status_code, 201)
        reservation_id = response.json()["reservation_id"]
        reservation = Reservation.objects.get(pk=reservation_id)
        self.assertEqual(reservation.user, self.user)
        self.assertEqual(reservation.resource, self.desk)
        self.assertEqual(reservation.reservation_date, date(2026, 9, 21))
        self.assertEqual(reservation.status, Reservation.Status.DRAFT)

    def test_anonymous_request_is_rejected(self):
        response = self._post({"resource_id": self.desk.pk, "reservation_date": "2026-09-21"})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Reservation.objects.exists())

    def test_invalid_input_is_rejected(self):
        self.client.force_login(self.user)
        self.desk.is_active = False
        self.desk.save()
        cases = {
            "unknown resource": {"resource_id": 9999, "reservation_date": "2026-09-21"},
            "inactive resource": {"resource_id": self.desk.pk, "reservation_date": "2026-09-21"},
            "invalid date": {"resource_id": self.desk.pk, "reservation_date": "2026-02-30"},
        }
        for name, body in cases.items():
            with self.subTest(name):
                self.assertEqual(self._post(body).status_code, 400)
        self.assertEqual(self.client.post(self.url, data="not json", content_type="application/json").status_code, 400)
        self.assertFalse(Reservation.objects.exists())

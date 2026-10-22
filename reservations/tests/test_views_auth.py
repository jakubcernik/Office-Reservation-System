from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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

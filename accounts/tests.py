from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AccountTests(TestCase):

    def signup(self, **overrides):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password1": "StrongPass!2026",
            "password2": "StrongPass!2026",
        }
        data.update(overrides)
        return self.client.post(reverse("accounts:signup"), data)

    def test_signup_creates_user_and_logs_in(self):
        response = self.signup()
        self.assertRedirects(response, reverse("store:product_list"))
        self.assertTrue(User.objects.filter(username="newuser").exists())
        # The user is now logged in, so the account page loads
        self.assertEqual(self.client.get(reverse("accounts:account")).status_code, 200)

    def test_signup_stores_email_lowercase(self):
        self.signup(email="New@Example.COM")
        self.assertEqual(User.objects.get(username="newuser").email, "new@example.com")

    def test_account_page_requires_login(self):
        response = self.client.get(reverse("accounts:account"))
        login_url = reverse("accounts:login")
        self.assertRedirects(response, f"{login_url}?next={reverse('accounts:account')}")

    def test_duplicate_email_rejected(self):
        User.objects.create_user("existing", "taken@example.com", "StrongPass!2026")
        response = self.signup(email="TAKEN@example.com")
        self.assertEqual(response.status_code, 200)   # form shown again, no redirect
        self.assertContains(response, "An account with this email already exists.")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_mismatched_passwords_rejected(self):
        self.signup(password2="DifferentPass!2026")
        self.assertEqual(User.objects.count(), 0)

    def test_wrong_password_shows_error(self):
        User.objects.create_user("arib", "arib@example.com", "StrongPass!2026")
        response = self.client.post(reverse("accounts:login"), {"username": "arib", "password": "wrong"})
        self.assertContains(response, "Wrong username or password")

    def test_logout_requires_post(self):
        user = User.objects.create_user("arib", "arib@example.com", "StrongPass!2026")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("store:product_list"))

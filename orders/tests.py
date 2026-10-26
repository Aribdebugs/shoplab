from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from store.currency import CACHE_KEY
from store.models import Category, Product

from .models import Order


class CheckoutTests(TestCase):

    def setUp(self):
        cache.set(CACHE_KEY, Decimal("120"), None)   # fixed rate, no real API call
        self.user = User.objects.create_user("buyer", "buyer@example.com", "StrongPass!2026")
        category = Category.objects.create(name="Phones", slug="phones")
        self.product = Product.objects.create(
            external_id=1, title="Test Phone", slug="test-phone-1", description="Test",
            category=category, price=Decimal("100.00"), discount_percentage=Decimal("10.00"), stock=5,
        )
        self.shipping = {
            "full_name": "Test Buyer",
            "phone": "01712345678",
            "address": "House 1, Road 2",
            "city": "Dhaka",
        }

    def add_to_cart(self, quantity):
        self.client.post(reverse("store:cart_add", args=[self.product.id]), {"quantity": quantity})

    def place_order(self, quantity=2, **shipping):
        self.client.force_login(self.user)
        self.add_to_cart(quantity)
        return self.client.post(reverse("orders:checkout"), {**self.shipping, **shipping})

    def test_successful_checkout(self):
        response = self.place_order(2)

        order = Order.objects.get()                       # exactly one order exists
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual(order.total, Decimal("180.00"))  # 2 × 90.00 discounted
        self.assertEqual(order.items.count(), 1)
        self.product.refresh_from_db()                    # reload from the database
        self.assertEqual(self.product.stock, 3)           # 5 − 2
        self.assertEqual(self.client.session.get("cart"), None)   # cart cleared

    def test_checkout_requires_login(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('orders:checkout')}")

    def test_empty_cart_redirects_to_cart(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("store:cart_detail"))

    def test_invalid_phone_rejected(self):
        response = self.place_order(phone="12345")
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, "Enter a valid Bangladeshi mobile number")

    def test_phone_with_spaces_dashes_and_country_code_accepted(self):
        self.place_order(phone="+880 1712-345678")
        self.assertEqual(Order.objects.get().phone, "01712345678")

    def test_out_of_stock_creates_no_order(self):
        self.client.force_login(self.user)
        self.add_to_cart(2)
        self.product.stock = 1
        self.product.save()
        response = self.client.post(reverse("orders:checkout"), self.shipping, follow=True)

        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, "Only 1 left of Test Phone.")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)   # the transaction rolled back

    def test_order_snapshot_survives_price_change(self):
        self.place_order(2)
        self.product.price = Decimal("999.00")
        self.product.save()
        order = Order.objects.get()
        self.assertEqual(order.items.get().unit_price, Decimal("90.00"))
        self.assertEqual(order.total, Decimal("180.00"))

    def test_cannot_view_another_users_order(self):
        self.place_order(2)
        order = Order.objects.get()
        other = User.objects.create_user("other", "other@example.com", "StrongPass!2026")
        self.client.force_login(other)
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)

    def test_account_page_lists_orders(self):
        self.place_order(2)
        response = self.client.get(reverse("accounts:account"))
        order = response.context["orders"].get()
        self.assertEqual(order.item_count, 2)
        self.assertContains(response, f"#{order.id}")

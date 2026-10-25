from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class ProductTests(TestCase):
    """setUp runs before EVERY test, on a fresh empty test database."""

    def setUp(self):
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.product = Product.objects.create(
            external_id=1,
            title="Test Phone",
            slug="test-phone-1",
            description="A phone for testing.",
            category=self.category,
            price=Decimal("100.00"),
            discount_percentage=Decimal("15.00"),
            stock=5,
        )

    def test_product_list_shows_product(self):
        response = self.client.get(reverse("store:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Phone")

    # ✍️ YOUR TURN: write these three tests
    # def test_discounted_price(self):
    #     expected: Decimal("85.00")
    #
    # def test_product_detail_page_loads(self):
    #     GET the product's URL (hint: self.product.get_absolute_url())
    #     expected: status 200, and the page contains "Test Phone"
    #
    # def test_missing_product_returns_404(self):
    #     GET reverse("store:product_detail", args=["does-not-exist"])
    #     expected: status 404
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem

from .currency import CACHE_KEY
from .models import Category, Product, Review
from .templatetags.currency import bdt


def make_product(category, n, **fields):
    """Create a product with a unique external_id and slug."""
    defaults = {
        "title": f"Product {n}", "slug": f"product-{n}", "description": "A product.",
        "price": Decimal("50.00"), "stock": 1,
    }
    defaults.update(fields)
    return Product.objects.create(category=category, external_id=n, **defaults)


class ProductTests(TestCase):
    def setUp(self):
        # Fixed exchange rate, so tests never call the real currency API
        cache.set(CACHE_KEY, Decimal("120"), None)
        self.category = Category.objects.create(name="Smartphones", slug="smartphones")
        self.product = make_product(
            self.category, 1, title="Test Phone", slug="test-phone",
            price=Decimal("100.00"), discount_percentage=Decimal("10"), stock=5,
        )

    # --- Day 2: pages and price ---

    def test_product_list_shows_products(self):
        response = self.client.get(reverse("store:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Phone")

    def test_product_detail_shows_product(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, "Test Phone")
        self.assertContains(response, "In stock (5 left)")

    def test_unknown_product_returns_404(self):
        response = self.client.get(reverse("store:product_detail", args=["no-such-product"]))
        self.assertEqual(response.status_code, 404)

    def test_discounted_price(self):
        self.assertEqual(self.product.discounted_price, Decimal("90.00"))

    def test_bdt_filter_converts_and_falls_back_to_usd(self):
        self.assertEqual(bdt(Decimal("90.00")), "৳10,800")
        cache.set(CACHE_KEY, 0, None)   # 0 = "rate unavailable"
        self.assertEqual(bdt(Decimal("90.00")), "$90.00")

    # --- Day 3: search, category filter, pagination, sorting ---

    def test_search_finds_matching_product(self):
        response = self.client.get(reverse("store:product_list"), {"q": "phone"})
        self.assertContains(response, "Test Phone")

    def test_search_excludes_non_matching(self):
        response = self.client.get(reverse("store:product_list"), {"q": "laptop"})
        self.assertNotContains(response, "Test Phone")
        self.assertContains(response, "No products found")

    def test_category_filter(self):
        laptops = Category.objects.create(name="Laptops", slug="laptops")
        make_product(laptops, 2, title="Test Laptop")
        response = self.client.get(reverse("store:product_list"), {"category": "smartphones"})
        self.assertContains(response, "Test Phone")
        self.assertNotContains(response, "Test Laptop")

    def test_unknown_category_returns_404(self):
        response = self.client.get(reverse("store:product_list"), {"category": "fake"})
        self.assertEqual(response.status_code, 404)

    def test_pagination_limits_products_per_page(self):
        for n in range(2, 17):   # 15 more, 16 in total
            make_product(self.category, n)
        response = self.client.get(reverse("store:product_list"))
        self.assertEqual(len(response.context["page_obj"]), 12)
        response = self.client.get(reverse("store:product_list"), {"page": 999})
        self.assertEqual(response.context["page_obj"].number, 2)   # last page, not an error

    def test_sort_by_price(self):
        cheap = make_product(self.category, 2, price=Decimal("10.00"))
        response = self.client.get(reverse("store:product_list"), {"sort": "price_asc"})
        self.assertEqual(response.context["page_obj"][0], cheap)

    def test_sort_uses_discounted_price(self):
        # $95 with no discount is dearer than $100 with 10% off ($90)
        make_product(self.category, 2, price=Decimal("95.00"))
        response = self.client.get(reverse("store:product_list"), {"sort": "price_asc"})
        self.assertEqual(response.context["page_obj"][0], self.product)

    def test_unknown_sort_falls_back_to_name(self):
        response = self.client.get(reverse("store:product_list"), {"sort": "DROP TABLE"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sort"], "name")


class CartTests(TestCase):

    def setUp(self):
        cache.set(CACHE_KEY, Decimal("120"), None)   # fixed rate, no real API call
        category = Category.objects.create(name="Phones", slug="phones")
        self.product = Product.objects.create(
            external_id=1, title="Test Phone", slug="test-phone-1",
            description="Test", category=category,
            price=Decimal("100.00"), discount_percentage=Decimal("10.00"), stock=5,
        )

    def add(self, quantity):
        """Helper: post to add-to-cart."""
        return self.client.post(reverse("store:cart_add", args=[self.product.id]), {"quantity": quantity})

    def cart(self):
        return self.client.session.get("cart", {})

    def test_add_to_cart_stores_quantity(self):
        self.add(2)
        self.assertEqual(self.client.session["cart"], {str(self.product.id): 2})

    def test_adding_twice_sums_quantity(self):
        self.add(2)
        self.add(1)
        self.assertEqual(self.cart(), {str(self.product.id): 3})

    def test_quantity_capped_at_stock(self):
        self.add(99)
        self.assertEqual(self.cart(), {str(self.product.id): 5})

    def test_cart_total_uses_discounted_price(self):
        self.add(2)
        response = self.client.get(reverse("store:cart_detail"))
        self.assertEqual(response.context["total"], Decimal("180.00"))

    def test_remove_from_cart(self):
        self.add(2)
        self.client.post(reverse("store:cart_remove", args=[self.product.id]))
        self.assertEqual(self.cart(), {})

    def test_update_to_zero_removes_item(self):
        self.add(2)
        self.client.post(reverse("store:cart_update", args=[self.product.id]), {"quantity": 0})
        self.assertEqual(self.cart(), {})

    def test_add_requires_post(self):
        response = self.client.get(reverse("store:cart_add", args=[self.product.id]))
        self.assertEqual(response.status_code, 405)

    def test_invalid_quantity_defaults_to_one(self):
        self.add("abc")
        self.assertEqual(self.cart(), {str(self.product.id): 1})

    def test_out_of_stock_product_not_added(self):
        self.product.stock = 0
        self.product.save()
        self.add(1)
        self.assertEqual(self.cart(), {})

    def test_deleted_product_disappears_from_cart(self):
        self.add(2)
        self.product.delete()
        response = self.client.get(reverse("store:cart_detail"))
        self.assertEqual(response.context["items"], [])
        self.assertEqual(self.cart(), {})   # navbar count drops to 0 too

    def test_navbar_shows_cart_count(self):
        self.add(3)
        response = self.client.get(reverse("store:product_list"))
        self.assertEqual(response.context["cart_count"], 3)


class ReviewTests(TestCase):

    def setUp(self):
        cache.set(CACHE_KEY, Decimal("120"), None)   # fixed rate, no real API call
        self.user = User.objects.create_user("buyer", "buyer@example.com", "StrongPass!2026")
        category = Category.objects.create(name="Phones", slug="phones")
        self.product = Product.objects.create(
            external_id=1, title="Test Phone", slug="test-phone-1", description="Test",
            category=category, price=Decimal("100.00"), stock=5, rating=Decimal("0"),
        )
        self.url = reverse("store:add_review", args=[self.product.slug])

    def make_purchase(self, status=Order.Status.DELIVERED):
        """Helper: give self.user an order containing the product."""
        order = Order.objects.create(
            user=self.user, full_name="Buyer", phone="01712345678",
            address="Dhaka", city="Dhaka", total=Decimal("100.00"), status=status,
        )
        OrderItem.objects.create(order=order, product=self.product,
                                 product_title="Test Phone", unit_price=Decimal("100.00"), quantity=1)

    def review(self, rating=4, comment="Great phone"):
        return self.client.post(self.url, {"rating": rating, "comment": comment})

    def test_buyer_can_review(self):
        self.make_purchase()
        self.client.force_login(self.user)
        self.review()
        review = Review.objects.get(user=self.user)
        self.assertTrue(review.is_verified)
        self.assertEqual(review.reviewer_name, "buyer")

    def test_non_buyer_cannot_review(self):
        self.client.force_login(self.user)
        self.review()
        self.assertEqual(Review.objects.count(), 0)

    def test_cancelled_order_cannot_review(self):
        self.make_purchase(Order.Status.CANCELLED)
        self.client.force_login(self.user)
        self.review()
        self.assertEqual(Review.objects.count(), 0)

    def test_only_one_review_per_user(self):
        self.make_purchase()
        self.client.force_login(self.user)
        self.review()
        self.review(rating=1)
        self.assertEqual(Review.objects.filter(user=self.user).count(), 1)

    def test_database_blocks_duplicate_review(self):
        # The final guarantee, even if the view's check were skipped
        Review.objects.create(product=self.product, user=self.user, reviewer_name="buyer", rating=5, comment="a")
        with self.assertRaises(IntegrityError):
            Review.objects.create(product=self.product, user=self.user, reviewer_name="buyer", rating=4, comment="b")

    def test_imported_reviews_are_exempt_from_one_per_user(self):
        for _ in range(2):
            Review.objects.create(product=self.product, reviewer_name="Guest", rating=5, comment="ok")
        self.assertEqual(self.product.reviews.count(), 2)

    def test_rating_updates_product_average(self):
        Review.objects.create(product=self.product, reviewer_name="Guest", rating=5, comment="ok")
        self.make_purchase()
        self.client.force_login(self.user)
        self.review(rating=4)
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating, Decimal("4.50"))   # (5 + 4) / 2

    def test_logged_out_user_redirected(self):
        response = self.review()
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")
        self.assertEqual(Review.objects.count(), 0)

    def test_rating_out_of_range_rejected(self):
        self.make_purchase()
        self.client.force_login(self.user)
        self.review(rating=9)
        self.assertEqual(Review.objects.count(), 0)

    def test_product_page_shows_form_only_to_buyers(self):
        page = self.product.get_absolute_url()
        self.assertContains(self.client.get(page), "Log in to write a review")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(page), "Only customers who bought")
        self.make_purchase()
        self.assertContains(self.client.get(page), "Submit review")
        self.review()
        response = self.client.get(page)
        self.assertContains(response, "You've reviewed this product")
        self.assertContains(response, "✓ Verified buyer")

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)   # URL-friendly name, e.g. "home-decoration"

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"   # admin shows "categories", not "categorys"

    def __str__(self):
        return self.name


class Product(models.Model):
    # ID from DummyJSON; prevents duplicate imports. Empty for products added by hand in the admin.
    external_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(   # Decimal, never float, for money
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    stock = models.PositiveIntegerField(default=0)
    thumbnail = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        # Validators only run in forms; constraints also protect the database from scripts and imports
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="product_price_non_negative"),
            models.CheckConstraint(
                condition=models.Q(discount_percentage__gte=0, discount_percentage__lte=100),
                name="product_discount_0_to_100",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=0, rating__lte=5), name="product_rating_0_to_5"
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("store:product_detail", args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def discounted_price(self):
        """Price after discount, rounded to 2 decimal places."""
        discount = self.price * self.discount_percentage / Decimal(100)
        return (self.price - discount).quantize(Decimal("0.01"))


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    # Imported reviews have no user account, so user can be empty
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews"
    )
    reviewer_name = models.CharField(max_length=100)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)   # not auto_now_add, so imports keep their original date

    class Meta:
        ordering = ["-created_at"]   # newest first
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"
            ),
            # One review per user per product. Imported reviews (user=None) are exempt.
            models.UniqueConstraint(
                fields=["product", "user"],
                condition=models.Q(user__isnull=False),
                name="one_review_per_user_per_product",
            ),
        ]

    def __str__(self):
        return f"{self.rating}★ by {self.reviewer_name} on {self.product}"

    @property
    def is_verified(self):
        """Reviews from real accounts come only from verified buyers."""
        return self.user_id is not None

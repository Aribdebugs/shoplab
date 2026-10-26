from django.conf import settings
from django.db import models
from django.urls import reverse

from store.models import Product


class Order(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    # Bootstrap badge colour for each status, used in templates
    STATUS_COLORS = {
        Status.PENDING: "secondary",
        Status.PROCESSING: "info",
        Status.SHIPPED: "primary",
        Status.DELIVERED: "success",
        Status.CANCELLED: "danger",
    }

    # PROTECT: you can't delete a user who has orders; business records must survive
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")

    # Delivery details
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=11)
    address = models.TextField()
    city = models.CharField(max_length=50)

    payment_method = models.CharField(max_length=20, default="cod", editable=False)  # Cash on Delivery
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    # Snapshot, like unit_price: the taka amounts on this order must not move with tomorrow's rate
    exchange_rate = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True, editable=False,
        help_text="USD→BDT rate at the moment the order was placed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]   # newest first

    def __str__(self):
        return f"Order #{self.id}"

    def get_absolute_url(self):
        return reverse("orders:order_detail", args=[self.id])

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, "secondary")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")

    # SET_NULL: if a product is later deleted, the order history still exists
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)

    # Snapshot: copied at purchase time, so old orders never change
    product_title = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity} × {self.product_title}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

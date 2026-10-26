"""Turn a cart into a saved order, safely."""

from decimal import Decimal

from django.db import transaction
from django.db.models import F

from store.currency import get_usd_to_bdt
from store.models import Product

from .models import Order, OrderItem


class OutOfStockError(Exception):
    """Raised when a product doesn't have enough stock for the order."""


@transaction.atomic   # everything below succeeds together, or nothing is saved
def create_order(user, cart, shipping_data):
    cart_items = list(cart)
    if not cart_items:
        raise ValueError("Cannot create an order from an empty cart.")

    # Lock these product rows until the transaction ends, so two checkouts
    # can't both buy the last item at the same moment (race condition).
    # Note: SQLite ignores this lock; PostgreSQL enforces it in production.
    product_ids = [item["product"].id for item in cart_items]
    products = {p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)}

    # Stock check against the locked, up-to-date rows
    for item in cart_items:
        product = products.get(item["product"].id)
        if product is None:   # deleted by the admin since the cart was loaded
            raise OutOfStockError(f"{item['product'].title} is no longer available.")
        if product.stock < item["quantity"]:
            raise OutOfStockError(f"Only {product.stock} left of {product.title}.")

    total = sum(
        (products[item["product"].id].discounted_price * item["quantity"] for item in cart_items),
        Decimal("0.00"),
    )
    # exchange_rate is None if the rate API is down; the order pages then show USD
    order = Order.objects.create(user=user, total=total, exchange_rate=get_usd_to_bdt(), **shipping_data)

    for item in cart_items:
        product = products[item["product"].id]
        OrderItem.objects.create(
            order=order,
            product=product,
            product_title=product.title,          # snapshot
            unit_price=product.discounted_price,  # snapshot
            quantity=item["quantity"],
        )
        # F() makes the DATABASE do the subtraction: "stock = stock - 2".
        # Reading stock into Python, subtracting, and saving could lose updates
        # if two orders happen at once.
        Product.objects.filter(id=product.id).update(stock=F("stock") - item["quantity"])

    return order

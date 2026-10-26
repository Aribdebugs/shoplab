"""Session-based shopping cart. Stores only product IDs and quantities."""

from decimal import Decimal

from .models import Product

CART_SESSION_KEY = "cart"


class Cart:
    def __init__(self, request):
        self.session = request.session
        # Read this visitor's cart. Unlike setdefault, .get() doesn't write to the session,
        # so visitors who never add anything don't get a session row in the database.
        self.items = self.session.get(CART_SESSION_KEY, {})

    def save(self):
        # Store the dict (needed the first time), and mark the session as changed:
        # changing a dict INSIDE the session doesn't trigger a save automatically
        self.session[CART_SESSION_KEY] = self.items
        self.session.modified = True

    def add(self, product, quantity=1, override=False):
        """Add a quantity, or set it exactly when override=True."""
        pid = str(product.id)   # session keys must be strings (JSON)
        current = 0 if override else self.items.get(pid, 0)
        new_quantity = min(current + quantity, product.stock)   # never more than we have

        if new_quantity <= 0:
            self.remove(product)
            return

        self.items[pid] = new_quantity
        self.save()

    def remove(self, product):
        """Remove a product from the cart completely."""
        self.items.pop(str(product.id), None)   # None: no error if it isn't there
        self.save()

    def __iter__(self):
        """Loop over the cart, attaching fresh product data and prices from the database."""
        products = Product.objects.filter(id__in=self.items.keys()).select_related("category")
        found = set()
        for product in products:
            found.add(str(product.id))
            quantity = self.items[str(product.id)]
            unit_price = product.discounted_price
            yield {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": unit_price * quantity,
            }

        # Products deleted by the admin: drop them, so the navbar count stays correct
        missing = self.items.keys() - found
        if missing:
            for pid in missing:
                del self.items[pid]
            self.save()

    def __len__(self):
        """Total number of items (2 phones + 1 case = 3)."""
        return sum(self.items.values())

    def total(self):
        return sum((item["line_total"] for item in self), Decimal("0.00"))

    def clear(self):
        """Empty the cart (used after checkout on Day 6)."""
        self.session.pop(CART_SESSION_KEY, None)
        self.session.modified = True

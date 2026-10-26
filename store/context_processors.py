from .cart import Cart


def cart(request):
    """Add the cart item count to every template."""
    return {"cart_count": len(Cart(request))}

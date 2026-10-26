from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from store.cart import Cart

from .forms import CheckoutForm
from .models import Order
from .services import OutOfStockError, create_order


@login_required
def checkout(request):
    cart = Cart(request)
    items = list(cart)
    if not items:
        messages.info(request, "Your cart is empty.")
        return redirect("store:cart_detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = create_order(request.user, cart, form.cleaned_data)
            except OutOfStockError as error:
                messages.error(request, str(error))
                return redirect("store:cart_detail")
            cart.clear()
            messages.success(request, f"Order #{order.id} placed! Pay cash on delivery.")
            return redirect(order.get_absolute_url())
    else:
        # Pre-fill the name from the user's account if available
        form = CheckoutForm(initial={"full_name": request.user.get_full_name()})

    total = sum((item["line_total"] for item in items), Decimal("0.00"))
    return render(request, "orders/checkout.html", {"form": form, "items": items, "total": total})


@login_required
def order_detail(request, order_id):
    # user=request.user is the IDOR protection: someone else's order gives a 404
    order = get_object_or_404(Order.objects.prefetch_related("items"), id=order_id, user=request.user)
    return render(request, "orders/order_detail.html", {"order": order})

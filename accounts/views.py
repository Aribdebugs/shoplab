from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from .forms import SignUpForm


def signup(request):
    # Already logged in? No need to sign up again.
    if request.user.is_authenticated:
        return redirect("store:product_list")

    if request.method == "POST":
        # The user submitted the form: validate their data
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()          # creates the user with a hashed password
            login(request, user)        # log them in straight away
            messages.success(request, f"Welcome to ShopLab, {user.username}!")
            return redirect("store:product_list")
    else:
        # First visit: show an empty form
        form = SignUpForm()

    # Reached on first visit OR when the form had errors (errors show in the template)
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def account(request):
    """Only logged-in users can see this. Others are redirected to the login page."""
    # item_count = total quantity per order, counted by the database in the same query
    # (calling order.items.count in the template would run one query per order)
    orders = request.user.orders.annotate(item_count=Sum("items__quantity"))   # related_name="orders"
    return render(request, "accounts/account.html", {"orders": orders})

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
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
    return render(request, "accounts/account.html")

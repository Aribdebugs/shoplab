from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from orders.models import Order, OrderItem

from .cart import Cart
from .forms import ReviewForm
from .models import Category, Product

PRODUCTS_PER_PAGE = 12

# Allowlist: URL value → database ordering. User input never reaches order_by() directly.
SORT_OPTIONS = {
    "name": "title",
    "price_asc": "sale_price",
    "price_desc": "-sale_price",
    "rating": "-rating",
}
DEFAULT_SORT = "name"


def product_list(request):
    """Home page: products with search, category filter, sorting and pagination."""
    # sale_price = what the shopper actually pays, so sorting matches the prices shown on the cards
    products = Product.objects.select_related("category").annotate(
        sale_price=ExpressionWrapper(
            F("price") * (100 - F("discount_percentage")) / 100,
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    )

    # Read filters from the URL, e.g. /?q=phone&category=smartphones&sort=price_asc
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "")
    sort = request.GET.get("sort", DEFAULT_SORT)
    if sort not in SORT_OPTIONS:
        sort = DEFAULT_SORT
    active_category = None

    # Search: match the text in title OR brand OR description
    if query:
        products = products.filter(
            Q(title__icontains=query)
            | Q(brand__icontains=query)
            | Q(description__icontains=query)
        )

    # Category filter: a wrong slug gives a 404, not a crash
    if category_slug:
        active_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=active_category)

    # "id" breaks ties (e.g. equal prices), so no product appears on two pages
    products = products.order_by(SORT_OPTIONS[sort], "id")

    # Sidebar: every category with how many products it has (one query, using COUNT)
    categories = Category.objects.annotate(product_count=Count("products"))

    # Pagination: get_page() safely handles ?page=abc or ?page=999
    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "store/product_list.html", {
        "page_obj": page_obj,
        "categories": categories,
        "query": query,
        "active_category": active_category,
        "sort": sort,
        "total": paginator.count,
    })


def _has_purchased(user, product):
    """True if the user has a non-cancelled order containing this product."""
    if not user.is_authenticated:
        return False
    return (
        OrderItem.objects
        .filter(order__user=user, product=product)
        .exclude(order__status=Order.Status.CANCELLED)
        .exists()
    )


def product_detail(request, slug):
    """One product page with its reviews."""
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)
    reviews = product.reviews.all()

    already_reviewed = (
        request.user.is_authenticated
        and reviews.filter(user=request.user).exists()
    )
    can_review = not already_reviewed and _has_purchased(request.user, product)

    return render(request, "store/product_detail.html", {
        "product": product,
        "reviews": reviews,
        "can_review": can_review,
        "already_reviewed": already_reviewed,
        "review_form": ReviewForm() if can_review else None,
    })


@login_required
@require_POST
def add_review(request, slug):
    product = get_object_or_404(Product, slug=slug)

    if not _has_purchased(request.user, product):
        messages.error(request, "Only customers who bought this product can review it.")
        return redirect(product.get_absolute_url())

    if product.reviews.filter(user=request.user).exists():
        messages.error(request, "You've already reviewed this product.")
        return redirect(product.get_absolute_url())

    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please choose a rating and write a comment.")
        return redirect(product.get_absolute_url())

    review = form.save(commit=False)   # build the object but don't save it yet
    review.product = product
    review.user = request.user
    review.reviewer_name = request.user.username
    try:
        # atomic: if the database rejects the row, only this block is undone
        with transaction.atomic():
            review.save()
    except IntegrityError:
        # A double-click got past the check above; the database constraint stopped the duplicate
        messages.error(request, "You've already reviewed this product.")
        return redirect(product.get_absolute_url())

    # The database calculates the new average in one query
    avg = product.reviews.aggregate(Avg("rating"))["rating__avg"]
    product.rating = Decimal(str(round(avg, 2)))
    product.save(update_fields=["rating"])   # saves ONLY that column

    messages.success(request, "Thanks for your review!")
    return redirect(product.get_absolute_url())


def _read_quantity(request, default=1):
    """Safely read a quantity from the submitted form. Bad input becomes the default."""
    try:
        return int(request.POST.get("quantity", default))
    except (TypeError, ValueError):
        return default


def cart_detail(request):
    cart = Cart(request)
    items = list(cart)   # run the database query ONCE, reuse for the list and the total
    total = sum((item["line_total"] for item in items), Decimal("0.00"))
    return render(request, "store/cart.html", {"items": items, "total": total})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not product.in_stock:
        messages.error(request, f"Sorry, {product.title} is out of stock.")
        return redirect(product.get_absolute_url())

    quantity = max(1, _read_quantity(request))   # at least 1
    Cart(request).add(product, quantity)
    messages.success(request, f"Added {product.title} to your cart.")
    return redirect("store:cart_detail")


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Cart(request).add(product, _read_quantity(request), override=True)   # 0 removes it
    return redirect("store:cart_detail")


@require_POST
def cart_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Cart(request).remove(product)
    messages.info(request, f"Removed {product.title} from your cart.")
    return redirect("store:cart_detail")

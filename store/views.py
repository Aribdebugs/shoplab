from django.shortcuts import get_object_or_404, render

from .models import Product


def product_list(request):
    """Home page: all products."""
    products = Product.objects.select_related("category")
    return render(request, "store/product_list.html", {"products": products})


def product_detail(request, slug):
    """One product page with its reviews."""
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)
    reviews = product.reviews.all()
    return render(request, "store/product_detail.html", {
        "product": product,
        "reviews": reviews,
    })

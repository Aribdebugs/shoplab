"""Import products, categories and reviews from DummyJSON into the database."""

import json
from datetime import datetime
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from store.models import Category, Product, Review

API_URL = "https://dummyjson.com/products?limit=0"   # limit=0 returns all products


class Command(BaseCommand):
    help = "Import products from DummyJSON"

    def handle(self, *args, **options):
        self.stdout.write("Downloading products...")
        # DummyJSON blocks Python's default User-Agent with 403 Forbidden, so send our own
        request = Request(API_URL, headers={"User-Agent": "shoplab-importer/1.0"})
        with urlopen(request, timeout=30) as response:
            data = json.load(response)

        products = data["products"]
        created_count = 0

        # transaction.atomic = all-or-nothing. If anything fails halfway,
        # the database is left unchanged instead of half-imported.
        with transaction.atomic():
            for item in products:
                category, _ = Category.objects.get_or_create(
                    slug=slugify(item["category"]),
                    defaults={"name": item["category"].replace("-", " ").title()},
                )

                # update_or_create: running the command twice updates
                # existing products instead of creating duplicates.
                product, created = Product.objects.update_or_create(
                    external_id=item["id"],
                    defaults={
                        "title": item["title"],
                        "slug": f"{slugify(item['title'])}-{item['id']}",
                        "description": item["description"],
                        "category": category,
                        "brand": item.get("brand", ""),   # some products have no brand
                        "price": item["price"],
                        "discount_percentage": item.get("discountPercentage", 0),
                        "rating": item.get("rating", 0),
                        "stock": item.get("stock", 0),
                        "thumbnail": item.get("thumbnail", ""),
                    },
                )
                created_count += created

                # Replace imported reviews (reviews from real users have a user set, so they're kept)
                product.reviews.filter(user__isnull=True).delete()
                for r in item.get("reviews", []):
                    Review.objects.create(
                        product=product,
                        reviewer_name=r["reviewerName"],
                        rating=r["rating"],
                        comment=r["comment"],
                        created_at=datetime.fromisoformat(r["date"].replace("Z", "+00:00")),
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {len(products)} products processed ({created_count} new)."
        ))

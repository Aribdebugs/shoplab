from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Category, Product, Review


class StockStatusFilter(admin.SimpleListFilter):
    title = "stock status"
    parameter_name = "stock_status"

    def lookups(self, request, model_admin):
        return [("out", "Out of stock"), ("low", "Low (1–10)"), ("in", "In stock")]

    def queryset(self, request, queryset):
        if self.value() == "out":
            return queryset.filter(stock=0)
        if self.value() == "low":
            return queryset.filter(stock__range=(1, 10))
        if self.value() == "in":
            return queryset.filter(stock__gt=0)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "product_count"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}   # auto-fills slug as you type the name

    def get_queryset(self, request):
        # Count products in the same query instead of one query per row
        return super().get_queryset(request).annotate(_product_count=Count("products"))

    @admin.display(description="products", ordering="_product_count")
    def product_count(self, obj):
        return obj._product_count


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    fields = ["reviewer_name", "rating", "comment", "created_at"]
    show_change_link = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["thumbnail_preview", "title", "category", "brand", "price", "stock", "rating"]
    list_display_links = ["thumbnail_preview", "title"]
    list_filter = ["category", StockStatusFilter]
    list_editable = ["price", "stock"]   # edit directly in the list view
    list_select_related = ["category"]
    list_per_page = 50
    search_fields = ["title", "brand", "category__name"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["category"]
    readonly_fields = ["thumbnail_preview", "created_at", "updated_at"]
    date_hierarchy = "created_at"
    inlines = [ReviewInline]
    fieldsets = [
        (None, {"fields": ["title", "slug", "category", "brand", "description"]}),
        ("Pricing & stock", {"fields": ["price", "discount_percentage", "stock", "rating"]}),
        ("Image", {"fields": ["thumbnail", "thumbnail_preview"]}),
        ("Metadata", {"fields": ["external_id", "created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    @admin.display(description="image")
    def thumbnail_preview(self, obj):
        if not obj.thumbnail:
            return "—"
        return format_html('<img src="{}" alt="" style="height:48px;border-radius:4px">', obj.thumbnail)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "reviewer_name", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
    list_select_related = ["product"]
    search_fields = ["reviewer_name", "comment", "product__title"]
    autocomplete_fields = ["product", "user"]
    date_hierarchy = "created_at"

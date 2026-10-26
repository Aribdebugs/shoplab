from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0   # don't show empty rows for adding items
    readonly_fields = ["product", "product_title", "unit_price", "quantity", "line_total"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False   # items come only from checkout


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "city", "total", "status", "created_at"]
    list_filter = ["status", "city", "created_at"]
    list_editable = ["status"]    # change status straight from the list
    list_select_related = ["user"]
    search_fields = ["=id", "full_name", "phone"]   # "=id": exact match, so "1" doesn't find 10, 11...
    readonly_fields = ["user", "total", "exchange_rate", "payment_method", "created_at"]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]

    def has_add_permission(self, request):
        return False   # orders are created by checkout, never by hand (total would be missing)

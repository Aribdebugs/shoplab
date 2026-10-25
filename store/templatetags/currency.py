from decimal import Decimal

from django import template

from store.currency import get_usd_to_bdt

register = template.Library()


@register.filter
def bdt(usd):
    """Show a USD amount in taka, e.g. {{ product.price|bdt }} → ৳3,588. Falls back to $ if no rate."""
    rate = get_usd_to_bdt()
    if rate is None:
        return f"${Decimal(usd):,.2f}"
    return f"৳{Decimal(usd) * rate:,.0f}"


@register.simple_tag
def usd_to_bdt_rate():
    """The current rate, for showing on the page; None if unavailable."""
    return get_usd_to_bdt()

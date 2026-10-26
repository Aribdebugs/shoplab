from decimal import Decimal

from django import template

from store.currency import get_usd_to_bdt

register = template.Library()


def _format(usd, rate):
    """৳ at the given rate, or $ if there is no rate. Shared by both filters so they always match."""
    if rate is None:
        return f"${Decimal(usd):,.2f}"
    return f"৳{Decimal(usd) * Decimal(rate):,.0f}"


@register.filter
def bdt(usd):
    """Show a USD amount in taka at today's rate, e.g. {{ product.price|bdt }} → ৳3,588.
    For the shop and cart, where prices aren't records yet."""
    return _format(usd, get_usd_to_bdt())


@register.filter
def bdt_at(usd, rate):
    """Convert using a fixed (snapshotted) rate, e.g. {{ order.total|bdt_at:order.exchange_rate }}.
    For orders, so their taka amounts never change. Falls back to USD if no rate was saved."""
    return _format(usd, rate)


@register.simple_tag
def usd_to_bdt_rate():
    """The current rate, for showing on the page; None if unavailable."""
    return get_usd_to_bdt()

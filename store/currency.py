"""Live USD → BDT exchange rate, cached so the API is called at most a few times a day."""

import json
import logging
from decimal import Decimal
from urllib.request import Request, urlopen

from django.core.cache import cache

RATE_URL = "https://open.er-api.com/v6/latest/USD"   # free, no API key, updates daily
CACHE_KEY = "usd_to_bdt_rate"
CACHE_SECONDS = 6 * 60 * 60     # keep a good rate for 6 hours
RETRY_SECONDS = 5 * 60          # after a failure, wait 5 minutes before trying again

logger = logging.getLogger(__name__)


def get_usd_to_bdt():
    """Return how many taka one US dollar buys, or None if the rate is unavailable."""
    rate = cache.get(CACHE_KEY)
    if rate is None:
        try:
            request = Request(RATE_URL, headers={"User-Agent": "shoplab/1.0"})
            with urlopen(request, timeout=5) as response:
                rate = Decimal(str(json.load(response)["rates"]["BDT"]))
            cache.set(CACHE_KEY, rate, CACHE_SECONDS)
        except (OSError, ValueError, KeyError) as exc:   # network error, bad JSON, missing rate
            logger.warning("Could not fetch USD→BDT rate: %s", exc)
            rate = 0   # cache the failure, so a page with 194 prices doesn't retry 194 times
            cache.set(CACHE_KEY, rate, RETRY_SECONDS)
    return rate or None

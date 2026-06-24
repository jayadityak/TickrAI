"""Kalshi prediction market data source.

Fetches live prediction market probabilities from Kalshi's regulated trading API.
Provides two signals for TickrAI:
  1. Per-stock earnings beat probability — shown in Analyst Consensus card
  2. Macro market signals (Fed, recession, CPI) — shown on landing page

Auth: API key via "Authorization: Key {api_key}" header.
Cache: earnings markets 30 min, macro markets 15 min.
Gracefully returns None / [] on any failure so callers can silently skip.
"""

import asyncio
import logging
import time

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"

_semaphore = asyncio.Semaphore(2)
_cache: dict[str, tuple[float, dict | list]] = {}

_EARNINGS_TTL = 1800  # 30 minutes — earnings markets move slowly
_MACRO_TTL = 900      # 15 minutes — macro markets update more frequently

# Known Kalshi series tickers for macro markets.
# (series_ticker, display_label) — verified once API keys are active.
_MACRO_SERIES = [
    ("KXFED", "Fed Rate Cut"),
    ("KXREC", "US Recession 2025"),
    ("KXCPI", "CPI Surprise"),
]


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Key {settings.kalshi_api_key}"}


async def _get(path: str, params: dict | None = None, ttl: float = _EARNINGS_TTL) -> dict | list:
    """Fetch from Kalshi API with caching and graceful error handling."""
    cache_key = f"{path}:{sorted((params or {}).items())}"

    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if time.time() - ts < ttl:
            return data

    async with _semaphore:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE_URL}/{path.lstrip('/')}",
                    params=params or {},
                    headers=_auth_headers(),
                )

            if resp.status_code == 401:
                logger.warning("Kalshi: invalid or missing API key (401)")
                return {}
            if resp.status_code == 429:
                logger.warning("Kalshi: rate limited (429)")
                return _cache.get(cache_key, (0, {}))[1]
            if resp.status_code != 200:
                logger.debug("Kalshi %s → %d", path, resp.status_code)
                return {}

            data = resp.json()
            _cache[cache_key] = (time.time(), data)
            return data

        except Exception as exc:
            logger.debug("Kalshi fetch error for %s: %s", path, exc)
            # Serve stale cache rather than empty on transient errors
            if cache_key in _cache:
                return _cache[cache_key][1]
            return {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mid_probability(market: dict) -> int | None:
    """Convert Kalshi market prices (0–100 cents) to an integer probability %."""
    yes_ask = market.get("yes_ask")
    yes_bid = market.get("yes_bid")
    last_price = market.get("last_price")

    if yes_ask is not None and yes_bid is not None and yes_ask > 0 and yes_bid > 0:
        return round((yes_ask + yes_bid) / 2)
    if last_price is not None and last_price > 0:
        return round(last_price)
    return None


def _format_market(market: dict, label: str | None = None) -> dict | None:
    """Return a normalised market dict or None if probability is unavailable."""
    prob = _mid_probability(market)
    if prob is None:
        return None

    ticker = market.get("ticker", "")
    return {
        "probability": prob,
        "title": label or market.get("title") or market.get("subtitle") or "Market",
        "close_time": market.get("close_time") or market.get("expiration_time"),
        "volume": market.get("volume") or market.get("volume_24h"),
        "url": f"https://kalshi.com/markets/{ticker}" if ticker else "https://kalshi.com",
    }


async def _fetch_event_market(series_ticker: str, label: str | None = None) -> dict | None:
    """Fetch the most recent open market for a given Kalshi series."""
    ev_data = await _get("events", {
        "series_ticker": series_ticker,
        "status": "open",
        "limit": 1,
    }, ttl=_MACRO_TTL)

    events = ev_data.get("events", []) if isinstance(ev_data, dict) else []
    if not events:
        return None

    event_ticker = events[0].get("event_ticker", "")
    event_title = events[0].get("title")

    mkt_data = await _get("markets", {
        "event_ticker": event_ticker,
        "status": "open",
        "limit": 1,
    }, ttl=_MACRO_TTL)

    markets = mkt_data.get("markets", []) if isinstance(mkt_data, dict) else []
    if not markets:
        return None

    return _format_market(markets[0], label=label or event_title)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_earnings_market(ticker: str) -> dict | None:
    """Return the Kalshi earnings beat probability for a stock ticker.

    Returns a dict with keys: probability, title, close_time, volume, url.
    Returns None if no open earnings market exists for this ticker (most small-caps).
    """
    upper = ticker.upper()

    # Primary: look for a dedicated earnings series (e.g. KXEARN-AAPL)
    result = await _fetch_event_market(f"KXEARN-{upper}")
    if result:
        return result

    # Fallback: scan recent open markets for any mentioning this ticker + earnings
    mkt_data = await _get("markets", {
        "status": "open",
        "limit": 50,
    }, ttl=_EARNINGS_TTL)
    markets = mkt_data.get("markets", []) if isinstance(mkt_data, dict) else []

    for m in markets:
        title = (m.get("title") or "").upper()
        subtitle = (m.get("subtitle") or "").upper()
        combined = title + " " + subtitle
        if upper in combined and any(kw in combined for kw in ("EARN", "EPS", "BEAT", "REVENUE")):
            return _format_market(m)

    return None


async def get_macro_markets() -> list[dict]:
    """Return live macro market probabilities (Fed, recession, CPI, etc.)

    Always returns a list; empty list means no markets found or API unavailable.
    """
    results: list[dict] = []
    for series_ticker, label in _MACRO_SERIES:
        market = await _fetch_event_market(series_ticker, label=label)
        if market:
            market["label"] = label
            results.append(market)
    return results

"""Live market index quotes (S&P 500, NASDAQ, DOW).

Uses Yahoo Finance via yfinance. Cached for 5 minutes to avoid
excessive API calls.
"""

import logging
import time
from functools import lru_cache

import yfinance as yf
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

INDICES = [
    {"symbol": "^GSPC", "name": "S&P 500"},
    {"symbol": "^IXIC", "name": "NASDAQ"},
    {"symbol": "^DJI", "name": "DOW"},
]

# Simple time-based cache
_cache: dict[str, any] = {"data": None, "timestamp": 0}
_CACHE_TTL = 300  # 5 minutes


def _fetch_indices() -> list[dict]:
    """Fetch index quotes from Yahoo Finance."""
    now = time.time()
    if _cache["data"] and (now - _cache["timestamp"]) < _CACHE_TTL:
        return _cache["data"]

    results = []
    for idx in INDICES:
        try:
            ticker = yf.Ticker(idx["symbol"])
            info = ticker.fast_info
            price = info.last_price
            prev_close = info.previous_close
            change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0

            results.append({
                "name": idx["name"],
                "value": f"{price:,.2f}",
                "change": f"{'+' if change_pct >= 0 else ''}{change_pct:.2f}%",
                "positive": change_pct >= 0,
            })
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", idx["symbol"], e)
            results.append({
                "name": idx["name"],
                "value": "—",
                "change": "—",
                "positive": True,
            })

    _cache["data"] = results
    _cache["timestamp"] = now
    return results


@router.get("/api/market/indices")
async def get_market_indices():
    """Return current index quotes. Cached for 5 minutes."""
    return _fetch_indices()

"""Trending stocks — tracks which tickers users research most.

Blends real user research counts with live market movers (FMP most-actives)
so the landing page always shows recognisable names even with low traffic.
Market movers are cached for 30 minutes to avoid hammering the API.
"""

import logging
import time
from collections import defaultdict

import httpx
from fastapi import APIRouter

from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory counter: ticker -> list of timestamps
_research_log: dict[str, list[float]] = defaultdict(list)
_total_reports = 0

# Cache for market movers: (fetched_at, list_of_(ticker, base_weight))
_movers_cache: tuple[float, list[tuple[str, int]]] | None = None
_MOVERS_TTL = 1800  # 30 minutes

# FMP base URL — keep in sync with fmp.py
_FMP_BASE = "https://financialmodelingprep.com/stable"

# Fallback well-known tickers used only when FMP is unavailable
_FALLBACK_MOVERS = [
    ("NVDA", 20), ("TSLA", 18), ("AAPL", 16), ("MSFT", 14), ("AMZN", 12),
    ("META", 10), ("GOOGL", 9), ("AMD", 8), ("NFLX", 7), ("JPM", 6),
]


async def _get_market_movers() -> list[tuple[str, int]]:
    """Return (ticker, base_weight) pairs for today's most active stocks.

    Fetches from FMP every 30 min; falls back to a static list on failure.
    """
    global _movers_cache

    now = time.time()
    if _movers_cache and now - _movers_cache[0] < _MOVERS_TTL:
        return _movers_cache[1]

    if not settings.fmp_api_key:
        return _FALLBACK_MOVERS

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                f"{_FMP_BASE}/most-actives",
                params={"apikey": settings.fmp_api_key},
            )
            if resp.status_code != 200:
                raise ValueError(f"FMP returned {resp.status_code}")

            data = resp.json()
            if not isinstance(data, list) or not data:
                raise ValueError("empty response")

            movers: list[tuple[str, int]] = []
            for i, item in enumerate(data[:10]):
                sym = item.get("symbol", "")
                # Skip tickers with dots (BRK.B) — they look odd in the UI
                if sym and "." not in sym:
                    # Descending weights: #1 gets 20, #10 gets 2
                    movers.append((sym, max(2, 20 - i * 2)))

            if movers:
                _movers_cache = (now, movers)
                return movers

    except Exception as exc:
        logger.debug("market movers fetch failed: %s", exc)

    # Return stale cache if available, else fallback
    if _movers_cache:
        return _movers_cache[1]
    return _FALLBACK_MOVERS


def log_research(ticker: str):
    """Call this when a report is generated to track trending."""
    global _total_reports
    _research_log[ticker.upper()].append(time.time())
    _total_reports += 1


@router.get("/api/trending")
async def get_trending():
    """Return top 10 most-researched tickers in the last 24 hours.

    Blends real user research counts with live market movers so the list
    always shows recognisable names regardless of how much user traffic
    the site has seen today.
    """
    cutoff = time.time() - 86400  # 24 hours ago
    counts: dict[str, int] = {}

    # Real user research activity
    for ticker, timestamps in _research_log.items():
        recent = [t for t in timestamps if t > cutoff]
        if recent:
            counts[ticker] = len(recent)

    # Blend in market movers as a baseline — user searches stack on top
    market_movers = await _get_market_movers()
    for ticker, weight in market_movers:
        counts[ticker] = counts.get(ticker, 0) + weight

    # Sort by combined score descending, take top 10
    top = sorted(counts.items(), key=lambda x: -x[1])[:10]

    return {
        "trending": [{"ticker": t, "count": c} for t, c in top],
        "total_reports_generated": _total_reports,
    }

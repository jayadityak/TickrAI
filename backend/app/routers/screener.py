"""Stock Discovery Screener.

Filters a curated small/mid-cap universe by sector and market cap tier,
then fetches live yfinance data ONLY for the paginated slice (max 20),
running those fetches in parallel via asyncio + run_in_executor.

No auth required — this is a discovery/acquisition channel.
Cache: 24 hours per ticker.
"""

import asyncio
import logging
import math
import time
from typing import Optional

import yfinance as yf
from fastapi import APIRouter

from ..data_sources.small_cap_universe import UNIVERSE

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache: ticker -> (timestamp, data_dict)
_screen_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 86400  # 24 hours


def _sf(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _fetch_one(ticker: str) -> dict | None:
    """Synchronous yfinance fetch for a single ticker. Runs in thread pool.

    Returns None if the ticker is not found or yfinance returns no useful data,
    so the caller can skip it rather than showing a blank card.
    """
    now = time.time()
    if ticker in _screen_cache:
        ts, data = _screen_cache[ticker]
        if now - ts < _CACHE_TTL:
            return data

    try:
        t = yf.Ticker(ticker)
        raw = t.info
        # yfinance can return a list for ambiguous/delisted tickers — treat as missing
        info = raw if isinstance(raw, dict) and raw else {}

        # Guard: if yfinance has no name for this ticker, it doesn't exist / was renamed
        if not info or not info.get("shortName"):
            logger.debug("Screener: ticker %s not found in yfinance (no shortName)", ticker)
            return None

        fast = t.fast_info

        price = _sf(getattr(fast, "last_price", None)) or _sf(info.get("currentPrice"))
        prev  = _sf(getattr(fast, "previous_close", None))
        change_pct = round((price / prev - 1) * 100, 2) if (price and prev and prev > 0) else None
        market_cap = info.get("marketCap")
        n_analysts = info.get("numberOfAnalystOpinions")

        data = {
            "price":      round(price, 2) if price else None,
            "change_pct": change_pct,
            "positive":   (change_pct or 0) >= 0,
            "market_cap": market_cap,
            "n_analysts": int(n_analysts) if n_analysts is not None else None,
        }
        # Only cache successful fetches (non-empty info)
        _screen_cache[ticker] = (now, data)
        return data
    except Exception as e:
        logger.debug("Screener fetch failed for %s: %s", ticker, e)
        # Don't cache failures — let the next request retry
        return None


def _fmt_market_cap(cap: int | float | None) -> str:
    if cap is None:
        return "N/A"
    if cap >= 1e12:
        return f"${cap / 1e12:.1f}T"
    if cap >= 1e9:
        return f"${cap / 1e9:.1f}B"
    if cap >= 1e6:
        return f"${cap / 1e6:.0f}M"
    return f"${cap:,.0f}"


@router.get("/api/screen")
async def screen_stocks(
    sector: Optional[str] = "",
    cap_tier: Optional[str] = "",
    offset: int = 0,
    limit: int = 20,
):
    """Return undercovered stocks from the universe, paginated.

    Static filtering (sector, cap_tier) is instant.
    Live yfinance data fetched in parallel ONLY for the page slice.
    This ensures the endpoint always returns quickly.
    """
    limit = min(limit, 40)

    # Step 1: filter by static fields only — no API calls yet
    candidates = UNIVERSE
    if sector:
        candidates = [u for u in candidates if u["sector"].lower() == sector.lower()]
    if cap_tier:
        candidates = [u for u in candidates if u["cap_tier"] == cap_tier.lower()]

    # Sort: micro first (most likely undercovered), then small, then mid
    tier_order = {"micro": 0, "small": 1, "mid": 2}
    candidates = sorted(candidates, key=lambda u: tier_order.get(u["cap_tier"], 9))

    total = len(candidates)
    page_items = candidates[offset: offset + limit]

    if not page_items:
        return {"total": total, "offset": offset, "limit": limit, "results": []}

    # Step 2: fetch live data for ONLY the page slice, in parallel
    loop = asyncio.get_event_loop()
    live_tasks = [
        loop.run_in_executor(None, _fetch_one, item["ticker"])
        for item in page_items
    ]
    live_results = await asyncio.gather(*live_tasks)

    results = []
    for item, live in zip(page_items, live_results):
        # Skip tickers that yfinance couldn't resolve (renamed, delisted, OTC-only)
        if live is None:
            continue
        results.append({
            "ticker":     item["ticker"],
            "name":       item["name"],
            "sector":     item["sector"],
            "cap_tier":   item["cap_tier"],
            "price":      live["price"],
            "change_pct": live["change_pct"],
            "positive":   live["positive"],
            "market_cap": _fmt_market_cap(live["market_cap"]),
            "n_analysts": live["n_analysts"],
        })

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": results,
    }


@router.get("/api/screen/sectors")
async def list_sectors():
    """Return unique sectors in the discovery universe."""
    sectors = sorted({u["sector"] for u in UNIVERSE})
    return {"sectors": sectors}

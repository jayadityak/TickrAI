"""Stock Discovery Screener.

Filters a curated small/mid-cap universe by sector and market cap tier,
then fetches live yfinance data ONLY for the paginated slice (max 20),
running those fetches in parallel via asyncio + run_in_executor.

Each result includes a proprietary Discovery Score (0–100) combining:
  - Analyst coverage gap (fewer analysts = more undiscovered)
  - Analyst upside potential (% to consensus price target)
  - 52-week range position (recovering from lows vs. at peak)
  - Quality signals (ROE, debt-to-equity)
  - Value signal (trailing P/E)

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


def _compute_discovery_score(
    n_analysts: int | None,
    analyst_upside_pct: float | None,
    range_position: float | None,   # 0=at 52w low, 1=at 52w high
    return_on_equity: float | None,
    debt_to_equity: float | None,
    trailing_pe: float | None,
) -> int:
    """Proprietary Discovery Score 0–100.

    Rewards:
    - Undercovered stocks (few/no analysts)
    - High analyst upside to price target
    - Price recovering from 52-week lows (not at peak)
    - Strong return on equity + manageable debt
    - Reasonable valuation (P/E)
    """
    score = 0

    # 1. Coverage gap (30 pts) — fewer analysts = more discovery opportunity
    n = n_analysts or 0
    if n == 0:
        score += 30
    elif n <= 2:
        score += 22
    elif n <= 5:
        score += 12
    elif n <= 10:
        score += 5

    # 2. Analyst upside to price target (25 pts)
    upside = analyst_upside_pct or 0
    if upside > 40:
        score += 25
    elif upside > 25:
        score += 20
    elif upside > 15:
        score += 13
    elif upside > 5:
        score += 7

    # 3. 52-week range position (20 pts)
    # Sweet spot: price in 5–40% of annual range = recovering from lows
    if range_position is not None:
        if 0.05 <= range_position <= 0.40:
            score += 20   # recovering from lows — best setup
        elif 0.40 < range_position <= 0.60:
            score += 14   # mid-range
        elif range_position < 0.05:
            score += 8    # near 52w low — value or falling knife
        elif 0.60 < range_position <= 0.80:
            score += 7
        else:
            score += 3    # near 52w high

    # 4. Quality signals (15 pts)
    roe = return_on_equity or 0
    dte = debt_to_equity if debt_to_equity is not None else 999
    if roe > 0.15:
        score += 8
    elif roe > 0.05:
        score += 5
    elif roe > 0:
        score += 2

    if dte < 0.5:
        score += 7
    elif dte < 1.0:
        score += 4
    elif dte < 2.0:
        score += 2

    # 5. Value signal (10 pts)
    pe = trailing_pe or 0
    if 0 < pe < 15:
        score += 10
    elif 0 < pe < 25:
        score += 7
    elif 0 < pe < 40:
        score += 3

    return min(100, max(0, score))


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

        # --- New: enriched fields ---
        target_mean = _sf(info.get("targetMeanPrice"))
        rec_key = info.get("recommendationKey") or ""  # "buy", "hold", "sell", "strong_buy" etc.
        week52_high = _sf(info.get("fiftyTwoWeekHigh"))
        week52_low  = _sf(info.get("fiftyTwoWeekLow"))
        trailing_pe = _sf(info.get("trailingPE"))
        roe = _sf(info.get("returnOnEquity"))
        dte = _sf(info.get("debtToEquity"))
        # yfinance returns D/E as a percentage (e.g. 150 means 1.5x) — normalise
        if dte is not None:
            dte = dte / 100.0

        # Derived
        analyst_upside_pct: float | None = None
        if target_mean and price and price > 0:
            analyst_upside_pct = round((target_mean / price - 1) * 100, 1)

        range_position: float | None = None
        if week52_high and week52_low and week52_high != week52_low and price:
            range_position = round((price - week52_low) / (week52_high - week52_low), 3)

        discovery_score = _compute_discovery_score(
            n_analysts=int(n_analysts) if n_analysts is not None else None,
            analyst_upside_pct=analyst_upside_pct,
            range_position=range_position,
            return_on_equity=roe,
            debt_to_equity=dte,
            trailing_pe=trailing_pe,
        )

        data = {
            "price":               round(price, 2) if price else None,
            "change_pct":          change_pct,
            "positive":            (change_pct or 0) >= 0,
            "market_cap":          market_cap,
            "n_analysts":          int(n_analysts) if n_analysts is not None else None,
            "analyst_upside_pct":  analyst_upside_pct,
            "recommendation_key":  rec_key,
            "week52_high":         week52_high,
            "week52_low":          week52_low,
            "range_position":      range_position,
            "trailing_pe":         round(trailing_pe, 1) if trailing_pe else None,
            "return_on_equity":    round(roe * 100, 1) if roe is not None else None,  # as %
            "discovery_score":     discovery_score,
        }
        # Only cache successful fetches
        _screen_cache[ticker] = (now, data)
        return data
    except Exception as e:
        logger.debug("Screener fetch failed for %s: %s", ticker, e)
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
    sort_by: Optional[str] = "discovery_score",
):
    """Return undercovered stocks from the universe, paginated.

    Static filtering (sector, cap_tier) is instant.
    Live yfinance data fetched in parallel ONLY for the page slice.

    sort_by options: discovery_score (default), analyst_upside, change_pct, market_cap
    """
    limit = min(limit, 40)

    # Step 1: filter by static fields only — no API calls yet
    candidates = list(UNIVERSE)
    if sector:
        candidates = [u for u in candidates if u["sector"].lower() == sector.lower()]
    if cap_tier:
        candidates = [u for u in candidates if u["cap_tier"] == cap_tier.lower()]

    # Default pre-sort: micro first (most undercovered), then small, then mid
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
        if live is None:
            continue
        results.append({
            "ticker":              item["ticker"],
            "name":                item["name"],
            "sector":              item["sector"],
            "cap_tier":            item["cap_tier"],
            "price":               live["price"],
            "change_pct":          live["change_pct"],
            "positive":            live["positive"],
            "market_cap":          _fmt_market_cap(live["market_cap"]),
            "n_analysts":          live["n_analysts"],
            "analyst_upside_pct":  live["analyst_upside_pct"],
            "recommendation_key":  live["recommendation_key"],
            "week52_high":         live["week52_high"],
            "week52_low":          live["week52_low"],
            "range_position":      live["range_position"],
            "trailing_pe":         live["trailing_pe"],
            "return_on_equity":    live["return_on_equity"],
            "discovery_score":     live["discovery_score"],
        })

    # Step 3: client-requested sort (applied after live fetch)
    sort_key_map = {
        "discovery_score": lambda r: r["discovery_score"] or 0,
        "analyst_upside":  lambda r: r["analyst_upside_pct"] or -999,
        "change_pct":      lambda r: r["change_pct"] or 0,
        "market_cap":      lambda r: r.get("market_cap") or "N/A",  # already formatted
    }
    sort_fn = sort_key_map.get(sort_by or "discovery_score", sort_key_map["discovery_score"])
    # discovery_score and analyst_upside: descending. market_cap string sort not ideal but fine for now.
    reverse = sort_by != "market_cap"
    results.sort(key=sort_fn, reverse=reverse)

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

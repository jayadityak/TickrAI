"""Kalshi prediction market endpoints.

Exposes earnings beat probability for a stock and macro market signals.
All endpoints return gracefully empty responses when the Kalshi API key
is not set or when no market exists for the requested ticker.
"""

from fastapi import APIRouter

from ..config import settings
from ..data_sources.kalshi import get_earnings_market, get_macro_markets

router = APIRouter()


@router.get("/api/kalshi/earnings/{ticker}")
async def kalshi_earnings(ticker: str):
    """Return Kalshi earnings beat probability for a stock.

    Returns {"market": null} when no open market exists (most small-caps).
    """
    if not settings.kalshi_api_key:
        return {"market": None}
    market = await get_earnings_market(ticker.upper())
    return {"market": market}


@router.get("/api/kalshi/macro")
async def kalshi_macro():
    """Return live macro market signals (Fed, recession, CPI)."""
    if not settings.kalshi_api_key:
        return {"markets": []}
    markets = await get_macro_markets()
    return {"markets": markets}

"""Watchlist — users save tickers they want to track.

In-memory storage keyed by user Google ID. Will migrate to DB later.
Includes live price data from yfinance.
"""

import logging
import time
import math
from collections import defaultdict

import yfinance as yf
from fastapi import APIRouter, Depends

from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory watchlist: user_id -> set of tickers
_watchlists: dict[str, set[str]] = defaultdict(set)

# Price cache: ticker -> (timestamp, price_data)
_price_cache: dict[str, tuple[float, dict]] = {}
_PRICE_CACHE_TTL = 300  # 5 minutes


def _get_price(symbol: str) -> dict:
    """Get current price for a ticker, cached for 5 min."""
    now = time.time()
    if symbol in _price_cache:
        ts, data = _price_cache[symbol]
        if now - ts < _PRICE_CACHE_TTL:
            return data

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = info.last_price
        prev_close = info.previous_close
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        data = {
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "positive": change >= 0,
        }
        _price_cache[symbol] = (now, data)
        return data
    except Exception as e:
        logger.warning("Price fetch failed for %s: %s", symbol, e)
        return {"price": None, "change": None, "change_pct": None, "positive": True}


@router.get("/api/watchlist")
async def get_watchlist(user: dict = Depends(get_current_user)):
    """Get user's watchlist with live prices."""
    user_id = user["sub"]
    tickers = sorted(_watchlists.get(user_id, set()))

    items = []
    for t in tickers:
        price_data = _get_price(t)
        items.append({
            "ticker": t,
            **price_data,
        })

    return {"watchlist": items}


@router.post("/api/watchlist/{ticker}")
async def add_to_watchlist(ticker: str, user: dict = Depends(get_current_user)):
    """Add a ticker to the user's watchlist."""
    user_id = user["sub"]
    upper = ticker.upper()
    _watchlists[user_id].add(upper)
    return {"status": "added", "ticker": upper}


@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, user: dict = Depends(get_current_user)):
    """Remove a ticker from the user's watchlist."""
    user_id = user["sub"]
    upper = ticker.upper()
    _watchlists[user_id].discard(upper)
    return {"status": "removed", "ticker": upper}


@router.get("/api/watchlist/{ticker}/status")
async def check_watchlist_status(ticker: str, user: dict = Depends(get_current_user)):
    """Check if a ticker is in the user's watchlist."""
    user_id = user["sub"]
    return {"in_watchlist": ticker.upper() in _watchlists.get(user_id, set())}

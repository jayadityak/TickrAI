"""Congress/politician stock trading tracker.

Uses Quiver Quant free API for real-time Congress trading disclosures.
"""

import logging
import time

import httpx
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache the full dataset — refresh every 2 hours
_cache: dict[str, tuple[float, list]] = {"all": (0, [])}
_CACHE_TTL = 7200
_API_URL = "https://api.quiverquant.com/beta/live/congresstrading"


async def _fetch_all() -> tuple[list[dict], bool]:
    """Fetch all Congress trades, cached for 2 hours.

    Returns (trades, is_error) — is_error=True when Quiver is unreachable
    and there is no stale cache to fall back on.
    """
    now = time.time()
    ts, data = _cache["all"]
    if data and (now - ts) < _CACHE_TTL:
        return data, False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(_API_URL, headers={"Accept": "application/json"})
            r.raise_for_status()
            trades = r.json()
            _cache["all"] = (now, trades)
            return trades, False
    except Exception as e:
        logger.warning("Congress trading fetch failed: %s", e)
        # Return stale data if we have it; otherwise signal the error to the caller
        if data:
            return data, False
        return [], True


@router.get("/api/congress")
async def get_congress_trades(
    ticker: str | None = Query(None, description="Filter by ticker symbol"),
    limit: int = Query(20, description="Max results"),
):
    """Get recent Congress trades, optionally filtered by ticker."""
    all_trades, fetch_error = await _fetch_all()

    if ticker:
        filtered = [t for t in all_trades if t.get("Ticker", "").upper() == ticker.upper()]
    else:
        filtered = all_trades

    # Sort by transaction date descending
    filtered.sort(key=lambda x: x.get("TransactionDate", ""), reverse=True)
    trades = filtered[:limit]

    # Normalize the output
    results = []
    for t in trades:
        results.append({
            "representative": t.get("Representative", "Unknown"),
            "party": t.get("Party", ""),
            "house": t.get("House", ""),
            "ticker": t.get("Ticker", ""),
            "transaction": t.get("Transaction", ""),
            "amount_range": t.get("Range", ""),
            "transaction_date": t.get("TransactionDate", ""),
            "report_date": t.get("ReportDate", ""),
            "excess_return": round(t["ExcessReturn"], 2) if t.get("ExcessReturn") is not None else None,
        })

    return {
        "trades": results,
        "total": len(filtered),
        # Signal to the frontend that the data source is temporarily unavailable
        "error": "rate_limited" if fetch_error else None,
    }


@router.get("/api/congress/summary")
async def get_congress_summary():
    """Get summary stats for the landing page — most traded tickers by Congress."""
    all_trades, _ = await _fetch_all()

    # Count trades per ticker
    ticker_counts: dict[str, int] = {}
    buys: dict[str, int] = {}
    sells: dict[str, int] = {}

    for t in all_trades:
        sym = t.get("Ticker", "")
        if not sym or t.get("TickerType") != "Stock":
            continue
        ticker_counts[sym] = ticker_counts.get(sym, 0) + 1
        tx = t.get("Transaction", "").lower()
        if "purchase" in tx:
            buys[sym] = buys.get(sym, 0) + 1
        elif "sale" in tx:
            sells[sym] = sells.get(sym, 0) + 1

    # Top 10 most traded
    top = sorted(ticker_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "top_tickers": [
            {
                "ticker": sym,
                "total_trades": count,
                "buys": buys.get(sym, 0),
                "sells": sells.get(sym, 0),
            }
            for sym, count in top
        ],
        "total_trades": len(all_trades),
    }

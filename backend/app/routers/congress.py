"""Congress/politician stock trading tracker.

Uses Finnhub's free API (finnhub.io — no credit card, just email signup).
Endpoint: GET /api/v1/stock/congressional-trading?symbol=X&token=KEY

Cache: 12 hours per ticker (disclosures trickle in slowly).
If no Finnhub key is configured, the section shows a friendly notice.
"""

import logging
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Query

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_FINNHUB_BASE = "https://finnhub.io/api/v1"

# Per-ticker cache: {"AAPL": (timestamp, [trades])}
_ticker_cache: dict[str, tuple[float, list]] = {}
_ALL_CACHE: tuple[float, list] = (0, [])   # for the summary / no-ticker endpoint
_CACHE_TTL = 43200  # 12 hours


def _parse_date(s: str | None) -> str:
    if not s:
        return ""
    return s[:10]


def _normalise(raw: list[dict]) -> list[dict]:
    """Map Finnhub congressional-trading rows → internal schema."""
    rows = []
    cutoff = (datetime.utcnow() - timedelta(days=548)).strftime("%Y-%m-%d")
    for t in raw:
        tx_date = _parse_date(t.get("transactionDate"))
        if tx_date < cutoff:
            continue
        tx_type = (t.get("transaction") or "").lower()
        if "purchase" in tx_type or "buy" in tx_type:
            transaction = "Purchase"
        elif "sale" in tx_type or "sell" in tx_type:
            transaction = "Sale"
        else:
            transaction = (t.get("transaction") or "").title()

        rows.append({
            "representative":  t.get("name", "Unknown"),
            "party":           t.get("party", ""),
            "house":           t.get("chamber", ""),
            "ticker":          (t.get("symbol") or "").upper(),
            "transaction":     transaction,
            "amount_range":    t.get("amount") or t.get("amountRange") or "",
            "transaction_date":tx_date,
            "report_date":     _parse_date(t.get("filingDate") or t.get("reportDate")),
            "excess_return":   None,
        })
    return rows


async def _fetch_ticker(symbol: str) -> tuple[list[dict], bool]:
    """Fetch trades for a single ticker, with per-ticker cache."""
    now = time.time()
    cached_ts, cached_data = _ticker_cache.get(symbol, (0, []))
    if cached_data and (now - cached_ts) < _CACHE_TTL:
        return cached_data, False

    if not settings.finnhub_api_key:
        logger.debug("No Finnhub API key — congressional trades unavailable for %s", symbol)
        return cached_data, not bool(cached_data)

    # Fetch last 18 months
    date_from = (datetime.utcnow() - timedelta(days=548)).strftime("%Y-%m-%d")
    date_to   = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{_FINNHUB_BASE}/stock/congressional-trading",
                params={
                    "symbol": symbol,
                    "from":   date_from,
                    "to":     date_to,
                    "token":  settings.finnhub_api_key,
                },
            )
            if r.status_code == 401:
                logger.warning("Finnhub API key rejected (401)")
                return cached_data, not bool(cached_data)
            if r.status_code == 429:
                logger.warning("Finnhub rate limited")
                return cached_data, not bool(cached_data)
            r.raise_for_status()
            payload = r.json()
            trades_raw = payload.get("data") or (payload if isinstance(payload, list) else [])
            trades = _normalise(trades_raw)
            trades.sort(key=lambda x: x["transaction_date"], reverse=True)
            _ticker_cache[symbol] = (now, trades)
            return trades, False
    except Exception as e:
        logger.warning("Finnhub congress fetch failed for %s: %s", symbol, e)
        return cached_data, not bool(cached_data)


async def _fetch_all() -> tuple[list[dict], bool]:
    """Fetch recent trades across all tickers (for the summary endpoint).

    Finnhub doesn't have a bulk endpoint, so we fetch a curated list of
    the most commonly traded tickers by Congress members.
    """
    global _ALL_CACHE
    now = time.time()
    ts, cached = _ALL_CACHE
    if cached and (now - ts) < _CACHE_TTL:
        return cached, False

    # Most frequently traded tickers by Congress members historically
    top_tickers = [
        "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA",
        "JPM", "BAC", "GS", "V", "MA", "XOM", "CVX", "LMT",
        "RTX", "BA", "DIS", "NFLX", "AMD",
    ]

    import asyncio
    results = await asyncio.gather(
        *[_fetch_ticker(sym) for sym in top_tickers],
        return_exceptions=True,
    )

    combined = []
    for trades, _ in (r for r in results if not isinstance(r, Exception)):
        combined.extend(trades)

    combined.sort(key=lambda x: x["transaction_date"], reverse=True)
    _ALL_CACHE = (now, combined)
    return combined, False


@router.get("/api/congress")
async def get_congress_trades(
    ticker: str | None = Query(None),
    limit: int = Query(20),
):
    if ticker:
        trades, fetch_error = await _fetch_ticker(ticker.upper())
    else:
        trades, fetch_error = await _fetch_all()

    results = trades[:limit]

    return {
        "trades": results,
        "total": len(trades),
        "error": "rate_limited" if fetch_error else None,
    }


@router.get("/api/congress/summary")
async def get_congress_summary():
    all_trades, _ = await _fetch_all()

    ticker_counts: dict[str, int] = {}
    buys:  dict[str, int] = {}
    sells: dict[str, int] = {}

    for t in all_trades:
        sym = t.get("ticker", "")
        if not sym:
            continue
        ticker_counts[sym] = ticker_counts.get(sym, 0) + 1
        tx = t.get("transaction", "").lower()
        if "purchase" in tx:
            buys[sym]  = buys.get(sym, 0) + 1
        elif "sale" in tx:
            sells[sym] = sells.get(sym, 0) + 1

    top = sorted(ticker_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "top_tickers": [
            {"ticker": sym, "total_trades": count,
             "buys": buys.get(sym, 0), "sells": sells.get(sym, 0)}
            for sym, count in top
        ],
        "total_trades": len(all_trades),
    }

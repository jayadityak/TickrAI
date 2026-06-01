"""Stock price chart data endpoint.

Returns OHLCV history for a ticker at various time ranges.
Uses yfinance with in-memory caching.
"""

import logging
import time

import yfinance as yf
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache: (symbol, range) -> (timestamp, data)
_cache: dict[tuple[str, str], tuple[float, list]] = {}

# Range config: range_key -> (yfinance period, yfinance interval, cache TTL seconds)
RANGE_CONFIG = {
    "1D": ("1d", "5m", 300),       # 5-min candles, cache 5 min
    "1W": ("5d", "15m", 600),      # 15-min candles, cache 10 min
    "1M": ("1mo", "1d", 3600),     # Daily candles, cache 1 hr
    "3M": ("3mo", "1d", 3600),
    "6M": ("6mo", "1d", 3600),
    "1Y": ("1y", "1d", 3600),
    "5Y": ("5y", "1wk", 7200),     # Weekly candles, cache 2 hr
    "MAX": ("max", "1mo", 7200),   # Monthly candles
}


@router.get("/api/chart/{ticker}")
async def get_chart_data(
    ticker: str,
    range: str = Query("1Y", description="Time range: 1D, 1W, 1M, 3M, 6M, 1Y, 5Y, MAX"),
):
    """Return OHLCV price history for charting."""
    symbol = ticker.upper()
    range_key = range.upper()

    if range_key not in RANGE_CONFIG:
        range_key = "1Y"

    period, interval, ttl = RANGE_CONFIG[range_key]
    cache_key = (symbol, range_key)

    # Check cache
    now = time.time()
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < ttl:
            return {"ticker": symbol, "range": range_key, "data": data}

    def _fetch_df(sym: str):
        t = yf.Ticker(sym)
        df = t.history(period=period, interval=interval, auto_adjust=True, actions=False)
        # Fallback to 3-month daily if the full range returns nothing
        if df.empty and period not in ("1d", "5d"):
            df = t.history(period="3mo", interval="1d", auto_adjust=True, actions=False)
        return df

    try:
        df = _fetch_df(symbol)

        # If still empty, try alternate ticker formats (e.g. BRK.B → BRK-B)
        if df.empty:
            alts = []
            if "." in symbol:
                alts.append(symbol.replace(".", "-"))
            for alt in alts:
                df = _fetch_df(alt)
                if not df.empty:
                    logger.info("Chart: resolved %s as %s", symbol, alt)
                    break

        if df.empty:
            # Signal to frontend that no data is available for this ticker
            return {"ticker": symbol, "range": range_key, "data": [], "unavailable": True}

        points = []
        for idx, row in df.iterrows():
            # Clean the timestamp — remove timezone for frontend
            date_str = str(idx)[:19]

            points.append({
                "date": date_str,
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })

        _cache[cache_key] = (now, points)
        return {"ticker": symbol, "range": range_key, "data": points}

    except Exception as e:
        logger.warning("Chart data fetch failed for %s: %s", symbol, e)
        return {"ticker": symbol, "range": range_key, "data": [], "error": str(e)}

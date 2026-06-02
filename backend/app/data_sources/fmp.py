"""Financial Modeling Prep (FMP) data source.

Provides async helpers to fetch company data from the FMP stable API.
Includes in-memory caching to minimise API calls within the free-tier daily limit.
When the free tier is exhausted (402/429), sets a global flag to skip all subsequent
calls instantly — the report builder falls back to yfinance automatically.
"""

import asyncio
import logging
import time

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com/stable"

_semaphore = asyncio.Semaphore(2)

# Simple in-memory cache: key -> (timestamp, data)
# TTL = 1 hour — avoids repeat calls for same ticker within a session
_cache: dict[str, tuple[float, list | dict]] = {}
_CACHE_TTL = 21600  # 6 hours — profile, financials, and ratios rarely change intraday

# Track when FMP is exhausted — skip all calls for 1 hour
_exhausted_until: float = 0.0


def _cache_key(endpoint: str, params: dict | None) -> str:
    """Build a deterministic cache key from endpoint + params."""
    parts = [endpoint]
    if params:
        for k in sorted(params):
            if k == "apikey":
                continue
            parts.append(f"{k}={params[k]}")
    return "|".join(parts)


async def _get(endpoint: str, params: dict | None = None) -> list | dict:
    global _exhausted_until

    p = {"apikey": settings.fmp_api_key}
    if params:
        p.update(params)

    # If FMP is exhausted, skip immediately
    if time.time() < _exhausted_until:
        logger.debug("FMP exhausted, skipping %s", endpoint)
        return []

    # Check cache first
    ck = _cache_key(endpoint, params)
    if ck in _cache:
        ts, data = _cache[ck]
        if time.time() - ts < _CACHE_TTL:
            logger.debug("FMP cache hit: %s", ck)
            return data

    async with _semaphore:
        for attempt in range(2):
            # Re-check flag — another coroutine may have marked exhausted while we waited
            if time.time() < _exhausted_until:
                return []
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.get(f"{BASE_URL}/{endpoint}", params=p)
                    if r.status_code in (402, 403):
                        logger.warning("FMP free tier exhausted (%d), skipping all calls for 1h", r.status_code)
                        _exhausted_until = time.time() + 3600
                        return []
                    if r.status_code == 429:
                        _exhausted_until = time.time() + 3600
                        logger.warning("FMP rate limited on %s, marking exhausted", endpoint)
                        return []
                    r.raise_for_status()
                    result = r.json()
                    # Check for FMP error responses (daily limit reached)
                    if isinstance(result, dict) and "Error Message" in result:
                        logger.warning("FMP error for %s: %s", endpoint, result["Error Message"])
                        _exhausted_until = time.time() + 3600
                        return []
                    # Cache successful responses
                    _cache[ck] = (time.time(), result)
                    return result
            except httpx.TimeoutException:
                logger.warning("FMP timeout on %s (attempt %d)", endpoint, attempt + 1)
                continue
            except httpx.HTTPStatusError as e:
                logger.warning("FMP HTTP error on %s: %s", endpoint, e)
                return []
        logger.warning("FMP max retries exceeded for %s", endpoint)
        return []


async def get_profile(symbol: str) -> dict:
    data = await _get("profile", {"symbol": symbol})
    return data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}


async def get_income_statement(symbol: str, period: str = "annual", limit: int = 5) -> list:
    data = await _get("income-statement", {"symbol": symbol, "period": period, "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_balance_sheet(symbol: str, period: str = "annual", limit: int = 5) -> list:
    data = await _get("balance-sheet-statement", {"symbol": symbol, "period": period, "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_cash_flow(symbol: str, period: str = "annual", limit: int = 5) -> list:
    data = await _get("cash-flow-statement", {"symbol": symbol, "period": period, "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_ratios(symbol: str, period: str = "annual", limit: int = 5) -> list:
    data = await _get("ratios", {"symbol": symbol, "period": period, "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_key_metrics(symbol: str, period: str = "annual", limit: int = 5) -> list:
    data = await _get("key-metrics", {"symbol": symbol, "period": period, "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_peers(symbol: str) -> list:
    data = await _get("stock-peers", {"symbol": symbol})
    return data if isinstance(data, list) else []


async def get_rating(symbol: str) -> list:
    data = await _get("rating", {"symbol": symbol})
    return data if isinstance(data, list) else []


async def get_price_target_consensus(symbol: str) -> dict:
    """Return analyst price target consensus (high/low/median/consensus).

    Available on FMP Starter+. Returns empty dict on free tier or error.
    """
    data = await _get("price-target-consensus", {"symbol": symbol})
    if isinstance(data, list) and data:
        return data[0]
    return {}


async def get_key_metrics_ttm(symbol: str) -> dict:
    """Return the most recent annual key-metrics row with quality/value signals.

    Fields used: returnOnEquity, freeCashFlowYield, netDebtToEBITDA,
    currentRatio, returnOnInvestedCapital, grahamNumber.
    Available on FMP Starter+.
    """
    data = await _get("key-metrics", {"symbol": symbol, "period": "annual", "limit": "1"})
    if isinstance(data, list) and data:
        return data[0]
    return {}


async def get_earnings_surprises(symbol: str, limit: int = 4) -> list:
    """Return recent earnings surprise history (actual vs estimated EPS/revenue).

    Available on FMP Starter+.
    """
    data = await _get("earnings", {"symbol": symbol, "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_analyst_estimates(symbol: str, limit: int = 2) -> list:
    """Return forward analyst consensus estimates (revenue + EPS by fiscal year).

    Available on FMP Starter+. Returns up to `limit` future year rows.
    Fields: date, revenueAvg, revenueHigh, revenueLow, epsAvg, epsHigh, epsLow,
            ebitdaAvg, netIncomeAvg, numAnalystsRevenue, numAnalystsEps
    """
    data = await _get("analyst-estimates", {"symbol": symbol, "period": "annual", "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_income_statement_quarterly(symbol: str, limit: int = 8) -> list:
    """Return recent quarterly income statements.

    Used for true quarter-over-quarter comparison in the Earnings section.
    Up to `limit` quarters (default 8 = 2 years).
    """
    data = await _get("income-statement", {"symbol": symbol, "period": "quarter", "limit": str(limit)})
    return data if isinstance(data, list) else []


async def get_key_executives(symbol: str) -> list:
    """Return C-suite and board executives with titles and compensation.

    Fields: name, title, pay, yearBorn, gender, titleSince.
    Available on FMP Starter+.
    """
    data = await _get("key-executives", {"symbol": symbol})
    return data if isinstance(data, list) else []


async def get_revenue_segments(symbol: str) -> dict:
    """Return product/geographic revenue segment breakdown.

    Returns a dict keyed by segment name → revenue value.
    Available on FMP Starter+.
    """
    data = await _get("revenue-product-segmentation", {"symbol": symbol})
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], dict) else {}
    return {}

"""Financial Modeling Prep (FMP) data source.

Provides async helpers to fetch company data from the FMP stable API.
Includes in-memory caching to minimise API calls within the free-tier daily limit.
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
_CACHE_TTL = 3600  # seconds


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
    p = {"apikey": settings.fmp_api_key}
    if params:
        p.update(params)

    # Check cache first
    ck = _cache_key(endpoint, params)
    if ck in _cache:
        ts, data = _cache[ck]
        if time.time() - ts < _CACHE_TTL:
            logger.debug("FMP cache hit: %s", ck)
            return data

    async with _semaphore:
        for attempt in range(4):
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(f"{BASE_URL}/{endpoint}", params=p)
                if r.status_code == 429:
                    wait = 5 * (attempt + 1)
                    logger.warning("FMP rate limited on %s (attempt %d), waiting %ds", endpoint, attempt + 1, wait)
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                result = r.json()
                # Check for FMP error responses (daily limit reached)
                if isinstance(result, dict) and "Error Message" in result:
                    logger.warning("FMP error for %s: %s", endpoint, result["Error Message"])
                    return []
                # Cache successful responses
                _cache[ck] = (time.time(), result)
                return result
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

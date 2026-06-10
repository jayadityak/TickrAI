"""ETF-specific data helpers (FMP).

Wraps the four ETF endpoints: fund info, top holdings, sector weights,
country weights.  Reuses the shared _get() from fmp.py so the same
semaphore, exhaustion flag, and 6-hour cache all apply automatically.
"""

import logging

from .fmp import _get

logger = logging.getLogger(__name__)


async def get_etf_info(symbol: str) -> dict:
    """Fund metadata: expense ratio, AUM, benchmark, inception date, etc."""
    result = await _get(f"etf-info/{symbol}")
    if isinstance(result, list) and result:
        return result[0]
    if isinstance(result, dict):
        return result
    return {}


async def get_etf_holders(symbol: str, limit: int = 20) -> list:
    """Top holdings sorted by weight descending."""
    result = await _get(f"etf-holder/{symbol}")
    if not isinstance(result, list):
        return []
    result = sorted(
        result,
        key=lambda x: float(x.get("weightPercentage", 0) or 0),
        reverse=True,
    )
    return result[:limit]


async def get_etf_sector_weights(symbol: str) -> list:
    """Sector allocation weights."""
    result = await _get(f"etf-sector-weightings/{symbol}")
    if not isinstance(result, list):
        return []
    return sorted(
        result,
        key=lambda x: float(x.get("weightPercentage", 0) or 0),
        reverse=True,
    )


async def get_etf_country_weights(symbol: str) -> list:
    """Country allocation weights (useful for international ETFs)."""
    result = await _get(f"etf-country-weightings/{symbol}")
    if not isinstance(result, list):
        return []
    return sorted(
        result,
        key=lambda x: float(x.get("weightPercentage", 0) or 0),
        reverse=True,
    )

"""Institutional ownership data endpoint.

Uses yfinance to fetch 13F institutional holder data:
- institutional_holders: top hedge funds / asset managers
- mutualfund_holders: top mutual fund holders
- major_holders: high-level % summary (insiders, institutions, float)

Cached 24 hours — 13F filings are quarterly so daily refresh is wasteful.
"""

import logging
import math
import time

import yfinance as yf
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache: symbol -> (timestamp, data)
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 86400  # 24 hours


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> float | None:
    """Return float, or None if val is None/NaN/non-numeric."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    """Return int, or None if val is None/NaN."""
    f = _safe_float(val)
    return int(f) if f is not None else None


def _pct(raw: float | None) -> float | None:
    """Convert a fraction (0–1) to a percentage, or pass through if already > 1."""
    if raw is None:
        return None
    return round(raw * 100, 2) if raw <= 1.0 else round(raw, 2)


def _parse_holders(df, limit: int) -> list[dict]:
    """Convert a yfinance holders DataFrame to a list of dicts."""
    if df is None or df.empty:
        return []
    results = []
    for _, row in df.head(limit).iterrows():
        # yfinance column name variations across versions
        holder = str(row.get("Holder", row.get("Name", "Unknown")))
        shares = _safe_int(row.get("Shares", row.get("shares")))
        value = _safe_float(row.get("Value", row.get("value")))
        pct_raw = _safe_float(row.get("% Out", row.get("pctHeld", row.get("% of Shares"))))
        date_raw = row.get("Date Reported", row.get("dateReported", row.get("reportDate")))
        date_str = str(date_raw)[:10] if date_raw and str(date_raw) != "NaT" else "N/A"

        results.append({
            "holder": holder,
            "shares": shares,
            "value": value,
            "pct_out": _pct(pct_raw),
            "date_reported": date_str,
        })
    return results


def _parse_major_holders(df) -> dict:
    """Extract high-level ownership percentages from major_holders DataFrame.

    yfinance returns this in multiple formats across versions:
    - v0.2.x (most common): index = label string (e.g. "insidersPercentHeld"),
      single column "Value" → row.values has ONE element, label is the index
    - older: 2-column DataFrame [value, label_string]
    - older still: columns named ["Value", "Name"]

    We handle all three by checking the index first.
    """
    result: dict = {
        "pct_insiders": None,
        "pct_institutions": None,
        "pct_float_institutions": None,
        "num_institutions": None,
    }
    if df is None or df.empty:
        return result

    try:
        for idx, row in df.iterrows():
            vals = list(row.values)

            # ── Format A (most common in yfinance 0.2.x) ──────────────────
            # Index is a camelCase string like "insidersPercentHeld"
            # Row has a single "Value" column
            if isinstance(idx, str) and len(idx) > 3 and idx[0].isalpha():
                label = idx.lower()
                value_raw = vals[0] if vals else None

            # ── Format B: 2-column rows [value, label] or [label, value] ──
            elif len(vals) >= 2:
                if isinstance(vals[0], str):
                    label, value_raw = vals[0].lower(), vals[1]
                else:
                    value_raw, label = vals[0], str(vals[1]).lower()

            else:
                continue

            f = _safe_float(value_raw)
            if f is None:
                continue

            # Match to known fields by keyword
            if "insider" in label:
                result["pct_insiders"] = _pct(f)
            elif "float" in label:
                result["pct_float_institutions"] = _pct(f)
            elif "institution" in label and "count" not in label and "number" not in label:
                result["pct_institutions"] = _pct(f)
            elif "count" in label or "number" in label or f > 100:
                result["num_institutions"] = int(f)

    except Exception as e:
        logger.debug("major_holders parse error: %s", e)

    return result


# ---------------------------------------------------------------------------
# Data fetcher
# ---------------------------------------------------------------------------

def _fetch_institutional_data(symbol: str) -> dict:
    """Fetch and cache institutional ownership data for a ticker."""
    now = time.time()
    if symbol in _cache:
        ts, data = _cache[symbol]
        if now - ts < _CACHE_TTL:
            return data

    try:
        ticker_obj = yf.Ticker(symbol)

        top_holders = _parse_holders(ticker_obj.institutional_holders, 10)
        top_funds = _parse_holders(ticker_obj.mutualfund_holders, 5)
        summary_stats = _parse_major_holders(ticker_obj.major_holders)

        # Derive institutional conviction signal
        pct_inst = summary_stats.get("pct_institutions")
        num_inst = summary_stats.get("num_institutions")

        if pct_inst is not None and num_inst is not None:
            if pct_inst >= 60 and num_inst >= 500:
                signal = "Bullish"
            elif pct_inst < 20:
                signal = "Bearish"
            else:
                signal = "Neutral"
        elif pct_inst is not None:
            signal = "Bullish" if pct_inst >= 60 else "Bearish" if pct_inst < 20 else "Neutral"
        else:
            signal = "Neutral"

        largest_holder = top_holders[0]["holder"] if top_holders else "N/A"
        largest_holder_pct = top_holders[0]["pct_out"] if top_holders else None

        data: dict = {
            "top_holders": top_holders,
            "top_funds": top_funds,
            "summary": {
                **summary_stats,
                "largest_holder": largest_holder,
                "largest_holder_pct": largest_holder_pct,
                "signal": signal,
            },
        }
        _cache[symbol] = (now, data)

        logger.info(
            "Institutional data for %s — %d holders, %d funds, pct_inst=%s%%",
            symbol,
            len(top_holders),
            len(top_funds),
            f"{pct_inst:.1f}" if pct_inst is not None else "?",
        )
        return data

    except Exception as e:
        logger.warning("Failed to fetch institutional data for %s: %s", symbol, e)
        return {"top_holders": [], "top_funds": [], "summary": {}}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/api/institutional/{ticker}")
async def get_institutional_ownership(ticker: str):
    """Return 13F institutional ownership data for a ticker."""
    return _fetch_institutional_data(ticker.upper())

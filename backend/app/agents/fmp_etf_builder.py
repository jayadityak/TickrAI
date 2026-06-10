"""Build ETF report sections from FMP data.

Called by reports.py when profile.isEtf == True.
Returns 3 sections (agent_index 1–3) parallel to build_all_sections()
but shaped for fund data rather than equity financials.
"""

import asyncio
import logging

from ..data_sources import fmp
from ..data_sources.fmp_etf import (
    get_etf_country_weights,
    get_etf_holders,
    get_etf_info,
    get_etf_sector_weights,
)
from ..agents.llm_narrator import enhance_narrative, llm_available

logger = logging.getLogger(__name__)


def _fmt_pct(value) -> str | None:
    if value is None:
        return None
    try:
        v = float(value)
        return f"{v:.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _fmt_aum(value) -> str | None:
    if value is None:
        return None
    try:
        v = float(value)
        if v >= 1e12:
            return f"${v / 1e12:.2f}T"
        if v >= 1e9:
            return f"${v / 1e9:.1f}B"
        if v >= 1e6:
            return f"${v / 1e6:.1f}M"
        return f"${v:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_shares(value) -> str | None:
    if value is None:
        return None
    try:
        v = float(value)
        if v >= 1e9:
            return f"{v / 1e9:.2f}B"
        if v >= 1e6:
            return f"{v / 1e6:.1f}M"
        if v >= 1e3:
            return f"{v / 1e3:.1f}K"
        return f"{v:,.0f}"
    except (TypeError, ValueError):
        return str(value)


# ── Section builders ──────────────────────────────────────────────────

def _build_overview_data(ticker: str, profile: dict, etf_info: dict) -> dict:
    expense_raw = etf_info.get("expenseRatio") or etf_info.get("netExpenseRatio")
    expense_str = _fmt_pct(expense_raw) if expense_raw else None

    aum_raw = etf_info.get("aum") or etf_info.get("totalAssets") or profile.get("mktCap")
    aum_str = _fmt_aum(aum_raw) if aum_raw else None

    nav_raw = etf_info.get("nav") or etf_info.get("navPrice")
    nav_str = f"${float(nav_raw):.2f}" if nav_raw else None

    return {
        "fund_name": etf_info.get("fundName") or profile.get("companyName") or ticker,
        "issuer": etf_info.get("etfCompany") or etf_info.get("issuer") or profile.get("ceo") or None,
        "asset_class": etf_info.get("assetClass") or "Equity",
        "benchmark": etf_info.get("benchmark") or etf_info.get("index") or None,
        "inception_date": etf_info.get("inceptionDate") or None,
        "aum": aum_str,
        "expense_ratio": expense_str,
        "nav": nav_str,
        "exchange": profile.get("exchange") or etf_info.get("exchange") or "",
        "website": profile.get("website") or "",
        "description": etf_info.get("description") or profile.get("description") or "",
        "summary": etf_info.get("description") or profile.get("description") or f"{ticker} is an exchange-traded fund.",
        "company_name": etf_info.get("fundName") or profile.get("companyName") or ticker,
        "domicile": etf_info.get("domicile") or None,
        "currency": etf_info.get("currency") or "USD",
        "holdings_count": etf_info.get("holdingsCount") or None,
    }


def _build_holdings_data(holders: list) -> dict:
    holdings = []
    for h in holders:
        weight_raw = h.get("weightPercentage") or h.get("weight")
        try:
            weight_val = float(weight_raw) if weight_raw is not None else 0.0
        except (TypeError, ValueError):
            weight_val = 0.0

        holdings.append({
            "name": h.get("asset") or h.get("name") or h.get("companyName") or "Unknown",
            "symbol": h.get("symbol") or h.get("ticker") or "",
            "weight": round(weight_val, 4),
            "weight_str": f"{weight_val:.2f}%",
            "shares": _fmt_shares(h.get("sharesNumber") or h.get("shares")),
            "market_value": _fmt_aum(h.get("marketValue")),
        })

    return {
        "holdings": holdings,
        "total_shown": len(holdings),
    }


def _build_allocation_data(sector_weights: list, country_weights: list) -> dict:
    sectors = []
    for s in sector_weights:
        weight_raw = s.get("weightPercentage") or s.get("weight")
        try:
            weight_val = float(weight_raw) if weight_raw is not None else 0.0
        except (TypeError, ValueError):
            weight_val = 0.0
        if weight_val > 0:
            sectors.append({
                "sector": s.get("sector") or s.get("name") or "Unknown",
                "weight": round(weight_val, 4),
                "weight_str": f"{weight_val:.1f}%",
            })

    countries = []
    for c in country_weights:
        weight_raw = c.get("weightPercentage") or c.get("weight")
        try:
            weight_val = float(weight_raw) if weight_raw is not None else 0.0
        except (TypeError, ValueError):
            weight_val = 0.0
        if weight_val > 0:
            countries.append({
                "country": c.get("country") or c.get("name") or "Unknown",
                "weight": round(weight_val, 4),
                "weight_str": f"{weight_val:.1f}%",
            })

    return {
        "sector_weights": sectors,
        "country_weights": countries,
        "has_country_data": len(countries) > 1,
    }


# ── Main entry point ──────────────────────────────────────────────────

async def build_etf_sections(ticker: str) -> list[dict]:
    """Build 3 ETF report sections in parallel, with optional LLM enhancement."""

    # Fetch all data in parallel
    profile, etf_info, holders, sector_w, country_w = await asyncio.gather(
        fmp.get_profile(ticker),
        get_etf_info(ticker),
        get_etf_holders(ticker, limit=20),
        get_etf_sector_weights(ticker),
        get_etf_country_weights(ticker),
    )

    profile = profile or {}
    etf_info = etf_info or {}

    # Build raw section data
    overview_data = _build_overview_data(ticker, profile, etf_info)
    holdings_data = _build_holdings_data(holders)
    allocation_data = _build_allocation_data(sector_w, country_w)

    fund_name = overview_data["fund_name"]
    asset_class = overview_data.get("asset_class", "")

    # Optionally enhance ETF Overview with LLM narrative
    if llm_available():
        try:
            overview_data = await enhance_narrative(
                agent_name="ETF Overview",
                computed_data=overview_data,
                ticker=ticker,
                company_name=fund_name,
                sector=asset_class,
                industry=overview_data.get("benchmark") or "",
            )
        except Exception as e:
            logger.warning("LLM enhancement failed for ETF Overview %s: %s", ticker, e)

    return [
        {
            "agent_name": "ETF Overview",
            "agent_index": 1,
            "status": "completed",
            "data": overview_data,
        },
        {
            "agent_name": "ETF Holdings",
            "agent_index": 2,
            "status": "completed",
            "data": holdings_data,
        },
        {
            "agent_name": "ETF Allocation",
            "agent_index": 3,
            "status": "completed",
            "data": allocation_data,
        },
    ]

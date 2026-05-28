"""Side-by-side company comparison endpoint.

Fetches key metrics for 2-3 tickers and returns a normalized comparison.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Query

from ..data_sources import fmp
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _fmt_b(value) -> str | None:
    if value is None:
        return None
    v = float(value)
    if abs(v) >= 1e12:
        return f"${v / 1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.0f}"


async def _fetch_company_metrics(symbol: str) -> dict:
    """Fetch profile, ratios, and income for one company."""
    try:
        profile, ratios, income, balance = await asyncio.gather(
            fmp.get_profile(symbol),
            fmp.get_ratios(symbol, "annual", 1),
            fmp.get_income_statement(symbol, "annual", 2),
            fmp.get_balance_sheet(symbol, "annual", 1),
        )
    except Exception as e:
        logger.warning("Failed to fetch data for %s: %s", symbol, e)
        return {"symbol": symbol, "error": str(e)}

    r = ratios[0] if ratios else {}
    bs = balance[0] if balance else {}
    latest_income = income[0] if income else {}

    # Compute revenue growth
    rev_growth = None
    if income and len(income) >= 2:
        curr = income[0].get("revenue", 0) or 0
        prev = income[1].get("revenue", 0) or 0
        if prev:
            rev_growth = (curr - prev) / prev

    pe = r.get("priceToEarningsRatio")
    net_margin = r.get("netProfitMargin")
    current_ratio = r.get("currentRatio")
    de_ratio = r.get("debtEquityRatio")
    if not de_ratio and bs.get("totalStockholdersEquity"):
        de_ratio = (bs.get("totalDebt", 0) or 0) / bs["totalStockholdersEquity"]

    return {
        "symbol": symbol,
        "company_name": profile.get("companyName", symbol) if profile else symbol,
        "sector": profile.get("sector", "N/A") if profile else "N/A",
        "industry": profile.get("industry", "N/A") if profile else "N/A",
        "price": profile.get("price") if profile else None,
        "metrics": {
            "market_cap": _fmt_b(profile.get("marketCap")) if profile else "N/A",
            "market_cap_raw": profile.get("marketCap") if profile else 0,
            "pe_ratio": round(float(pe), 1) if pe else None,
            "revenue": _fmt_b(latest_income.get("revenue")),
            "revenue_raw": latest_income.get("revenue", 0) or 0,
            "net_income": _fmt_b(latest_income.get("netIncome")),
            "net_income_raw": latest_income.get("netIncome", 0) or 0,
            "eps": round(float(latest_income.get("epsDiluted", 0)), 2) if latest_income.get("epsDiluted") else None,
            "revenue_growth": round(rev_growth * 100, 1) if rev_growth is not None else None,
            "net_margin": round(float(net_margin) * 100, 1) if net_margin else None,
            "current_ratio": round(float(current_ratio), 2) if current_ratio else None,
            "debt_to_equity": round(float(de_ratio), 2) if de_ratio else None,
            "beta": round(float(profile.get("beta", 0)), 2) if profile and profile.get("beta") else None,
            "dividend_yield": round(float(r.get("dividendYield", 0)) * 100, 2) if r.get("dividendYield") else None,
        },
    }


@router.get("/api/compare")
async def compare_companies(
    tickers: str = Query(..., description="Comma-separated tickers (2-4)"),
    user: dict = Depends(get_current_user),
):
    """Compare 2-4 companies side by side."""
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    symbols = symbols[:4]  # Max 4

    if len(symbols) < 2:
        return {"error": "Please provide at least 2 tickers to compare"}

    results = await asyncio.gather(
        *[_fetch_company_metrics(s) for s in symbols],
        return_exceptions=True,
    )

    companies = []
    for r in results:
        if isinstance(r, Exception):
            continue
        if not r.get("error"):
            companies.append(r)

    # Determine "best" for each metric
    metric_keys = [
        "pe_ratio", "revenue_growth", "net_margin",
        "current_ratio", "debt_to_equity", "eps",
    ]
    winners: dict[str, str] = {}
    for key in metric_keys:
        best_sym = None
        best_val = None
        for c in companies:
            val = c["metrics"].get(key)
            if val is None:
                continue
            # Lower is better for PE and debt_to_equity
            if key in ("pe_ratio", "debt_to_equity"):
                if val > 0 and (best_val is None or val < best_val):
                    best_val = val
                    best_sym = c["symbol"]
            else:
                if best_val is None or val > best_val:
                    best_val = val
                    best_sym = c["symbol"]
        if best_sym:
            winners[key] = best_sym

    return {
        "companies": companies,
        "winners": winners,
    }

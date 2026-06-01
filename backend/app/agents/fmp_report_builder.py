"""Build structured report sections directly from FMP data.

Used when no OpenAI API key is configured — produces real reports
for any ticker using only FMP financial data.
"""

import asyncio
import logging

import yfinance as yf

from ..data_sources import fmp
from ..data_sources.edgar import get_10k_sections
from ..data_sources.transcript import get_earnings_transcript
from ..routers.insider import _fetch_insider_transactions
from ..routers.congress import _fetch_all as _fetch_congress_all
from ..routers.news import _fetch_headlines, _keyword_sentiment

logger = logging.getLogger(__name__)


async def _fetch_congress_trades_only() -> list:
    """Unwrap the (trades, is_error) tuple from _fetch_congress_all."""
    trades, _ = await _fetch_congress_all()
    return trades


def _fmt_billions(value) -> str | None:
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


def _fmt_pct(value) -> str | None:
    if value is None:
        return None
    return f"{float(value) * 100:.1f}%"


def _fmt_ratio(value) -> str | None:
    if value is None:
        return None
    return f"{float(value):.1f}x"


async def _safe_fetch(coro, default=None):
    try:
        return await coro
    except Exception as e:
        logger.warning("FMP fetch failed: %s", e)
        return default if default is not None else []


def _fetch_yfinance_info(symbol: str) -> dict:
    """Fetch all yfinance data for a ticker in one call (synchronous)."""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        # yfinance occasionally returns a list for ambiguous/delisted tickers
        return info if isinstance(info, dict) and info else {}
    except Exception as e:
        logger.warning("yfinance fetch failed for %s: %s", symbol, e)
        return {}


def _build_synthetic_profile(ticker: str, yf_info: dict) -> dict:
    """Build a FMP-profile-like dict from yfinance data when FMP is unavailable."""
    return {
        "companyName": yf_info.get("shortName") or yf_info.get("longName") or ticker.upper(),
        "sector": yf_info.get("sector", ""),
        "industry": yf_info.get("industry", ""),
        "marketCap": yf_info.get("marketCap"),
        "beta": yf_info.get("beta"),
        "price": yf_info.get("currentPrice") or yf_info.get("regularMarketPrice"),
        "exchange": yf_info.get("exchange", ""),
        "exchangeShortName": yf_info.get("exchange", ""),
        "exchangeFullName": yf_info.get("exchange", ""),
        "description": yf_info.get("longBusinessSummary", ""),
        "city": yf_info.get("city", ""),
        "state": yf_info.get("state", ""),
        "country": yf_info.get("country", ""),
        "website": yf_info.get("website", ""),
        "ceo": "",
        "fullTimeEmployees": yf_info.get("fullTimeEmployees"),
        "ipoDate": "",
        "lastDividend": yf_info.get("lastDividendValue"),
    }


def _format_transcript_context(transcript: dict) -> str:
    """Format transcript sections into a compact context string for Agent 5."""
    if not transcript:
        return ""
    parts = []
    period = transcript.get("period", "")
    if period:
        parts.append(f"=== Earnings Call {period} ===")
    if transcript.get("prepared_remarks"):
        parts.append(f"Prepared remarks: {transcript['prepared_remarks']}")
    if transcript.get("guidance_snippets"):
        parts.append(f"Guidance/forward-looking: {transcript['guidance_snippets']}")
    if transcript.get("qa_highlights"):
        parts.append(f"Q&A highlights: {transcript['qa_highlights']}")
    return "\n".join(parts)


async def _enhance_all_narratives(
    ticker: str, sections: list[dict], profile: dict, yf_info: dict,
    cross_signals: dict | None = None,
    filing_sections: dict | None = None,
    transcript: dict | None = None,
    key_metrics_ttm: dict | None = None,
    price_target_consensus: dict | None = None,
    analyst_estimates: list | None = None,
) -> list[dict]:
    """Enhance all section narratives with LLM-generated text.

    Runs agents 1-6 in parallel, then agent 7 sequentially (it can
    reference prior agent outputs for cross-signal synthesis).
    Falls back to original template text on any error.
    """
    from .llm_narrator import enhance_narrative, llm_available

    if not llm_available():
        return sections

    company_name = profile.get("companyName", ticker)
    sector = yf_info.get("sector") or profile.get("sector", "")
    industry = yf_info.get("industry") or profile.get("industry", "")
    current_price = profile.get("price") or (yf_info or {}).get("currentPrice")

    filing_sections = filing_sections or {}
    transcript = transcript or {}
    km = key_metrics_ttm or {}
    ptc = price_target_consensus or {}
    estimates = analyst_estimates or []

    # ── Company Overview context: EDGAR + FMP profile (CEO, description) ──
    overview_parts = []
    if filing_sections.get("business"):
        overview_parts.append(
            f"=== SEC 10-K BUSINESS DESCRIPTION ===\n{filing_sections['business']}"
        )
    profile_lines = []
    if profile.get("ceo"):
        profile_lines.append(f"CEO: {profile['ceo']}")
    if profile.get("fullTimeEmployees"):
        profile_lines.append(f"Employees: {profile['fullTimeEmployees']:,}")
    if profile.get("description"):
        profile_lines.append(profile["description"])
    if profile.get("website"):
        profile_lines.append(f"Website: {profile['website']}")
    if profile_lines:
        overview_parts.append("=== COMPANY PROFILE (FMP) ===\n" + "\n".join(profile_lines))

    # ── Financial Analysis context: quality metrics + price targets + estimates ──
    financial_parts = []

    if km:
        kparts = []
        if km.get("returnOnEquity") is not None:
            kparts.append(f"ROE: {km['returnOnEquity']*100:.1f}%")
        if km.get("returnOnInvestedCapital") is not None:
            kparts.append(f"ROIC: {km['returnOnInvestedCapital']*100:.1f}%")
        if km.get("freeCashFlowYield") is not None:
            kparts.append(f"FCF Yield: {km['freeCashFlowYield']*100:.1f}%")
        if km.get("netDebtToEBITDA") is not None:
            kparts.append(f"Net Debt/EBITDA: {km['netDebtToEBITDA']:.1f}x")
        if km.get("currentRatio") is not None:
            kparts.append(f"Current Ratio: {km['currentRatio']:.2f}")
        if km.get("grahamNumber") is not None:
            gn = km["grahamNumber"]
            kparts.append(f"Graham Number: ${gn:.2f}")
            if current_price and current_price > 0:
                kparts.append(f"Price vs Graham: {(current_price/gn - 1)*100:+.1f}%")
        if kparts:
            financial_parts.append(
                "=== QUALITY & VALUE SIGNALS (FMP key-metrics TTM) ===\n" + " | ".join(kparts)
            )

    if ptc:
        pt_line = []
        if ptc.get("targetConsensus"):
            pt_line.append(f"Consensus: ${ptc['targetConsensus']}")
        if ptc.get("targetMedian"):
            pt_line.append(f"Median: ${ptc['targetMedian']}")
        if ptc.get("targetLow"):
            pt_line.append(f"Bear: ${ptc['targetLow']}")
        if ptc.get("targetHigh"):
            pt_line.append(f"Bull: ${ptc['targetHigh']}")
        if current_price and ptc.get("targetConsensus") and current_price > 0:
            upside = (ptc["targetConsensus"] / current_price - 1) * 100
            pt_line.append(f"Implied upside from current: {upside:+.1f}%")
        if pt_line:
            financial_parts.append(
                "=== ANALYST PRICE TARGET CONSENSUS ===\n" + " | ".join(pt_line)
            )

    if estimates:
        est_lines = ["=== FORWARD ANALYST CONSENSUS ESTIMATES ==="]
        for est in estimates[:2]:
            yr = est.get("date", "")[:4]
            rev = est.get("revenueAvg")
            eps = est.get("epsAvg")
            n_rev = est.get("numAnalystsRevenue", "?")
            n_eps = est.get("numAnalystsEps", "?")
            line = f"FY{yr}:"
            if rev:
                line += f"  Revenue ${rev/1e9:.2f}B avg ({n_rev} analysts)"
            if eps:
                line += f"  |  EPS ${eps:.2f} avg ({n_eps} analysts)"
            if est.get("epsHigh") and est.get("epsLow"):
                line += f"  [range ${est['epsLow']:.2f}–${est['epsHigh']:.2f}]"
            est_lines.append(line)
        financial_parts.append("\n".join(est_lines))

    # ── Earnings Call context: transcript + analyst estimates (what the street expects) ──
    earnings_parts = [_format_transcript_context(transcript)]
    if estimates:
        est_lines = ["=== CONSENSUS ESTIMATES (what the street expects next) ==="]
        for est in estimates[:2]:
            yr = est.get("date", "")[:4]
            rev = est.get("revenueAvg")
            eps = est.get("epsAvg")
            line = f"FY{yr}:"
            if rev:
                line += f"  Revenue ${rev/1e9:.2f}B"
            if eps:
                line += f"  |  EPS ${eps:.2f}"
            est_lines.append(line)
        earnings_parts.append("\n".join(est_lines))

    # ── Risk Analysis context: EDGAR risks + quality/leverage signals ──
    risk_parts = []
    if filing_sections.get("risk_factors"):
        risk_parts.append(
            f"=== SEC 10-K RISK FACTORS ===\n{filing_sections['risk_factors']}"
        )
    if km:
        risk_signals = []
        if km.get("netDebtToEBITDA") is not None:
            risk_signals.append(f"Net Debt/EBITDA: {km['netDebtToEBITDA']:.1f}x")
        if km.get("currentRatio") is not None:
            risk_signals.append(f"Current Ratio: {km['currentRatio']:.2f}")
        if km.get("freeCashFlowYield") is not None:
            risk_signals.append(f"FCF Yield: {km['freeCashFlowYield']*100:.1f}%")
        if risk_signals:
            risk_parts.append("=== LEVERAGE & LIQUIDITY (FMP) ===\n" + " | ".join(risk_signals))

    filing_context_map = {
        "Company Overview":   "\n\n".join(overview_parts),
        "Financial Analysis": "\n\n".join(financial_parts),
        "Risk Analysis":      "\n\n".join(risk_parts),
        "Auditor Flags":      filing_sections.get("auditor", ""),
        "Earnings Call":      "\n\n".join(p for p in earnings_parts if p),
    }

    # Enhance agents 1-6 in parallel
    parallel_tasks = []
    for section in sections[:6]:
        parallel_tasks.append(
            enhance_narrative(
                agent_name=section["agent_name"],
                computed_data=section["data"],
                ticker=ticker,
                company_name=company_name,
                sector=sector,
                industry=industry,
                filing_context=filing_context_map.get(section["agent_name"], ""),
            )
        )

    enhanced_data = await asyncio.gather(*parallel_tasks)
    for i, data in enumerate(enhanced_data):
        sections[i]["data"] = data

    # Enhance agent 7 (Green/Red Flags) with prior sections + cross-signal data
    if len(sections) >= 7:
        prior = {s["agent_name"]: s["data"] for s in sections[:6]}
        if cross_signals:
            prior["cross_signals"] = cross_signals
        sections[6]["data"] = await enhance_narrative(
            agent_name=sections[6]["agent_name"],
            computed_data=sections[6]["data"],
            ticker=ticker,
            company_name=company_name,
            sector=sector,
            industry=industry,
            prior_sections=prior,
        )

    return sections


async def build_all_sections(ticker: str) -> list[dict]:
    """Fetch FMP data and build all 7 report sections.

    Optimized: 6 FMP calls + 1 yfinance call for target company.
    Peers use 1 yfinance call each (no FMP, saves API quota).
    """

    # Phase 1: fetch all data in parallel — FMP + yfinance + EDGAR + transcript + cross-signals
    loop = asyncio.get_event_loop()
    (
        profile, income_annual, balance, cash_flow, ratios, peers,
        yf_info, insider_data, congress_all, news_headlines,
        filing_sections, transcript, key_metrics_ttm, price_target_consensus,
        earnings_surprises, analyst_estimates,
    ) = await asyncio.gather(
        _safe_fetch(fmp.get_profile(ticker), {}),
        _safe_fetch(fmp.get_income_statement(ticker, "annual", 5)),
        _safe_fetch(fmp.get_balance_sheet(ticker, "annual", 1)),
        _safe_fetch(fmp.get_cash_flow(ticker, "annual", 1)),
        _safe_fetch(fmp.get_ratios(ticker, "annual", 1)),
        _safe_fetch(fmp.get_peers(ticker)),
        loop.run_in_executor(None, _fetch_yfinance_info, ticker),
        loop.run_in_executor(None, _fetch_insider_transactions, ticker.upper()),
        _safe_fetch(_fetch_congress_trades_only(), []),
        loop.run_in_executor(None, _fetch_headlines, ticker.upper()),
        _safe_fetch(get_10k_sections(ticker), {}),
        _safe_fetch(get_earnings_transcript(ticker), {}),
        _safe_fetch(fmp.get_key_metrics_ttm(ticker), {}),
        _safe_fetch(fmp.get_price_target_consensus(ticker), {}),
        _safe_fetch(fmp.get_earnings_surprises(ticker, 4), []),
        _safe_fetch(fmp.get_analyst_estimates(ticker, 2), []),
    )

    # If FMP profile is empty (rate-limited), build a synthetic one from yfinance
    if not profile and yf_info:
        profile = _build_synthetic_profile(ticker, yf_info)
    if not profile:
        raise ValueError(f"Could not find company data for ticker '{ticker}'")

    latest_ratios = ratios[0] if ratios else {}
    latest_bs = balance[0] if balance else {}
    latest_cf = cash_flow[0] if cash_flow else {}

    # Use income_annual last 4 quarters approximation for earnings section
    income_quarterly = income_annual[:2] if income_annual else []

    # Process cross-signal data for Agent 7
    cross_signals = _build_cross_signals(
        ticker, insider_data, congress_all, news_headlines,
    )

    # Phase 2: build all sections — pass shared yf_info to all builders
    sections = list(await asyncio.gather(
        _build_overview(ticker, profile, income_annual, yf_info),
        _build_financials(ticker, profile, income_annual, income_quarterly, latest_ratios, latest_ratios, yf_info, key_metrics_ttm, price_target_consensus, earnings_surprises),
        _build_risk(ticker, profile, latest_bs, latest_cf, latest_ratios, income_annual, yf_info),
        _build_auditor(ticker, profile, latest_ratios, latest_bs, latest_cf, income_annual, yf_info),
        _build_earnings(ticker, profile, income_quarterly, latest_ratios, yf_info),
        _build_sector_peers(ticker, profile, peers, latest_ratios, income_annual, yf_info),
        _build_green_red_flags(ticker, profile, income_annual, latest_ratios, latest_ratios, latest_bs, latest_cf, yf_info, cross_signals),
    ))

    # Phase 3: enhance narrative fields with LLM (if OpenAI key configured)
    sections = await _enhance_all_narratives(
        ticker, sections, profile, yf_info,
        cross_signals=cross_signals,
        filing_sections=filing_sections,
        transcript=transcript,
        key_metrics_ttm=key_metrics_ttm,
        price_target_consensus=price_target_consensus,
        analyst_estimates=analyst_estimates,
    )

    return sections


async def _build_overview(ticker: str, profile: dict, income_annual: list, yf_info: dict | None = None) -> dict:
    yf_info = yf_info or {}

    revenue_segments = []
    if profile.get("sector"):
        revenue_segments.append({"name": profile.get("industry", "Core"), "description": profile.get("description", "")[:120]})

    recent_devs = []
    if profile.get("ipoDate"):
        recent_devs.append(f"IPO date: {profile['ipoDate']}")
    if profile.get("lastDividend"):
        recent_devs.append(f"Last dividend: ${profile['lastDividend']}")
    if income_annual and len(income_annual) >= 2:
        rev_curr = income_annual[0].get("revenue", 0)
        rev_prev = income_annual[1].get("revenue", 0)
        if rev_prev and rev_curr:
            growth = (rev_curr - rev_prev) / rev_prev * 100
            recent_devs.append(f"Revenue growth of {growth:.1f}% in FY{income_annual[0].get('fiscalYear', '')}")

    # Use shared yf_info for richer data
    long_summary = yf_info.get("longBusinessSummary", "")
    yf_sector = yf_info.get("sector") or profile.get("sector", "")
    yf_industry = yf_info.get("industry") or profile.get("industry", "")
    website = yf_info.get("website") or profile.get("website")

    key_products = []
    if yf_industry:
        key_products.append(yf_industry)
    if not key_products:
        key_products = [profile.get("industry", "N/A")]

    exchange = profile.get("exchangeShortName") or profile.get("exchange", "")
    company_name = profile.get("companyName", ticker)

    return {
        "agent_name": "Company Overview",
        "agent_index": 1,
        "status": "completed",
        "data": {
            "business_description": long_summary or profile.get("description", "No description available."),
            "key_products": key_products,
            "revenue_segments": revenue_segments,
            "competitive_position": f"{company_name} operates in the {yf_industry or 'N/A'} industry within the {yf_sector or 'N/A'} sector. Market cap: {_fmt_billions(profile.get('marketCap'))}. Beta: {profile.get('beta', 'N/A')}.",
            "recent_developments": recent_devs if recent_devs else ["No recent developments available"],
            "management_highlights": f"CEO: {profile.get('ceo', 'N/A')}. Headquartered in {profile.get('city', '')}, {profile.get('state', '')}.",
            "employee_count": profile.get("fullTimeEmployees", "N/A"),
            "headquarters": f"{profile.get('city', '')}, {profile.get('state', profile.get('country', ''))}",
            "exchange": exchange,
            "company_name": company_name,
            "website": website,
            "sector": yf_sector,
            "industry": yf_industry,
        },
    }


async def _build_financials(ticker: str, profile: dict, annual: list, quarterly: list, ratios: dict, metrics: dict, yf_info: dict | None = None, key_metrics_ttm: dict | None = None, price_target_consensus: dict | None = None, earnings_surprises: list | None = None) -> dict:
    yf_info = yf_info or {}
    km = key_metrics_ttm or {}
    ptc = price_target_consensus or {}
    surprises = earnings_surprises or []
    company_name = profile.get("companyName", ticker)

    annual_trends = []
    for row in reversed(annual):
        rev = row.get("revenue")
        ni = row.get("netIncome")
        annual_trends.append({
            "year": f"FY{row.get('fiscalYear', row.get('date', '')[:4])}",
            "revenue": _fmt_billions(rev),
            "net_income": _fmt_billions(ni),
            "eps": f"${row.get('epsDiluted', 'N/A')}" if row.get("epsDiluted") else "N/A",
            "ebitda_margin": _fmt_pct(ratios.get("ebitdaMargin")) if ratios else "N/A",
            "net_margin": _fmt_pct(row.get("netIncome", 0) / row.get("revenue", 1)) if row.get("revenue") else "N/A",
        })

    quarterly_trends = []
    for row in reversed(quarterly[:4]):
        date = row.get("date", "")
        rev = row.get("revenue")
        ni = row.get("netIncome")
        quarterly_trends.append({
            "quarter": date[:7] if date else "N/A",
            "revenue": _fmt_billions(rev),
            "net_income": _fmt_billions(ni),
            "revenue_growth_yoy": "N/A",
        })

    pe = profile.get("price", 0) / annual[0].get("epsDiluted", 1) if annual and annual[0].get("epsDiluted") else None
    # Fallback PE from yfinance
    if pe is None:
        pe = yf_info.get("trailingPE") or yf_info.get("forwardPE")

    # When FMP annual data is empty, build summary from yfinance
    if annual:
        summary = f"{company_name} reported revenue of {_fmt_billions(annual[0].get('revenue'))} and net income of {_fmt_billions(annual[0].get('netIncome'))} in its most recent fiscal year. EPS was ${annual[0].get('epsDiluted', 'N/A')}."
        analysis = f"The company's most recent fiscal year shows revenue of {_fmt_billions(annual[0].get('revenue'))} with a net margin of {_fmt_pct(annual[0].get('netIncome', 0) / annual[0].get('revenue', 1)) if annual[0].get('revenue') else 'N/A'}. Operating income was {_fmt_billions(annual[0].get('operatingIncome'))}."
    else:
        total_rev = yf_info.get("totalRevenue")
        net_inc = yf_info.get("netIncomeToCommon")
        trailing_eps = yf_info.get("trailingEps")
        if total_rev:
            summary = f"{company_name} has trailing twelve-month revenue of {_fmt_billions(total_rev)}{f' and net income of {_fmt_billions(net_inc)}' if net_inc else ''}. {f'EPS: ${trailing_eps:.2f}.' if trailing_eps is not None else ''}"
            profit_margin = yf_info.get("profitMargins")
            op_margin = yf_info.get("operatingMargins")
            parts = [f"Trailing twelve-month revenue: {_fmt_billions(total_rev)}."]
            if profit_margin is not None:
                parts.append(f"Profit margin: {profit_margin*100:.1f}%.")
            if op_margin is not None:
                parts.append(f"Operating margin: {op_margin*100:.1f}%.")
            analysis = " ".join(parts)
        else:
            summary = "Financial data unavailable."
            analysis = "Insufficient data for analysis."

    # --- Quality & Value signals from FMP key-metrics (Starter+) ---
    roe = km.get("returnOnEquity")
    fcf_yield = km.get("freeCashFlowYield")
    net_debt_ebitda = km.get("netDebtToEBITDA")
    roic = km.get("returnOnInvestedCapital")
    graham_number = km.get("grahamNumber")
    current_price = profile.get("price") or yf_info.get("currentPrice")

    quality_metrics = {}
    if roe is not None:
        quality_metrics["roe"] = f"{roe * 100:.1f}%"
    if fcf_yield is not None:
        quality_metrics["fcf_yield"] = f"{fcf_yield * 100:.1f}%"
    if net_debt_ebitda is not None:
        quality_metrics["net_debt_ebitda"] = f"{net_debt_ebitda:.1f}x"
    if roic is not None:
        quality_metrics["roic"] = f"{roic * 100:.1f}%"
    if graham_number and current_price:
        upside = ((graham_number / current_price) - 1) * 100
        quality_metrics["graham_number"] = f"${graham_number:.2f}"
        quality_metrics["graham_upside"] = f"{upside:+.1f}%"

    # --- Analyst price target consensus (Starter+) ---
    price_target = {}
    if ptc:
        price_target = {
            "target_high": ptc.get("targetHigh"),
            "target_low": ptc.get("targetLow"),
            "target_consensus": ptc.get("targetConsensus"),
            "target_median": ptc.get("targetMedian"),
        }
        if ptc.get("targetConsensus") and current_price:
            upside_pct = ((ptc["targetConsensus"] / current_price) - 1) * 100
            price_target["upside_pct"] = round(upside_pct, 1)

    # --- Earnings surprises (Starter+) ---
    recent_surprises = []
    for s in surprises[:4]:
        eps_a = s.get("epsActual")
        eps_e = s.get("epsEstimated")
        if eps_a is not None and eps_e is not None and eps_e != 0:
            beat_pct = ((eps_a - eps_e) / abs(eps_e)) * 100
            recent_surprises.append({
                "date": s.get("date", "")[:7],
                "eps_actual": eps_a,
                "eps_estimated": eps_e,
                "beat_pct": round(beat_pct, 1),
            })

    return {
        "agent_name": "Financial Analysis",
        "agent_index": 2,
        "status": "completed",
        "data": {
            "summary": summary,
            "key_metrics": {
                "pe_ratio": round(pe, 1) if pe else None,
                "market_cap": _fmt_billions(profile.get("marketCap") or yf_info.get("marketCap")),
                "price_to_book": round(float(metrics.get("priceToBookRatio", 0)), 1) if metrics.get("priceToBookRatio") else (round(yf_info["priceToBook"], 1) if yf_info.get("priceToBook") else None),
                "dividend_yield": _fmt_pct(metrics.get("dividendYield")) if metrics.get("dividendYield") else (_fmt_pct(yf_info["dividendYield"]) if yf_info.get("dividendYield") else None),
            },
            "quality_metrics": quality_metrics,
            "price_target": price_target if price_target else None,
            "earnings_surprises": recent_surprises if recent_surprises else None,
            "annual_trends": annual_trends,
            "analysis": analysis,
        },
    }


async def _build_risk(ticker: str, profile: dict, bs: dict, cf: dict, ratios: dict, income_annual: list | None = None, yf_info: dict | None = None) -> dict:
    risks = []

    yf_data = yf_info or {}

    # --- 1. Leverage Risk (FMP balance sheet) ---
    total_debt = bs.get("totalDebt", 0) or 0
    total_equity = bs.get("totalStockholdersEquity", 0) or 0
    de_ratio = total_debt / total_equity if total_equity else None
    # Also check yfinance D/E
    if de_ratio is None and yf_data.get("debtToEquity"):
        de_ratio = yf_data["debtToEquity"] / 100  # yfinance returns as percentage

    if de_ratio is not None:
        risks.append({
            "category": "Leverage Risk",
            "severity": 5 if de_ratio > 3 else 4 if de_ratio > 2 else 2 if de_ratio > 1 else 1,
            "description": f"Debt-to-equity ratio of {de_ratio:.2f}. {'Highly leveraged — significant financial risk.' if de_ratio > 2 else 'Moderate leverage.' if de_ratio > 1 else 'Conservative capital structure.'}",
            "evidence": f"Total debt: {_fmt_billions(total_debt)}, Total equity: {_fmt_billions(total_equity)}.",
        })
    else:
        risks.append({
            "category": "Leverage Risk",
            "severity": 2,
            "description": "Debt-to-equity data unavailable.",
            "evidence": "Balance sheet data unavailable.",
        })

    # --- 2. Liquidity Risk (FMP ratios) ---
    current_ratio = ratios.get("currentRatio")
    if current_ratio is not None:
        risks.append({
            "category": "Liquidity Risk",
            "severity": 5 if current_ratio < 0.5 else 4 if current_ratio < 1 else 2 if current_ratio < 1.5 else 1,
            "description": f"Current ratio of {current_ratio:.2f}. {'Severe liquidity strain — may struggle to meet short-term obligations.' if current_ratio < 1 else 'Adequate but tight liquidity.' if current_ratio < 1.5 else 'Healthy liquidity position.'}",
            "evidence": f"Current ratio: {current_ratio:.2f}. A ratio below 1.0 means current liabilities exceed current assets.",
        })
    else:
        risks.append({
            "category": "Liquidity Risk",
            "severity": 2,
            "description": "Current ratio data unavailable.",
            "evidence": "Liquidity data not reported.",
        })

    # --- 3. Cash Flow Risk (FMP cash flow + yfinance) ---
    ocf = cf.get("operatingCashFlow", 0) or yf_data.get("operatingCashflow", 0) or 0
    ni = cf.get("netIncome", 0) or 0
    fcf = yf_data.get("freeCashflow")
    cash_conversion = ocf / ni if ni and ni != 0 else None

    cf_severity = 1
    cf_desc = f"Operating cash flow of {_fmt_billions(ocf)}."
    if ocf <= 0:
        cf_severity = 5
        cf_desc = f"Negative operating cash flow of {_fmt_billions(ocf)}. Company is burning cash from operations."
    elif cash_conversion is not None and cash_conversion < 0.5:
        cf_severity = 3
        cf_desc = f"Operating cash flow of {_fmt_billions(ocf)} (cash conversion ratio: {cash_conversion:.2f}x). Earnings quality is weak — cash flow significantly trails net income."
    elif cash_conversion is not None and cash_conversion >= 0.8:
        cf_desc = f"Operating cash flow of {_fmt_billions(ocf)} (cash conversion ratio: {cash_conversion:.2f}x). Strong earnings quality."

    if fcf is not None:
        cf_desc += f" Free cash flow: {_fmt_billions(fcf)}."
        if fcf < 0 and cf_severity < 4:
            cf_severity = max(cf_severity, 3)

    risks.append({
        "category": "Cash Flow Risk",
        "severity": cf_severity,
        "description": cf_desc,
        "evidence": f"OCF: {_fmt_billions(ocf)}, Net Income: {_fmt_billions(ni)}, FCF: {_fmt_billions(fcf) if fcf else 'N/A'}.",
    })

    # --- 4. Volatility & Market Risk (yfinance) ---
    beta = yf_data.get("beta") or profile.get("beta")
    high_52 = yf_data.get("fiftyTwoWeekHigh")
    low_52 = yf_data.get("fiftyTwoWeekLow")
    current_price = yf_data.get("currentPrice")
    drawdown = None
    if high_52 and current_price:
        drawdown = (current_price - high_52) / high_52 * 100

    vol_severity = 1
    vol_parts = []
    if beta:
        if beta > 2:
            vol_severity = max(vol_severity, 4)
            vol_parts.append(f"Beta of {beta:.2f} — extremely volatile, moves {beta:.1f}x vs the market")
        elif beta > 1.5:
            vol_severity = max(vol_severity, 3)
            vol_parts.append(f"Beta of {beta:.2f} — significantly more volatile than the market")
        elif beta > 1:
            vol_severity = max(vol_severity, 2)
            vol_parts.append(f"Beta of {beta:.2f} — slightly above-market volatility")
        else:
            vol_parts.append(f"Beta of {beta:.2f} — lower volatility than the market")

    if drawdown is not None and drawdown < -30:
        vol_severity = max(vol_severity, 3)
        vol_parts.append(f"Currently {drawdown:.1f}% below 52-week high")
    elif drawdown is not None:
        vol_parts.append(f"{drawdown:.1f}% from 52-week high")

    if high_52 and low_52:
        range_pct = (high_52 - low_52) / low_52 * 100
        vol_parts.append(f"52-week range: ${low_52:.2f}–${high_52:.2f} ({range_pct:.0f}% spread)")

    risks.append({
        "category": "Volatility & Market Risk",
        "severity": vol_severity,
        "description": ". ".join(vol_parts) + "." if vol_parts else "Volatility data unavailable.",
        "evidence": (f"Beta: {beta or 'N/A'}, Current: ${current_price:.2f}" + (f", 52W High: ${high_52:.2f}" if high_52 else "")) if current_price else f"Beta: {beta or 'N/A'}. Price data unavailable.",
    })

    # --- 5. Short Seller Risk (yfinance) ---
    short_pct = yf_data.get("shortPercentOfFloat")
    short_ratio = yf_data.get("shortRatio")

    if short_pct is not None:
        short_severity = 4 if short_pct > 0.2 else 3 if short_pct > 0.1 else 2 if short_pct > 0.05 else 1
        risks.append({
            "category": "Short Interest Risk",
            "severity": short_severity,
            "description": f"{short_pct*100:.1f}% of float is sold short{' (days to cover: ' + f'{short_ratio:.1f})' if short_ratio else ''}. {'Heavy short interest signals strong bearish sentiment.' if short_pct > 0.2 else 'Elevated short interest — bears are actively betting against this stock.' if short_pct > 0.1 else 'Moderate short interest.' if short_pct > 0.05 else 'Low short interest.'}",
            "evidence": f"Short % of float: {short_pct*100:.1f}%, Short ratio (days to cover): {short_ratio:.1f}" if short_ratio else f"Short % of float: {short_pct*100:.1f}%",
        })

    # --- 6. Profitability Risk (yfinance + FMP) ---
    gross_margin = yf_data.get("grossMargins")
    op_margin = yf_data.get("operatingMargins")
    roe = yf_data.get("returnOnEquity")
    earnings_growth = yf_data.get("earningsGrowth")

    prof_severity = 1
    prof_parts = []

    if op_margin is not None:
        if op_margin < 0:
            prof_severity = max(prof_severity, 4)
            prof_parts.append(f"Negative operating margin of {op_margin*100:.1f}% — company is not operationally profitable")
        elif op_margin < 0.05:
            prof_severity = max(prof_severity, 3)
            prof_parts.append(f"Thin operating margin of {op_margin*100:.1f}% — vulnerable to cost pressures")
        else:
            prof_parts.append(f"Operating margin of {op_margin*100:.1f}%")

    if roe is not None:
        if roe < 0:
            prof_severity = max(prof_severity, 3)
            prof_parts.append(f"negative return on equity ({roe*100:.1f}%)")
        elif roe > 0.2:
            prof_parts.append(f"strong ROE of {roe*100:.1f}%")
        else:
            prof_parts.append(f"ROE of {roe*100:.1f}%")

    if earnings_growth is not None:
        if earnings_growth < -0.2:
            prof_severity = max(prof_severity, 3)
            prof_parts.append(f"earnings declining {earnings_growth*100:.1f}% YoY")
        elif earnings_growth > 0:
            prof_parts.append(f"earnings growing {earnings_growth*100:.1f}% YoY")

    if prof_parts:
        risks.append({
            "category": "Profitability Risk",
            "severity": prof_severity,
            "description": (prof_parts[0][0].upper() + prof_parts[0][1:] + ", " + ", ".join(prof_parts[1:]) + ".") if len(prof_parts) > 1 else prof_parts[0] + ".",
            "evidence": ", ".join(filter(None, [
                f"Gross margin: {gross_margin*100:.1f}%" if gross_margin is not None else None,
                f"Operating margin: {op_margin*100:.1f}%" if op_margin is not None else None,
                f"ROE: {roe*100:.1f}%" if roe is not None else None,
            ])) or "Profitability data unavailable.",
        })

    # --- 7. Revenue Concentration / Growth Risk ---
    rev_growth = yf_data.get("revenueGrowth")
    if rev_growth is not None:
        rg_severity = 4 if rev_growth < -0.1 else 3 if rev_growth < 0 else 2 if rev_growth < 0.05 else 1
        risks.append({
            "category": "Growth Risk",
            "severity": rg_severity,
            "description": f"Revenue {'declining' if rev_growth < 0 else 'growing'} at {rev_growth*100:.1f}% YoY. {'Significant revenue decline raises sustainability concerns.' if rev_growth < -0.1 else 'Revenue contraction is a warning sign.' if rev_growth < 0 else 'Slow growth may indicate market saturation.' if rev_growth < 0.05 else 'Healthy revenue growth.'}",
            "evidence": f"Revenue growth: {rev_growth*100:.1f}% year-over-year. Total revenue: {_fmt_billions(yf_data.get('totalRevenue'))}." if yf_data.get("totalRevenue") else f"Revenue growth: {rev_growth*100:.1f}% YoY.",
        })

    overall = "High" if any(r["severity"] >= 4 for r in risks) else "Medium" if any(r["severity"] >= 3 for r in risks) else "Low"

    return {
        "agent_name": "Risk Analysis",
        "agent_index": 3,
        "status": "completed",
        "data": {
            "overall_risk_level": overall,
            "risks": risks,
        },
    }


async def _build_auditor(ticker: str, profile: dict, ratios: dict, bs: dict, cf: dict, income_annual: list | None = None, yf_info: dict | None = None) -> dict:
    flags = []
    yf_data = yf_info or {}

    ocf = cf.get("operatingCashFlow", 0) or yf_data.get("operatingCashflow", 0) or 0
    ni = cf.get("netIncome", 0) or yf_data.get("netIncomeToCommon", 0) or 0

    # --- 1. Earnings Quality (OCF vs Net Income) ---
    if ni and ocf:
        ratio = ocf / ni if ni != 0 else 0
        flags.append({
            "type": "Earnings Quality",
            "severity": "OK" if ratio > 0.8 else "Warning" if ratio > 0.5 else "Critical",
            "description": f"Cash conversion ratio: {ratio:.2f}x. {'Strong — cash flow supports reported earnings.' if ratio > 0.8 else 'Moderate — earnings exceed operating cash, possible accrual build-up.' if ratio > 0.5 else 'Weak — significant gap between reported earnings and actual cash generated. Potential earnings manipulation risk.'}",
            "recommendation": "Strong cash earnings quality — no concerns." if ratio > 0.8 else "Monitor accruals and receivables growth." if ratio > 0.5 else "Deep-dive into accruals, receivables, and revenue recognition policies. Large OCF-to-NI gaps can signal aggressive accounting.",
        })

    # --- 2. Liquidity Health ---
    cr = ratios.get("currentRatio")
    if cr:
        flags.append({
            "type": "Liquidity Health",
            "severity": "OK" if cr > 1.5 else "Warning" if cr > 1 else "Critical",
            "description": f"Current ratio: {cr:.2f}. {'Healthy liquidity buffer.' if cr > 1.5 else 'Tight but functional — short-term obligations are just barely covered.' if cr > 1 else 'Current liabilities exceed current assets. Risk of inability to meet near-term obligations.'}",
            "recommendation": "Adequate liquidity — no immediate concerns." if cr > 1.5 else "Monitor working capital trends and upcoming debt maturities." if cr > 1 else "Assess if the company has credit facilities, near-term debt maturities, or potential going-concern risk.",
        })

    # --- 3. Leverage Assessment ---
    de = ratios.get("debtEquityRatio") or (bs.get("totalDebt", 0) / bs.get("totalStockholdersEquity", 1) if bs.get("totalStockholdersEquity") else None)
    if de:
        flags.append({
            "type": "Leverage Assessment",
            "severity": "OK" if de < 1 else "Warning" if de < 2.5 else "Critical",
            "description": f"Debt-to-equity: {de:.2f}. {'Conservative balance sheet.' if de < 1 else 'Moderately leveraged — debt is manageable but worth monitoring.' if de < 2.5 else 'Heavily leveraged — high debt burden relative to equity. Debt servicing could become problematic in a downturn.'}",
            "recommendation": "Conservative leverage — no concerns." if de < 1 else "Review interest coverage ratio and upcoming debt maturities." if de < 2.5 else "Evaluate debt covenants, refinancing risk, and interest coverage. High leverage in downturns can trigger covenant breaches.",
        })

    # --- 4. Interest Coverage ---
    ebit = None
    interest_expense = None
    if income_annual:
        ebit = income_annual[0].get("operatingIncome", 0) or income_annual[0].get("ebitda", 0)
        interest_expense = income_annual[0].get("interestExpense", 0)

    if ebit and interest_expense and interest_expense != 0:
        ic_ratio = abs(ebit / interest_expense)
        flags.append({
            "type": "Interest Coverage",
            "severity": "OK" if ic_ratio > 5 else "Warning" if ic_ratio > 2 else "Critical",
            "description": f"Interest coverage ratio: {ic_ratio:.1f}x. {'Strong ability to service debt from operating income.' if ic_ratio > 5 else 'Adequate but limited margin of safety for debt payments.' if ic_ratio > 2 else 'Earnings barely cover interest payments. Risk of debt distress if earnings decline.'}",
            "recommendation": "Comfortable debt coverage." if ic_ratio > 5 else "Monitor for any earnings deterioration that could pressure debt service." if ic_ratio > 2 else "Assess refinancing options and potential for covenant breaches. Interest coverage below 2x is a major red flag.",
        })

    # --- 5. Receivables vs Revenue Growth (earnings manipulation check) ---
    if income_annual and len(income_annual) >= 2:
        rev_curr = income_annual[0].get("revenue", 0) or 0
        rev_prev = income_annual[1].get("revenue", 0) or 0
        ar_curr = bs.get("netReceivables", 0) or 0

        if rev_curr and rev_prev and rev_prev != 0:
            rev_growth_rate = (rev_curr - rev_prev) / abs(rev_prev)
            # Days Sales Outstanding proxy
            dso = (ar_curr / rev_curr * 365) if rev_curr else None

            if dso is not None:
                dso_severity = "OK" if dso < 60 else "Warning" if dso < 90 else "Critical"
                flags.append({
                    "type": "Receivables Quality",
                    "severity": dso_severity,
                    "description": f"Days sales outstanding: {dso:.0f} days. {'Normal collection period.' if dso < 60 else 'Elevated receivables — customers are slow to pay or revenue may be recognized aggressively.' if dso < 90 else 'Very high receivables relative to revenue. Potential revenue recognition issues or credit risk.'}",
                    "recommendation": "Receivables look healthy." if dso < 60 else "Compare DSO to industry peers and historical trend. Rising DSO with flat revenue can signal channel stuffing." if dso < 90 else "Investigate revenue recognition policies, customer credit quality, and allowance for doubtful accounts.",
                })

    # --- 6. Free Cash Flow Check ---
    capex = cf.get("capitalExpenditure", 0) or 0
    fcf = ocf + capex  # capex is typically negative in FMP
    if ocf:
        fcf_severity = "OK" if fcf > 0 else "Warning" if ocf > 0 else "Critical"
        flags.append({
            "type": "Free Cash Flow",
            "severity": fcf_severity,
            "description": f"Free cash flow: {_fmt_billions(fcf)} (OCF: {_fmt_billions(ocf)}, CapEx: {_fmt_billions(abs(capex))}). {'Positive FCF — company generates cash after reinvestment.' if fcf > 0 else 'Negative FCF despite positive operating cash flow — heavy capital spending.' if ocf > 0 else 'Negative operating cash flow — company is cash-consumptive.'}",
            "recommendation": "Healthy free cash flow generation." if fcf > 0 else "Assess whether capital spending is growth-oriented or maintenance. Persistent negative FCF requires external financing." if ocf > 0 else "Evaluate burn rate and funding sources. Negative FCF companies depend on debt or equity issuance to survive.",
        })

    # --- 7. Piotroski F-Score (financial strength, 0-9 scale) ---
    f_score = 0
    f_details = []

    if ni and ni > 0:
        f_score += 1
        f_details.append("Positive net income")
    if ocf and ocf > 0:
        f_score += 1
        f_details.append("Positive operating cash flow")
    if ni and ocf and ocf > ni:
        f_score += 1
        f_details.append("Cash flow exceeds net income (accrual quality)")
    if cr and ratios.get("currentRatio"):
        # Check if current ratio improved (would need prior year — approximate)
        if cr > 1.5:
            f_score += 1
            f_details.append("Strong current ratio")
    total_assets = bs.get("totalAssets", 0) or 0
    if total_assets and ni:
        roa = ni / total_assets
        if roa > 0:
            f_score += 1
            f_details.append(f"Positive ROA ({roa*100:.1f}%)")
    gross_profit = income_annual[0].get("grossProfit", 0) if income_annual else 0
    revenue = income_annual[0].get("revenue", 0) if income_annual else 0
    if gross_profit and revenue and gross_profit / revenue > 0.3:
        f_score += 1
        f_details.append(f"Healthy gross margin ({gross_profit/revenue*100:.1f}%)")

    # Debt change
    total_equity_auditor = bs.get("totalStockholdersEquity", 0) or 0
    long_term_debt = bs.get("longTermDebt", 0) or 0
    if total_equity_auditor and long_term_debt:
        lt_de = long_term_debt / total_equity_auditor
        if lt_de < 0.5:
            f_score += 1
            f_details.append("Low long-term debt relative to equity")

    flags.append({
        "type": "Piotroski F-Score",
        "severity": "OK" if f_score >= 6 else "Warning" if f_score >= 3 else "Critical",
        "description": f"F-Score: {f_score}/7. {'Strong financial health across profitability, leverage, and efficiency metrics.' if f_score >= 6 else 'Mixed signals — some financial health metrics are concerning.' if f_score >= 3 else 'Weak financial health — multiple warning signs across profitability and balance sheet.'}",
        "recommendation": f"Passing signals: {', '.join(f_details[:4])}." + ("" if f_score >= 6 else " Review failing criteria for specific areas of concern."),
    })

    # --- Build summary ---
    critical_count = sum(1 for f in flags if f["severity"] == "Critical")
    warning_count = sum(1 for f in flags if f["severity"] == "Warning")
    ok_count = sum(1 for f in flags if f["severity"] == "OK")

    if critical_count >= 2:
        overall_assessment = f"Multiple critical flags detected ({critical_count}). Significant financial health concerns warrant careful due diligence."
    elif critical_count == 1:
        overall_assessment = f"One critical flag with {warning_count} warnings. Specific areas require attention before investing."
    elif warning_count >= 3:
        overall_assessment = f"Several warning signs ({warning_count}). No critical issues, but elevated caution is warranted."
    elif warning_count >= 1:
        overall_assessment = f"Generally healthy with {warning_count} area(s) to monitor. Fundamentals are largely intact."
    else:
        overall_assessment = f"Clean audit assessment — {ok_count} metrics all pass. Strong financial health indicators."

    return {
        "agent_name": "Auditor Flags",
        "agent_index": 4,
        "status": "completed",
        "data": {
            "summary": f"{profile.get('companyName', ticker)}: {overall_assessment}",
            "flags": flags,
            "auditor_assessment": overall_assessment,
        },
    }


async def _build_earnings(ticker: str, profile: dict, quarterly: list, metrics: dict, yf_info: dict | None = None) -> dict:
    yf_info = yf_info or {}
    themes = []
    concerns = []

    company_name = profile.get("companyName", ticker)

    # --- Revenue trend ---
    if quarterly and len(quarterly) >= 2:
        rev_latest = quarterly[0].get("revenue", 0) or 0
        rev_prior = quarterly[1].get("revenue", 0) or 0
        if rev_prior:
            qoq_growth = (rev_latest - rev_prior) / rev_prior * 100
            themes.append(f"Sequential revenue {'growth' if qoq_growth > 0 else 'decline'} of {qoq_growth:.1f}% ({_fmt_billions(rev_prior)} → {_fmt_billions(rev_latest)})")
            if qoq_growth < -5:
                concerns.append(f"Revenue dropped {abs(qoq_growth):.1f}% sequentially")

    # --- YoY revenue growth from yfinance ---
    rev_growth = yf_info.get("revenueGrowth")
    if rev_growth is not None:
        themes.append(f"Year-over-year revenue growth: {rev_growth*100:.1f}%")
        if rev_growth < -0.05:
            concerns.append(f"YoY revenue declining {rev_growth*100:.1f}%")

    # --- Earnings growth ---
    earnings_growth = yf_info.get("earningsGrowth")
    if earnings_growth is not None:
        if earnings_growth > 0.15:
            themes.append(f"Earnings growing {earnings_growth*100:.1f}% YoY — strong bottom-line momentum")
        elif earnings_growth > 0:
            themes.append(f"Earnings growth of {earnings_growth*100:.1f}% YoY")
        else:
            concerns.append(f"Earnings declining {earnings_growth*100:.1f}% YoY")

    # --- Margins ---
    if quarterly:
        rev = quarterly[0].get("revenue", 0) or 0
        ni = quarterly[0].get("netIncome", 0) or 0
        gp = quarterly[0].get("grossProfit", 0) or 0
        if rev:
            net_margin = ni / rev
            themes.append(f"Net margin: {net_margin*100:.1f}%")
            if net_margin < 0:
                concerns.append(f"Net loss of {_fmt_billions(abs(ni))} — company is unprofitable")
            elif net_margin < 0.03:
                concerns.append(f"Thin net margin of {net_margin*100:.1f}%")
            if gp:
                gross_margin = gp / rev
                themes.append(f"Gross margin: {gross_margin*100:.1f}%")

    # --- EPS data ---
    trailing_eps = yf_info.get("trailingEps")
    forward_eps = yf_info.get("forwardEps")
    if trailing_eps is not None and forward_eps is not None:
        eps_growth = (forward_eps - trailing_eps) / abs(trailing_eps) * 100 if trailing_eps != 0 else 0
        themes.append(f"EPS: ${trailing_eps:.2f} trailing → ${forward_eps:.2f} forward ({'+' if eps_growth > 0 else ''}{eps_growth:.0f}% expected)")
    elif trailing_eps is not None:
        themes.append(f"Trailing EPS: ${trailing_eps:.2f}")

    # --- Analyst estimates ---
    rec_key = yf_info.get("recommendationKey", "")
    num_analysts = yf_info.get("numberOfAnalystOpinions", 0)
    target_mean = yf_info.get("targetMeanPrice")
    target_high = yf_info.get("targetHighPrice")
    target_low = yf_info.get("targetLowPrice")
    current_price = yf_info.get("currentPrice")

    # --- Volatility ---
    beta = yf_info.get("beta") or profile.get("beta")
    if beta and beta > 1.5:
        concerns.append(f"High beta of {beta:.2f} — stock is significantly more volatile than the market")

    if not themes:
        themes = ["Limited quarterly data available"]
    if not concerns:
        concerns = ["No significant concerns identified from recent financial data"]

    # Determine tone from balance of signals
    bullish_signals = sum(1 for t in themes if any(w in t.lower() for w in ["growing", "growth", "strong", "positive"]))
    bearish_signals = len(concerns) - (1 if "No significant concerns" in concerns[0] else 0)

    if bearish_signals >= 3:
        tone = "bearish"
    elif bearish_signals >= 2 and bullish_signals < 2:
        tone = "bearish"
    elif bullish_signals >= 3 and bearish_signals <= 1:
        tone = "bullish"
    elif bullish_signals > bearish_signals:
        tone = "bullish"
    elif bearish_signals > bullish_signals:
        tone = "bearish"
    else:
        tone = "neutral"

    # Build guidance section from real analyst data
    guidance = {}
    if quarterly:
        guidance["revenue_guidance"] = f"Latest quarterly revenue: {_fmt_billions(quarterly[0].get('revenue'))}"
    if forward_eps is not None:
        guidance["earnings_guidance"] = f"Forward EPS estimate: ${forward_eps:.2f}"
    elif trailing_eps is not None:
        guidance["earnings_guidance"] = f"Trailing EPS: ${trailing_eps:.2f}"

    if rec_key and num_analysts:
        guidance["commentary"] = f"Analyst consensus: {rec_key} ({num_analysts} analysts)."
        if target_mean and current_price:
            upside = (target_mean - current_price) / current_price * 100
            if target_low is not None and target_high is not None:
                guidance["commentary"] += f" Price target range: ${target_low:.0f}–${target_high:.0f} (mean ${target_mean:.0f}, {'+' if upside > 0 else ''}{upside:.0f}% from current ${current_price:.2f})."
            else:
                guidance["commentary"] += f" Mean price target: ${target_mean:.0f} ({'+' if upside > 0 else ''}{upside:.0f}% from current ${current_price:.2f})."
    else:
        guidance["commentary"] = "Limited analyst coverage available."

    # Build forward outlook
    outlook_parts = []
    if rev_growth is not None:
        outlook_parts.append(f"revenue {'growing' if rev_growth > 0 else 'declining'} at {rev_growth*100:.1f}%")
    if earnings_growth is not None:
        outlook_parts.append(f"earnings {'up' if earnings_growth > 0 else 'down'} {abs(earnings_growth)*100:.1f}%")
    if rec_key:
        outlook_parts.append(f"analyst consensus is '{rec_key}'")

    forward_outlook = f"With {', '.join(outlook_parts)}, {company_name} shows {'positive' if tone == 'bullish' else 'mixed' if tone == 'neutral' else 'challenging'} forward momentum." if outlook_parts else f"{company_name} outlook data is limited."

    return {
        "agent_name": "Earnings Call",
        "agent_index": 5,
        "status": "completed",
        "data": {
            "summary": f"{company_name} reported revenue of {_fmt_billions(quarterly[0].get('revenue'))} with net income of {_fmt_billions(quarterly[0].get('netIncome'))} in its most recent period. {'EPS: $' + f'{trailing_eps:.2f}.' if trailing_eps else ''}" if quarterly else "Earnings data unavailable.",
            "management_tone": tone,
            "key_themes": themes,
            "guidance": guidance,
            "analyst_concerns": concerns,
            "forward_outlook": forward_outlook,
        },
    }


def _calc_rev_growth(income: list) -> float | None:
    if income and len(income) >= 2:
        curr = income[0].get("revenue", 0) or 0
        prev = income[1].get("revenue", 0) or 0
        if prev:
            return (curr - prev) / prev
    return None


def _fetch_peer_yfinance(symbol: str) -> dict:
    """Fetch peer metrics from yfinance (no API limit, covers most tickers)."""
    try:
        t = yf.Ticker(symbol)
        raw = t.info
        info = raw if isinstance(raw, dict) and raw else {}

        name = info.get("shortName") or info.get("longName") or symbol
        mcap = info.get("marketCap")
        pe = info.get("trailingPE") or info.get("forwardPE")
        margin = info.get("profitMargins")
        rev_growth = info.get("revenueGrowth")

        return {
            "symbol": symbol,
            "company_name": name,
            "market_cap": _fmt_billions(mcap) if mcap else None,
            "pe_ratio": _fmt_ratio(pe) if pe else None,
            "revenue_growth": _fmt_pct(rev_growth) if rev_growth is not None else None,
            "margin": _fmt_pct(margin) if margin is not None else None,
        }
    except Exception as e:
        logger.warning("yfinance peer fetch failed for %s: %s", symbol, e)
        return {"symbol": symbol}


async def _get_peer_data(symbol: str) -> dict:
    """Fetch peer metrics using yfinance (primary) with FMP fallback.

    yfinance has no daily API limit and covers most tickers reliably.
    Only falls back to FMP if yfinance returns nothing useful.
    """
    # Run yfinance in thread pool (it's synchronous)
    loop = asyncio.get_event_loop()
    yf_data = await loop.run_in_executor(None, _fetch_peer_yfinance, symbol)

    mcap = yf_data.get("market_cap")
    pe = yf_data.get("pe_ratio")
    margin = yf_data.get("margin")
    rev_growth = yf_data.get("revenue_growth")
    name = yf_data.get("company_name", symbol)

    # If yfinance got nothing useful, try FMP as fallback
    all_none = mcap is None and pe is None and margin is None and rev_growth is None
    if all_none:
        try:
            prof, rats, income = await asyncio.gather(
                _safe_fetch(fmp.get_profile(symbol), {}),
                _safe_fetch(fmp.get_ratios(symbol, "annual", 1)),
                _safe_fetch(fmp.get_income_statement(symbol, "annual", 2)),
            )
            r = rats[0] if rats else {}
            if isinstance(prof, dict) and prof:
                name = prof.get("companyName", symbol)
                mcap = _fmt_billions(prof.get("marketCap")) if prof.get("marketCap") else None
            pe_val = r.get("priceToEarningsRatio")
            margin_val = r.get("netProfitMargin")
            rg = _calc_rev_growth(income) if income else None
            pe = _fmt_ratio(pe_val) if pe_val else None
            margin = _fmt_pct(margin_val) if margin_val else None
            rev_growth = _fmt_pct(rg) if rg is not None else None
        except Exception as e:
            logger.warning("FMP fallback failed for %s: %s", symbol, e)

    return {
        "symbol": symbol,
        "company_name": name,
        "market_cap": mcap or "N/A",
        "pe_ratio": pe or "N/A",
        "revenue_growth": rev_growth or "N/A",
        "margin": margin or "N/A",
        "assessment": "",
    }


async def _build_sector_peers(ticker: str, profile: dict, peers_raw: list, ratios: dict, income_annual: list | None = None, yf_info: dict | None = None) -> dict:
    yf_info = yf_info or {}
    target_pe = ratios.get("priceToEarningsRatio") or yf_info.get("trailingPE") or yf_info.get("forwardPE")
    target_rev_growth = _calc_rev_growth(income_annual) if income_annual else yf_info.get("revenueGrowth")
    target_margin = ratios.get("netProfitMargin") or yf_info.get("profitMargins")

    peer_comparison = [{
        "symbol": ticker,
        "company_name": profile.get("companyName", ticker),
        "market_cap": _fmt_billions(profile.get("marketCap") or yf_info.get("marketCap")),
        "pe_ratio": _fmt_ratio(target_pe) if target_pe else "N/A",
        "revenue_growth": _fmt_pct(target_rev_growth) if target_rev_growth is not None else "N/A",
        "margin": _fmt_pct(target_margin) if target_margin is not None else "N/A",
        "assessment": "Target company",
    }]

    if peers_raw:
        # FMP stock-peers can return [{"symbol": "X", "peersList": [...]}] or [{"symbol": "X"}, ...]
        peer_symbols = []
        for p in peers_raw:
            if isinstance(p, dict) and "peersList" in p:
                peer_symbols.extend(p["peersList"][:6])
            elif isinstance(p, dict) and "symbol" in p:
                peer_symbols.append(p["symbol"])
            elif isinstance(p, str):
                peer_symbols.append(p)
        # Exclude the target itself, take more candidates so we can filter empties
        peer_symbols = [s for s in peer_symbols if s != ticker][:6]
        if peer_symbols:
            peer_data = await asyncio.gather(
                *[_get_peer_data(s) for s in peer_symbols],
                return_exceptions=True,
            )
            for pd_item in peer_data:
                if isinstance(pd_item, Exception):
                    logger.warning("Peer data fetch failed: %s", pd_item)
                    continue
                # Skip peers where ALL metrics are N/A — useless rows
                has_data = any(
                    pd_item.get(k) not in (None, "N/A")
                    for k in ("market_cap", "pe_ratio", "revenue_growth", "margin")
                )
                if has_data:
                    peer_comparison.append(pd_item)
                else:
                    logger.info("Skipping peer %s — no data available", pd_item.get("symbol"))
            # Cap at 4 peers with actual data
            peer_comparison = peer_comparison[:5]  # 1 target + 4 peers

    # Build dynamic tailwinds/headwinds from actual data
    tailwinds = []
    headwinds = []

    yf_info = yf_info or {}

    mcap = profile.get("marketCap", 0) or 0
    rev_growth_val = yf_info.get("revenueGrowth")
    earnings_growth = yf_info.get("earningsGrowth")
    profit_margins = yf_info.get("profitMargins")
    op_margins = yf_info.get("operatingMargins")
    beta = yf_info.get("beta") or profile.get("beta")
    rec_key = yf_info.get("recommendationKey", "")
    target_price = yf_info.get("targetMeanPrice")
    current_price = yf_info.get("currentPrice")
    fcf = yf_info.get("freeCashflow")
    roe = yf_info.get("returnOnEquity")
    dividend_yield = yf_info.get("dividendYield")

    # Tailwinds (positive signals)
    if rev_growth_val is not None and rev_growth_val > 0.05:
        tailwinds.append(f"Revenue growing at {rev_growth_val*100:.1f}% YoY — strong top-line momentum")
    if earnings_growth is not None and earnings_growth > 0.1:
        tailwinds.append(f"Earnings growing at {earnings_growth*100:.1f}% YoY")
    if profit_margins is not None and profit_margins > 0.15:
        tailwinds.append(f"Healthy profit margins of {profit_margins*100:.1f}%")
    if fcf is not None and fcf > 0:
        tailwinds.append(f"Positive free cash flow of {_fmt_billions(fcf)}")
    if roe is not None and roe > 0.15:
        tailwinds.append(f"Strong return on equity of {roe*100:.1f}%")
    if mcap > 100e9:
        tailwinds.append(f"Large-cap stability ({_fmt_billions(mcap)} market cap)")
    elif mcap > 10e9:
        tailwinds.append(f"Mid-cap growth potential ({_fmt_billions(mcap)} market cap)")
    if dividend_yield is not None and dividend_yield > 0.02:
        tailwinds.append(f"Dividend yield of {dividend_yield*100:.1f}% provides income")
    if rec_key in ("buy", "strongBuy") and target_price and current_price:
        upside = (target_price - current_price) / current_price * 100
        if upside > 5:
            tailwinds.append(f"Analyst consensus: {rec_key} with {upside:.0f}% upside to ${target_price:.0f} target")

    # Headwinds (negative signals)
    if rev_growth_val is not None and rev_growth_val < 0:
        headwinds.append(f"Revenue declining {rev_growth_val*100:.1f}% YoY — top-line contraction")
    if earnings_growth is not None and earnings_growth < -0.1:
        headwinds.append(f"Earnings declining {earnings_growth*100:.1f}% YoY")
    if profit_margins is not None and profit_margins < 0:
        headwinds.append(f"Negative profit margins ({profit_margins*100:.1f}%) — not yet profitable")
    elif profit_margins is not None and profit_margins < 0.05:
        headwinds.append(f"Thin margins of {profit_margins*100:.1f}% — vulnerable to cost pressures")
    if beta and beta > 1.5:
        headwinds.append(f"High beta ({beta:.2f}) means amplified market swings")
    if fcf is not None and fcf < 0:
        headwinds.append(f"Negative free cash flow of {_fmt_billions(fcf)} — cash burn")
    if roe is not None and roe < 0:
        headwinds.append(f"Negative ROE ({roe*100:.1f}%) — destroying shareholder value")
    if rec_key in ("sell", "strongSell"):
        headwinds.append(f"Analyst consensus: {rec_key}")
    if target_price and current_price and target_price < current_price:
        downside = (target_price - current_price) / current_price * 100
        headwinds.append(f"Trading above analyst target (${target_price:.0f}, {downside:.0f}% downside)")

    # Ensure at least 1 of each
    if not tailwinds:
        tailwinds.append(f"Listed on {profile.get('exchangeFullName', 'major exchange')}")
    if not headwinds:
        headwinds.append("General macroeconomic and competitive risks")

    pe_str = _fmt_ratio(target_pe) if target_pe else "N/A"

    return {
        "agent_name": "Sector & Peers",
        "agent_index": 6,
        "status": "completed",
        "data": {
            "sector_overview": f"{profile.get('companyName', ticker)} operates in the {profile.get('sector', 'N/A')} sector, specifically in {profile.get('industry', 'N/A')}. The company is listed on {profile.get('exchangeFullName', 'N/A')}.",
            "tailwinds": tailwinds,
            "headwinds": headwinds,
            "peer_comparison": peer_comparison,
            "relative_valuation": f"{profile.get('companyName', ticker)} trades at a P/E of {pe_str} with a market cap of {_fmt_billions(profile.get('marketCap'))}. Compare against peers above for relative positioning.",
        },
    }


def _build_cross_signals(
    ticker: str,
    insider_data: list[dict],
    congress_all: list[dict],
    news_headlines: list[dict],
) -> dict:
    """Process cross-signal data sources into a compact summary for Agent 7.

    Returns a dict with insider, congress, and news signal summaries.
    Each section is structured so the LLM can synthesize across signals.
    """
    signals: dict = {}

    # --- Insider trading summary ---
    if insider_data:
        purchases = [t for t in insider_data if t.get("transaction_type") == "Purchase"]
        sales = [t for t in insider_data if t.get("transaction_type") == "Sale"]
        total_buy_value = sum(t.get("value") or 0 for t in purchases)
        total_sell_value = sum(t.get("value") or 0 for t in sales)
        net_value = total_buy_value - total_sell_value

        # Recent notable trades (top 5 by value)
        notable = sorted(
            [t for t in insider_data if t.get("value")],
            key=lambda t: abs(t["value"]),
            reverse=True,
        )[:5]
        notable_compact = [
            {
                "insider": t.get("insider", "Unknown"),
                "type": t.get("transaction_type", ""),
                "value": t.get("value"),
                "date": t.get("date", ""),
            }
            for t in notable
        ]

        signals["insider"] = {
            "total_transactions": len(insider_data),
            "purchases": len(purchases),
            "sales": len(sales),
            "net_value": net_value,
            "signal": "Bullish" if net_value > 0 else "Bearish" if net_value < 0 else "Neutral",
            "notable_trades": notable_compact,
        }

    # --- Congress trading summary ---
    ticker_upper = ticker.upper()
    congress_filtered = [
        t for t in congress_all
        if t.get("Ticker", "").upper() == ticker_upper
    ]
    if congress_filtered:
        congress_filtered.sort(
            key=lambda x: x.get("TransactionDate", ""), reverse=True,
        )
        recent = congress_filtered[:10]

        buys = sum(1 for t in recent if "purchase" in t.get("Transaction", "").lower())
        sells = sum(1 for t in recent if "sale" in t.get("Transaction", "").lower())

        congress_compact = [
            {
                "representative": t.get("Representative", "Unknown"),
                "party": t.get("Party", ""),
                "transaction": t.get("Transaction", ""),
                "amount": t.get("Range", ""),
                "date": t.get("TransactionDate", ""),
            }
            for t in recent[:5]
        ]

        signals["congress"] = {
            "total_trades": len(congress_filtered),
            "recent_buys": buys,
            "recent_sells": sells,
            "signal": "Bullish" if buys > sells else "Bearish" if sells > buys else "Neutral",
            "recent_trades": congress_compact,
        }

    # --- News sentiment summary ---
    if news_headlines:
        sentiment = _keyword_sentiment(news_headlines)
        signals["news"] = {
            "headline_count": len(news_headlines),
            "overall_score": sentiment.get("overall_score", 5),
            "overall_label": sentiment.get("overall_label", "neutral"),
            "recent_headlines": [
                h.get("title", "")[:100] for h in news_headlines[:5]
            ],
        }

    return signals


async def _build_green_red_flags(ticker: str, profile: dict, annual: list, ratios: dict, metrics: dict, bs: dict, cf: dict, yf_info: dict | None = None, cross_signals: dict | None = None) -> dict:
    green_flags = []
    red_flags = []

    company_name = profile.get("companyName", ticker)
    yf_flags = yf_info or {}

    # --- Revenue trend (FMP) ---
    if annual and len(annual) >= 2:
        rev_curr = annual[0].get("revenue", 0) or 0
        rev_prev = annual[1].get("revenue", 0) or 0
        if rev_prev:
            growth = (rev_curr - rev_prev) / rev_prev * 100
            if growth > 0:
                green_flags.append({"flag": f"Revenue growth of {growth:.1f}% YoY", "evidence": f"Revenue: {_fmt_billions(rev_curr)} vs prior year {_fmt_billions(rev_prev)}.", "significance": "High" if growth > 10 else "Medium"})
            else:
                red_flags.append({"flag": f"Revenue decline of {growth:.1f}% YoY", "evidence": f"Revenue: {_fmt_billions(rev_curr)} vs prior year {_fmt_billions(rev_prev)}.", "significance": "High" if growth < -10 else "Medium"})

    # --- Profitability (FMP ratios with yfinance fallback) ---
    net_margin = ratios.get("netProfitMargin") or yf_flags.get("profitMargins")
    if net_margin is not None:
        if net_margin > 0.15:
            green_flags.append({"flag": f"Strong net margin of {_fmt_pct(net_margin)}", "evidence": "Demonstrates pricing power and operational efficiency.", "significance": "High"})
        elif net_margin < 0:
            red_flags.append({"flag": f"Negative net margin of {_fmt_pct(net_margin)}", "evidence": "Company is not profitable.", "significance": "High"})
        elif net_margin < 0.05:
            red_flags.append({"flag": f"Thin net margin of {_fmt_pct(net_margin)}", "evidence": "Low profitability may indicate competitive pressure.", "significance": "Medium"})

    # --- Cash flow (FMP with yfinance fallback) ---
    ocf = cf.get("operatingCashFlow", 0) or yf_flags.get("operatingCashflow", 0) or 0
    if ocf > 0:
        green_flags.append({"flag": f"Positive operating cash flow of {_fmt_billions(ocf)}", "evidence": "Healthy cash generation from operations.", "significance": "High" if ocf > 1e9 else "Medium"})
    else:
        red_flags.append({"flag": "Negative operating cash flow", "evidence": f"OCF: {_fmt_billions(ocf)}. Company is burning cash.", "significance": "High"})

    # --- Free cash flow (yfinance) ---
    fcf = yf_flags.get("freeCashflow")
    if fcf is not None:
        if fcf > 0:
            green_flags.append({"flag": f"Positive free cash flow of {_fmt_billions(fcf)}", "evidence": "Generates cash after all capital expenditures.", "significance": "High" if fcf > 1e9 else "Medium"})
        else:
            red_flags.append({"flag": f"Negative free cash flow of {_fmt_billions(fcf)}", "evidence": "Capital spending exceeds cash generation — reliant on external financing.", "significance": "High"})

    # --- Leverage (FMP balance sheet with yfinance fallback) ---
    total_debt = bs.get("totalDebt", 0) or yf_flags.get("totalDebt", 0) or 0
    total_equity = bs.get("totalStockholdersEquity", 0) or 0
    de_from_yf = yf_flags.get("debtToEquity")
    if total_equity and total_debt:
        de = total_debt / total_equity
    elif de_from_yf is not None:
        de = de_from_yf / 100  # yfinance returns as percentage
    else:
        de = None
    if de is not None:
        if de < 0.5:
            green_flags.append({"flag": f"Very low leverage (D/E: {de:.2f})", "evidence": f"Debt: {_fmt_billions(total_debt)}, Equity: {_fmt_billions(total_equity)}.", "significance": "Medium"})
        elif de > 2:
            red_flags.append({"flag": f"High leverage (D/E: {de:.2f})", "evidence": f"Debt: {_fmt_billions(total_debt)}, Equity: {_fmt_billions(total_equity)}.", "significance": "High"})

    # --- Liquidity (FMP ratios) ---
    cr = ratios.get("currentRatio")
    if cr and cr > 2:
        green_flags.append({"flag": f"Strong liquidity (current ratio: {cr:.2f})", "evidence": "Ample short-term liquidity buffer.", "significance": "Medium"})
    elif cr and cr < 1:
        red_flags.append({"flag": f"Weak liquidity (current ratio: {cr:.2f})", "evidence": "May struggle to meet short-term obligations.", "significance": "High"})

    # --- Earnings growth (yfinance) ---
    earnings_growth = yf_flags.get("earningsGrowth")
    if earnings_growth is not None:
        if earnings_growth > 0.15:
            green_flags.append({"flag": f"Earnings growing {earnings_growth*100:.1f}% YoY", "evidence": "Strong bottom-line momentum.", "significance": "High"})
        elif earnings_growth < -0.15:
            red_flags.append({"flag": f"Earnings declining {earnings_growth*100:.1f}% YoY", "evidence": "Significant deterioration in profitability.", "significance": "High"})

    # --- ROE (yfinance) ---
    roe = yf_flags.get("returnOnEquity")
    if roe is not None:
        if roe > 0.2:
            green_flags.append({"flag": f"High return on equity ({roe*100:.1f}%)", "evidence": "Efficient use of shareholder capital.", "significance": "Medium"})
        elif roe < 0:
            red_flags.append({"flag": f"Negative ROE ({roe*100:.1f}%)", "evidence": "Company is destroying shareholder value.", "significance": "High"})

    # --- Analyst consensus (yfinance) ---
    rec_key = yf_flags.get("recommendationKey", "")
    target_mean = yf_flags.get("targetMeanPrice")
    current_price = yf_flags.get("currentPrice")
    if rec_key and target_mean and current_price:
        upside = (target_mean - current_price) / current_price * 100
        if rec_key in ("buy", "strongBuy") and upside > 10:
            green_flags.append({"flag": f"Analyst consensus: {rec_key} ({upside:.0f}% upside)", "evidence": f"Mean price target: ${target_mean:.0f} vs current ${current_price:.2f}.", "significance": "Medium"})
        elif rec_key in ("sell", "strongSell"):
            red_flags.append({"flag": f"Analyst consensus: {rec_key}", "evidence": f"Analysts are bearish. Target: ${target_mean:.0f} vs current ${current_price:.2f}.", "significance": "Medium"})
        elif upside < -10:
            red_flags.append({"flag": f"Trading {abs(upside):.0f}% above analyst target", "evidence": f"Mean target: ${target_mean:.0f} vs current ${current_price:.2f}. May be overvalued.", "significance": "Medium"})

    # --- Short interest (yfinance) ---
    short_pct = yf_flags.get("shortPercentOfFloat")
    if short_pct is not None:
        if short_pct > 0.15:
            red_flags.append({"flag": f"Heavy short interest ({short_pct*100:.1f}% of float)", "evidence": "Significant bearish bets against the stock.", "significance": "High"})
        elif short_pct > 0.08:
            red_flags.append({"flag": f"Elevated short interest ({short_pct*100:.1f}% of float)", "evidence": "Above-average short selling activity.", "significance": "Medium"})
        elif short_pct < 0.02:
            green_flags.append({"flag": f"Low short interest ({short_pct*100:.1f}% of float)", "evidence": "Bears are not actively betting against this stock.", "significance": "Low"})

    # --- Insider ownership (yfinance) ---
    insider_pct = yf_flags.get("heldPercentInsiders")
    if insider_pct is not None and insider_pct > 0.05:
        green_flags.append({"flag": f"Insider ownership at {insider_pct*100:.1f}%", "evidence": "Management has meaningful skin in the game.", "significance": "Medium" if insider_pct > 0.1 else "Low"})

    # --- Dividend (yfinance) ---
    div_yield = yf_flags.get("dividendYield")
    if div_yield is not None and div_yield > 0.02:
        green_flags.append({"flag": f"Dividend yield of {div_yield*100:.1f}%", "evidence": "Provides regular income to shareholders.", "significance": "Medium" if div_yield > 0.03 else "Low"})

    # --- Cross-signal derived flags (insider trading, congress, news) ---
    if cross_signals:
        insider = cross_signals.get("insider")
        if insider:
            net_val = insider.get("net_value", 0)
            purchases = insider.get("purchases", 0)
            sales = insider.get("sales", 0)
            if net_val > 0 and purchases > 0:
                green_flags.append({
                    "flag": f"Net insider buying ({purchases} purchases vs {sales} sales)",
                    "evidence": f"Net insider buy value: {_fmt_billions(net_val)}. Insiders are putting their own money in.",
                    "significance": "High" if net_val > 1_000_000 else "Medium",
                })
            elif net_val < 0 and sales > 0:
                red_flags.append({
                    "flag": f"Net insider selling ({sales} sales vs {purchases} purchases)",
                    "evidence": f"Net insider sell value: {_fmt_billions(abs(net_val))}. Insiders are reducing their exposure.",
                    "significance": "High" if abs(net_val) > 5_000_000 else "Medium",
                })

        congress = cross_signals.get("congress")
        if congress:
            total_trades = congress.get("total_trades", 0)
            recent_buys = congress.get("recent_buys", 0)
            recent_sells = congress.get("recent_sells", 0)
            if total_trades > 0:
                congress_signal = congress.get("signal", "Neutral")
                if congress_signal == "Bullish":
                    green_flags.append({
                        "flag": f"Congress members buying ({recent_buys} buys in {total_trades} total trades)",
                        "evidence": "Politicians with access to briefings are net buyers.",
                        "significance": "Medium",
                    })
                elif congress_signal == "Bearish":
                    red_flags.append({
                        "flag": f"Congress members selling ({recent_sells} sells in {total_trades} total trades)",
                        "evidence": "Politicians with access to briefings are net sellers.",
                        "significance": "Medium",
                    })

        news = cross_signals.get("news")
        if news:
            news_score = news.get("overall_score", 5)
            news_label = news.get("overall_label", "neutral")
            headline_count = news.get("headline_count", 0)
            if headline_count > 0:
                if news_score >= 7:
                    green_flags.append({
                        "flag": f"Positive news sentiment (score: {news_score}/10)",
                        "evidence": f"Recent headlines ({headline_count}) lean {news_label}.",
                        "significance": "Medium",
                    })
                elif news_score <= 3:
                    red_flags.append({
                        "flag": f"Negative news sentiment (score: {news_score}/10)",
                        "evidence": f"Recent headlines ({headline_count}) lean {news_label}.",
                        "significance": "Medium",
                    })

    # Ensure minimums
    if not green_flags:
        green_flags.append({"flag": f"Listed on {profile.get('exchangeFullName', 'major exchange')}", "evidence": f"Publicly traded with regulatory oversight.", "significance": "Low"})
    if not red_flags:
        red_flags.append({"flag": "No significant red flags identified", "evidence": "Financial health metrics are solid across the board.", "significance": "Low"})

    # Score
    green_weight = sum(3 if f["significance"] == "High" else 2 if f["significance"] == "Medium" else 1 for f in green_flags)
    red_weight = sum(3 if f["significance"] == "High" else 2 if f["significance"] == "Medium" else 1 for f in red_flags)
    total = green_weight + red_weight
    score = round(green_weight / total * 10) if total else 5

    data = {
        "overall_score": min(max(score, 1), 10),
        "overall_assessment": f"{company_name} scores {min(max(score, 1), 10)}/10 with {len(green_flags)} bullish and {len(red_flags)} bearish signals. {'Strong investment case.' if score >= 7 else 'Mixed signals — proceed with caution.' if score >= 4 else 'Significant concerns outweigh positives.'}",
        "green_flags": green_flags,
        "red_flags": red_flags,
        "investment_thesis_summary": f"{company_name} {'has strong fundamentals' if score >= 7 else 'shows mixed signals' if score >= 4 else 'faces significant headwinds'}. Top strength: {green_flags[0]['flag'].lower()}. Top risk: {red_flags[0]['flag'].lower()}.",
    }

    # Attach cross-signal summaries for frontend display and LLM context
    if cross_signals:
        data["cross_signals"] = cross_signals

    return {
        "agent_name": "Green/Red Flags",
        "agent_index": 7,
        "status": "completed",
        "data": data,
    }

"""AI Investment Summary endpoint.

Synthesizes all 7 report agent outputs into a structured analyst recommendation:
- Rating (Strong Buy → Strong Sell)
- 12-month price target (bear / base / bull)
- Investment thesis headline + paragraph
- Top 3 bull and bear points grounded in the report data
- Key upcoming catalysts with timeframes

Cached 1 hour per ticker — regenerating on every page view would be wasteful.
Uses the same OpenAI client pattern as chat.py.
"""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel

from ..config import settings
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache: ticker -> (timestamp, summary_dict)
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hour

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = """You are a Managing Director of Equity Research at a top-tier global investment bank (think Goldman Sachs, Morgan Stanley). You have 20+ years of experience writing initiating coverage reports.

Your job is to synthesize a comprehensive research report into a crisp, decisive investment recommendation. You are known for being bold, specific, and right — not hedging everything with "could" and "may".

Your output must be grounded in the data provided. Every claim should trace back to a number in the report."""

_USER_TEMPLATE = """Analyze this comprehensive research report on {ticker} ({company_name}) and produce a structured investment recommendation.

=== FULL RESEARCH REPORT ===
{report_data}
=== END REPORT ===

Return ONLY a valid JSON object with EXACTLY this structure (no extra keys, no markdown):
{{
  "rating": "Strong Buy" | "Buy" | "Hold" | "Sell" | "Strong Sell",
  "conviction": "High" | "Medium" | "Low",
  "summary_headline": "<12–18 word punchy headline capturing the core investment narrative, e.g. 'Services Flywheel Accelerating; AI Integration Creates Next Re-Rating Catalyst'>",
  "investment_thesis": "<2–3 sentence bottom-line thesis. Be specific: cite exact revenue figures, margins, or multiples from the report. Commit to a view.>",
  "price_target_low": <12-month bear-case price target as a number, or null if cannot determine>,
  "price_target_mid": <12-month base-case price target as a number, or null if cannot determine>,
  "price_target_high": <12-month bull-case price target as a number, or null if cannot determine>,
  "current_price": <current stock price as a number pulled from the report, or null>,
  "bull_case": [
    "<Bull point 1 — one specific sentence with a number from the report>",
    "<Bull point 2 — one specific sentence with a number from the report>",
    "<Bull point 3 — one specific sentence with a number from the report>"
  ],
  "bear_case": [
    "<Bear point 1 — one specific sentence with a number or risk from the report>",
    "<Bear point 2>",
    "<Bear point 3>"
  ],
  "key_catalysts": [
    "<Catalyst 1 with timeframe, e.g. 'Q3 FY2025 earnings report (August 2025)'>",
    "<Catalyst 2 with timeframe>",
    "<Catalyst 3 with timeframe — optional, omit if not enough data>"
  ],
  "time_horizon": "12 months",
  "sector": "<sector of the company>"
}}

Rules:
- Price targets: derive from P/E, EV/EBITDA, or DCF multiples visible in the report. If no price data in report, use null.
- Each bull/bear point must cite a specific metric or fact (revenue %, margin %, ratio, etc.)
- Each catalyst must include a timeframe (Q-number, month+year, or "H1/H2 YYYY")
- Headline should read like a research note headline, not a generic description
- Do NOT say "may", "could", "might" — commit to a view
- If the company has major red flags, rate it appropriately (Sell / Strong Sell)
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_context(report_data: dict, ticker: str) -> tuple[str, str]:
    """Extract company name and compact report JSON, same as chat.py."""
    company_name = ticker.upper()
    sections: dict[str, dict] = {}

    for key, val in report_data.items():
        if isinstance(val, dict):
            agent_name = val.get("agent_name", key)
            data = val.get("data", val)
            sections[agent_name] = data
            if isinstance(data, dict) and data.get("company_name"):
                company_name = data["company_name"]

    order = [
        "Company Overview", "Financial Analysis", "Green/Red Flags",
        "Risk Analysis", "Earnings Call", "Sector & Peers", "Auditor Flags",
    ]
    ordered: dict = {}
    for name in order:
        if name in sections:
            ordered[name] = sections[name]
    for name, data in sections.items():
        if name not in ordered:
            ordered[name] = data

    compact = json.dumps(ordered, default=str, separators=(",", ":"))
    MAX_CHARS = 55000
    if len(compact) > MAX_CHARS:
        compact = compact[:MAX_CHARS] + "...}"

    return company_name, compact


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class SummaryRequest(BaseModel):
    report_data: dict


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/api/reports/{ticker}/ai-summary")
async def generate_ai_summary(
    ticker: str,
    body: SummaryRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a structured AI investment recommendation for a completed report."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    upper = ticker.upper()

    # Return cached result if fresh
    now = time.time()
    if upper in _cache:
        ts, data = _cache[upper]
        if now - ts < _CACHE_TTL:
            return data

    company_name, report_context = _extract_context(body.report_data, upper)

    prompt = _USER_TEMPLATE.format(
        ticker=upper,
        company_name=company_name,
        report_data=report_context,
    )

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=1200,
        )

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

        # Guarantee required keys exist
        result.setdefault("rating", "Hold")
        result.setdefault("conviction", "Medium")
        result.setdefault("summary_headline", "")
        result.setdefault("investment_thesis", "")
        result.setdefault("bull_case", [])
        result.setdefault("bear_case", [])
        result.setdefault("key_catalysts", [])
        result.setdefault("time_horizon", "12 months")
        result["ticker"] = upper
        result["company_name"] = company_name

        _cache[upper] = (now, result)
        logger.info("AI summary generated for %s — rating=%s", upper, result.get("rating"))
        return result

    except Exception as e:
        logger.exception("AI summary error for %s", upper)
        raise HTTPException(status_code=500, detail=f"AI summary generation failed: {e}")

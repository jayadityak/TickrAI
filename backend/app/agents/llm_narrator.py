"""LLM Narrative Enhancement Layer for TickrAI reports.

Takes the computed data from fmp_report_builder and enhances narrative text
fields using GPT-4o while preserving all numeric/structured data unchanged.

Graceful fallback: on ANY error, returns the original computed data.
"""

import asyncio
import copy
import json
import logging
import re

from openai import AsyncOpenAI, RateLimitError

from ..config import settings

logger = logging.getLogger(__name__)

# ── OpenAI client (lazy init) ──────────────────────────────────────────

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def llm_available() -> bool:
    return bool(settings.openai_api_key)


# ── Per-agent config: token budgets + temperature ──────────────────────
# Higher token budgets for data-rich sections; lower temperature for
# analytical/forensic agents; higher for narrative/voice-driven ones.

_AGENT_CONFIG: dict[str, dict] = {
    "Financial Analysis": {"max_tokens": 2400, "temperature": 0.25},
    "Green/Red Flags":    {"max_tokens": 2800, "temperature": 0.25},
    "Earnings Call":      {"max_tokens": 2000, "temperature": 0.35},
    "Company Overview":   {"max_tokens": 1800, "temperature": 0.35},
    "Sector & Peers":     {"max_tokens": 2000, "temperature": 0.30},
    "Risk Analysis":      {"max_tokens": 1800, "temperature": 0.20},
    "Auditor Flags":      {"max_tokens": 1600, "temperature": 0.20},
    # ETF sections
    "ETF Overview":       {"max_tokens": 1200, "temperature": 0.35},
}
_DEFAULT_AGENT_CONFIG = {"max_tokens": 1500, "temperature": 0.30}


# ── Sector benchmarks for calibrated analysis ─────────────────────────
# Lets the LLM say "above/below sector average" rather than just restating numbers.

_SECTOR_BENCHMARKS: dict[str, str] = {
    "Technology":          "net margin 15-25%, gross margin 65-85%, P/E 25-45x, rev growth 15-30%",
    "Communication Services": "net margin 10-22%, gross margin 55-75%, P/E 18-35x, rev growth 8-20%",
    "Healthcare":          "net margin 5-20%, gross margin 55-75%, P/E 20-35x, rev growth 8-18%",
    "Consumer Cyclical":   "net margin 3-8%, gross margin 30-50%, P/E 15-28x, rev growth 5-12%",
    "Consumer Defensive":  "net margin 5-12%, gross margin 30-55%, P/E 18-28x, rev growth 3-8%",
    "Industrials":         "net margin 5-12%, gross margin 25-45%, P/E 15-25x, rev growth 4-10%",
    "Financial Services":  "ROE 12-18%, P/B 1.0-2.5x, P/E 10-18x, net interest margin 2-4%",
    "Energy":              "net margin 5-15%, D/E 0.3-0.8x, P/E 10-20x, FCF yield 5-12%",
    "Basic Materials":     "net margin 5-15%, D/E 0.4-1.0x, P/E 12-22x, rev growth 3-8%",
    "Real Estate":         "FFO yield 5-8%, D/E 1.0-2.0x, P/FFO 15-25x",
    "Utilities":           "net margin 10-20%, D/E 1.0-2.0x, P/E 16-24x, dividend yield 3-5%",
    "Consumer Electronics": "net margin 3-8%, gross margin 30-50%, P/E 12-22x",
    "Biotechnology":       "R&D/revenue >30%, cash runway >18mo matters more than margin; P/S 3-15x typical",
    "Semiconductors":      "net margin 15-30%, gross margin 50-70%, P/E 20-40x, capex-intensive",
    "Software":            "net margin 15-30%, gross margin 70-85%, P/E 30-60x, FCF margin 20-35%",
}


def _sector_context(sector: str, industry: str) -> str:
    """Return a formatted sector benchmark block for LLM prompts."""
    # Try exact sector match, then partial
    benchmark = _SECTOR_BENCHMARKS.get(sector, "")
    if not benchmark:
        for key in _SECTOR_BENCHMARKS:
            if key.lower() in sector.lower() or sector.lower() in key.lower():
                benchmark = _SECTOR_BENCHMARKS[key]
                break
    # Also try industry-level overrides
    if not benchmark:
        for key in _SECTOR_BENCHMARKS:
            if key.lower() in industry.lower():
                benchmark = _SECTOR_BENCHMARKS[key]
                break
    if not benchmark:
        return ""
    return (
        f"\n=== SECTOR CONTEXT ({sector} — {industry}) ===\n"
        f"Typical ranges: {benchmark}\n"
        f"Calibrate your analysis against these norms. "
        f"State explicitly whether this company is above or below sector average on each key metric.\n"
    )


# ── Shared system prompt ───────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Managing Director of Equity Research at TickrAI, covering global equities. \
You previously spent 15 years writing research at Goldman Sachs and Bernstein. \
Your reports are known for being decisive, data-grounded, and written for investors who need signal — not summaries.

Voice and style:
- Write like a seasoned sell-side analyst, not a textbook. Confident, direct, specific.
- Lead with what matters: the insight, the anomaly, the implication — not the data recap.
- Use precise financial language: "operating leverage", "FCF conversion", "multiple compression risk", \
"re-rating catalyst", "beat-and-raise", "margin inflection", "deceleration", "re-acceleration".
- Compare to peers, to history, to sector norms — context is what separates analysis from description.
- Be opinionated. "Revenue growth is decelerating" is a fact. \
"That deceleration, combined with multiple expansion YTD, creates asymmetric downside risk" is analysis.
- Don't hedge excessively. If the data is mixed, say so directly: \
"The bull case depends on X; if X fails, the stock has Y% downside."
- When you have pre-computed trend signals, USE them — do not restate the raw numbers, interpret the trend.

Rules:
- Ground every claim in the specific data provided. Never fabricate numbers.
- Write in present tense for current state, past tense for historical.
- Be concise: every sentence must earn its place.
- Return valid JSON matching the exact schema specified."""


# ── Per-agent prompt builders ──────────────────────────────────────────

def _prompt_overview(ticker: str, company_name: str, sector: str, industry: str, data: dict, filing_context: str = "") -> str:
    filing_block = f"\n=== SEC 10-K BUSINESS DESCRIPTION (authoritative source) ===\n{filing_context}\n" if filing_context else ""

    # Extract executive and segment data for the LLM to use
    execs = data.get("key_executives", [])
    segments = data.get("revenue_segments", [])
    exec_block = ""
    if execs:
        exec_block = f"\n=== KEY EXECUTIVES ===\n" + "\n".join(f"- {e}" for e in execs[:4]) + "\n"
    segment_block = ""
    if segments and any(s.get("revenue") for s in segments):
        seg_lines = [f"- {s['name']}: {s.get('revenue', 'N/A')}" for s in segments[:5]]
        segment_block = f"\n=== REVENUE SEGMENTS (most recent year) ===\n" + "\n".join(seg_lines) + "\n"

    return f"""Write initiating-coverage-style narrative for {company_name} ({ticker}), a {industry} company in the {sector} sector.

=== COMPUTED DATA ===
{json.dumps({k: v for k, v in data.items() if k not in ("key_executives", "revenue_segments")}, indent=2)}
{filing_block}{exec_block}{segment_block}
=== INSTRUCTIONS ===
Think like you're writing the opening page of a 20-page initiation report. Investors already know the company exists — tell them what actually matters.
{"Ground the business description in the 10-K text above — it is the authoritative source." if filing_context else ""}
{"Reference revenue segments to identify which business line is the primary growth driver and which is mature/declining." if segment_block else ""}
{"Reference the executive team composition — does the company have stable, experienced leadership or recent turnover?" if exec_block else ""}

Return a JSON object with exactly these keys:
{{
  "business_description": "<2-4 sentences. Skip generic descriptions. Lead with what makes this business competitively defensible or uniquely positioned. Identify where it sits in its growth lifecycle (early hypergrowth, scaling, mature compounder, turnaround). Reference specific revenue drivers.{' Ground in the 10-K text.' if filing_context else ''}{' Identify the dominant revenue segment.' if segment_block else ''}>",
  "competitive_position": "<Analyst take on the moat: is it real, wide, narrowing? Cite specific advantages — switching costs, network effects, cost structure, brand, IP. Be honest about vulnerabilities. Reference market cap and sector positioning. Where does this company rank vs. peers — leader, challenger, niche player?>",
  "management_highlights": "<Specific assessment of leadership quality and track record.{' Reference the executives listed above by name and role.' if exec_block else ''} Have they executed on promises? What does their capital allocation history tell you about their priorities? Any red flags or green flags?>"
}}

Only return these 3 keys. Do not include other fields."""


def _prompt_financials(ticker: str, company_name: str, data: dict, filing_context: str = "") -> str:
    fmp_block = f"\n{filing_context}\n" if filing_context else ""
    has_targets   = "ANALYST PRICE TARGET" in filing_context
    has_estimates = "FORWARD ANALYST" in filing_context
    has_quality   = "QUALITY & VALUE" in filing_context
    has_trends    = "ANALYST PRE-ANALYSIS" in filing_context
    surprises     = data.get("earnings_surprises") or []
    has_surprises = len(surprises) >= 2
    beat_count    = sum(1 for s in surprises if isinstance(s.get("beat_pct"), (int, float)) and s["beat_pct"] > 0)
    dcf_val       = (data.get("dcf_valuation") or {})
    has_dcf       = bool(dcf_val.get("dcf_fair_value"))
    growth        = data.get("growth_rates") or {}
    has_growth    = bool(growth.get("revenue_10y_cumulative") or growth.get("revenue_5y_cumulative"))

    dcf_note = (
        f"DCF fair value ${dcf_val['dcf_fair_value']} vs. current ${dcf_val['current_price']} "
        f"({dcf_val['verdict']}). Is this premium/discount justified by growth durability?"
    ) if has_dcf else ""
    summary_dcf_hint  = f" Mention DCF: {dcf_val.get('verdict', '')}." if has_dcf else ""
    summary_tgt_hint  = " State analyst price target upside." if has_targets else ""
    analysis_cagr     = " Reference long-term CAGRs." if has_growth else ""
    analysis_val      = (f" Valuation — {dcf_note}") if has_dcf else " Valuation — what multiple does this business deserve vs. sector norms?"
    analysis_pt4      = " Earnings execution and guidance credibility." if has_surprises else analysis_val
    growth_instruction = (
        "You have 3Y/5Y/10Y per-share growth CAGRs in growth_rates — use them to characterise the "
        "business as a compounder, a maturing franchise, or a turnaround. Compare to what the market pays today."
    ) if has_growth else ""
    dcf_instruction   = f"VALUATION ANCHOR: {dcf_note}" if has_dcf else ""
    eps_instruction   = f"You have {len(surprises)} quarters of EPS data ({beat_count} beats). Assess execution quality." if has_surprises else ""

    return f"""Write a sell-side financial analysis for {company_name} ({ticker}).

=== COMPUTED FINANCIAL DATA ===
{json.dumps(data, indent=2)}
{fmp_block}
=== INSTRUCTIONS ===
This is the core of the research note. Don't recap the data — interpret it.
{"The PRE-ANALYSIS block above has already identified the key trends — reference them directly, don't restate the numbers." if has_trends else ""}
{"You have analyst price targets — cite the consensus upside/downside explicitly." if has_targets else ""}
{"You have forward consensus estimates — frame the growth story against what the street expects." if has_estimates else ""}
{"You have quality signals (ROE, ROIC, FCF yield) — compare to sector norms, make a statement about capital efficiency." if has_quality else ""}
{eps_instruction}
{growth_instruction}
{dcf_instruction}

Return a JSON object with exactly these keys:
{{
  "summary": "<2-3 sentences. Lead with the single most important financial signal. Cite exact numbers.{summary_tgt_hint}{summary_dcf_hint}>",
  "analysis": "<Analyst-grade narrative: (1) Revenue trajectory — accelerating or decelerating?{analysis_cagr} (2) Margin story — gross/operating/net trend and pricing power implication. (3) Cash flow quality and FCF conversion. (4){analysis_pt4} (5) The one specific factor that breaks the bull thesis — name it and quantify the downside. Numbers throughout.>"
}}"""


def _prompt_risk(ticker: str, company_name: str, data: dict, filing_context: str = "") -> str:
    risks = data.get("risks", [])
    compact = [{"category": r["category"], "severity": r["severity"],
                "current_desc": r.get("description", "")[:100]} for r in risks]
    filing_block = f"\n=== SEC 10-K RISK FACTORS (disclosed risks) ===\n{filing_context}\n" if filing_context else ""
    has_trends = "ANALYST PRE-ANALYSIS" in filing_context

    return f"""Rewrite risk descriptions for {company_name} ({ticker}). Overall risk: {data.get("overall_risk_level")}.
{filing_block}
{"Reference the trend signals in the PRE-ANALYSIS block — state whether each risk is improving, worsening, or stable based on the trend." if has_trends else ""}
Risks: {json.dumps(compact)}

Return JSON: {{"risks": [{{"category":"<same>","severity":<same>,"description":"<1-2 sentences: what this risk means for the business — is it worsening or improving?{'. Reference 10-K risk factors if relevant.' if filing_context else ''}>","evidence":"<key numbers with trend context>"}}]}}
Return exactly {len(risks)} risks, same order. Keep category and severity identical. Be concise."""


def _prompt_auditor(ticker: str, company_name: str, data: dict, filing_context: str = "") -> str:
    flags = data.get("flags", [])
    compact = [{"type": f["type"], "severity": f["severity"],
                "current_desc": f.get("description", "")[:100]} for f in flags]
    filing_block = f"\n=== SEC 10-K AUDITOR/CONTROLS SECTION ===\n{filing_context}\n" if filing_context else ""
    has_trends = "ANALYST PRE-ANALYSIS" in filing_context

    return f"""Write forensic accounting analysis for {company_name} ({ticker}).
{filing_block}
{"Use the trend data in the PRE-ANALYSIS block to assess whether financial quality is improving or deteriorating over time." if has_trends else ""}
Flags: {json.dumps(compact)}

Return JSON:
{{
  "summary": "<2-3 sentence forensic analyst brief. State clearly: is financial reporting quality improving, stable, or deteriorating?{' Reference auditor opinion from 10-K if available.' if filing_context else ''}>",
  "auditor_assessment": "<the specific area that warrants deepest scrutiny and why>",
  "flags": [{{"type":"<same>","severity":"<same>","description":"<forensic analysis: what this signal means about earnings quality or financial health>","recommendation":"<specific, actionable due diligence step>"}}]
}}
Return exactly {len(flags)} flags, same order. Keep type and severity identical. Be concise."""


def _prompt_earnings(ticker: str, company_name: str, data: dict, filing_context: str = "") -> str:
    filing_block = f"\n=== ACTUAL EARNINGS CALL / PRESS RELEASE (most recent) ===\n{filing_context}\n" if filing_context else ""
    has_transcript = bool(filing_context)
    has_trends = "ANALYST PRE-ANALYSIS" in filing_context

    # Extract quarterly trend data if available
    themes = data.get("key_themes", [])
    qt_themes = [t for t in themes if "Q-o-Q" in t or "→" in t or "YoY" in t or "quarter" in t.lower()]

    return f"""Write earnings analysis for {company_name} ({ticker}) as a buy-side analyst briefing a portfolio manager.

=== COMPUTED EARNINGS DATA ===
{json.dumps(data, indent=2)}
{filing_block}
=== INSTRUCTIONS ===
The PM has 30 seconds. Lead with what matters most.
{"Use the PRE-ANALYSIS trend block to establish whether this quarter represents acceleration or deceleration vs. the recent trend." if has_trends else ""}
{"The key_themes list contains Q-o-Q and YoY quarterly comparisons with specific quarter labels — reference them explicitly (e.g. 'Q3→Q4 sequential growth of X%)." if qt_themes else ""}
{"The transcript/press release above contains actual management language — quote it directly for forward guidance." if has_transcript else ""}

Return a JSON object with exactly these keys:
{{
  "summary": "<2-3 sentences. Open with the headline verdict: beat/miss/in-line on revenue and EPS, and whether this quarter represents acceleration or deceleration vs. the prior trend. Reference specific quarter labels (e.g. Q4 2024) if available.{' Quote management directly on the most important forward-looking comment.' if has_transcript else ''}>",
  "key_themes": ["<rewrite each theme as a crisp analyst observation — not a data point, but what the data implies. E.g. not 'Revenue grew 12%' but 'Revenue re-acceleration to 12% YoY (from 8% prior quarter) signals demand recovery.'>" ],
  "analyst_concerns": ["<rewrite each concern as a specific risk to monitor — what would have to happen for this concern to materialize, and what would be the magnitude of impact?>"],
  "forward_outlook": "<What should investors monitor over the next 1-2 quarters? Name the specific metric or event that proves or disproves the thesis. What's the bar for the next print?{' Reference guidance ranges from the transcript.' if has_transcript else ''}>",
  "guidance_commentary": "<Frame the consensus estimate picture: are estimates going up or down? What's the EPS power scenario if the company executes? What specific event would trigger a guidance cut?>"
}}
Return exactly {len(themes)} items in key_themes and {len(data.get("analyst_concerns", []))} items in analyst_concerns."""


def _prompt_sector(ticker: str, company_name: str, data: dict, sector_context_block: str = "") -> str:
    tailwinds = data.get("tailwinds", [])
    headwinds = data.get("headwinds", [])

    return f"""Write a peer comparison and relative valuation section for {company_name} ({ticker}).

=== COMPUTED PEER DATA ===
{json.dumps(data, indent=2)}
{sector_context_block}
=== INSTRUCTIONS ===
This section answers: "Why own this vs. the peer group?" Be specific about multiples and make a judgment.

Return a JSON object with exactly these keys:
{{
  "sector_overview": "<Position this company within its competitive landscape. Is it the sector leader, fastest grower, cheapest name, or highest quality? Reference the peer group specifically — who is the closest comparable and how does management execution compare? Identify whether the sector has tailwinds or headwinds affecting all names.{' Use the sector benchmark ranges to state explicitly where this company sits vs. peers.' if sector_context_block else ''}>",
  "tailwinds": ["<rewrite each tailwind as a specific, forward-looking catalyst with magnitude — not 'revenue growing' but 'revenue re-accelerating from 8%→12% YoY creates positive estimate revision risk'>", "<...>"],
  "headwinds": ["<rewrite each headwind as a specific risk with a plausible worst-case — not 'high beta' but 'beta of 2.1 means a 10% market selloff implies ~21% stock decline'>", "<...>"],
  "relative_valuation": "<Key question: is the valuation premium or discount justified? Compare specific multiples (P/E, EV/EBITDA, P/S) to peers with exact numbers from the data above. State explicitly: cheap vs. peers, fair, or expensive — and why. If it trades at a premium, what growth rate justifies it?>"
}}
Return exactly {len(tailwinds)} tailwinds and {len(headwinds)} headwinds."""


def _prompt_flags(ticker: str, company_name: str, data: dict, prior_sections: dict | None = None, sector_context_block: str = "") -> str:
    prior_context = ""
    cross_signal_context = ""
    if prior_sections:
        summaries = {}
        for name, section_data in prior_sections.items():
            if name == "cross_signals":
                continue
            if isinstance(section_data, dict):
                for key in ("summary", "overall_risk_level", "management_tone", "auditor_assessment"):
                    if key in section_data:
                        val = section_data[key]
                        summaries[f"{name} — {key}"] = val[:180] if isinstance(val, str) else val
        if summaries:
            prior_context = f"\nPrior findings: {json.dumps(summaries)}\n"

        cross = prior_sections.get("cross_signals")
        if cross and isinstance(cross, dict):
            parts = []
            insider = cross.get("insider")
            if insider:
                parts.append(
                    f"INSIDER TRADING: {insider.get('purchases', 0)} purchases, "
                    f"{insider.get('sales', 0)} sales, net value: ${insider.get('net_value', 0):,.0f}, "
                    f"signal: {insider.get('signal', 'N/A')}. "
                    f"Notable: {json.dumps(insider.get('notable_trades', [])[:3])}"
                )
            congress = cross.get("congress")
            if congress:
                parts.append(
                    f"CONGRESS TRADES: {congress.get('total_trades', 0)} total, "
                    f"{congress.get('recent_buys', 0)} buys / {congress.get('recent_sells', 0)} sells recent, "
                    f"signal: {congress.get('signal', 'N/A')}. "
                    f"Recent: {json.dumps(congress.get('recent_trades', [])[:3])}"
                )
            news = cross.get("news")
            if news:
                parts.append(
                    f"NEWS SENTIMENT: score {news.get('overall_score', 5)}/10 ({news.get('overall_label', 'neutral')}), "
                    f"{news.get('headline_count', 0)} headlines. "
                    f"Recent: {json.dumps(news.get('recent_headlines', [])[:3])}"
                )
            if parts:
                cross_signal_context = (
                    "\n=== CROSS-SIGNAL DATA (synthesize with fundamentals) ===\n"
                    + "\n".join(parts) + "\n"
                )

    green_flags = data.get("green_flags", [])
    red_flags = data.get("red_flags", [])
    compact_green = [{"flag": f["flag"], "significance": f["significance"]} for f in green_flags]
    compact_red   = [{"flag": f["flag"], "significance": f["significance"]} for f in red_flags]

    synthesis_instruction = ""
    if cross_signal_context:
        synthesis_instruction = """
CRITICAL — Cross-signal synthesis:
When writing overall_assessment and investment_thesis_summary, look for convergence and divergence:
- Insiders buying + congress buying + improving news = high-conviction bull signal → say so explicitly
- Insiders selling + bearish news + fundamental deterioration = high-conviction bear signal → say so explicitly
- Mixed signals → identify which signal is more informative and why (e.g. "insider buys of $2M carry more weight than 3 bearish headlines")
- Always call out the most significant cross-signal observation by name in your assessment
"""

    return f"""Write the investment scorecard verdict for {company_name} ({ticker}). Composite score: {data.get("overall_score")}/10.

This is the final word — the section where an analyst commits to a view. Don't summarize what came before. Synthesize it into actionable conclusions.
{prior_context}{cross_signal_context}{sector_context_block}
Signals identified:
GREEN: {json.dumps(compact_green)}
RED: {json.dumps(compact_red)}
{synthesis_instruction}
Return JSON:
{{
  "overall_assessment": "<2-3 sentences. Open with your verdict — are the bulls or bears in control of this story right now? Cite the 1-2 most decisive data points. If cross-signal data is present, incorporate what insiders/congress/news are telling you and whether they confirm or contradict the fundamentals.>",
  "investment_thesis_summary": "<Structure as: BULL CASE: [2-3 specific, numbered reasons with data]. BEAR CASE: [2-3 specific risks with magnitude]. WHAT TO MONITOR: [1-2 specific metrics or events that resolve the debate within 2 quarters]. If insider/congress/news data available, weave it in as confirming or conflicting evidence.>",
  "green_flags": [{{"flag":"<same>","evidence":"<connect this flag to its return implication — what does it mean for the stock if this persists? Quantify.>","significance":"<same>"}}],
  "red_flags": [{{"flag":"<same>","evidence":"<worst-case scenario if this materializes — what's the magnitude? What multiple/price does the stock deserve?>","significance":"<same>"}}]
}}
Return exactly {len(green_flags)} green and {len(red_flags)} red flags, same order. Keep flag and significance identical."""


def _prompt_etf_overview(ticker: str, company_name: str, sector: str, industry: str, data: dict, filing_context: str = "") -> str:
    benchmark = industry or data.get("benchmark") or ""
    asset_class = sector or data.get("asset_class") or "Equity"
    expense = data.get("expense_ratio") or "N/A"
    aum = data.get("aum") or "N/A"
    description = data.get("description") or ""

    return f"""Write a concise fund overview for {company_name} ({ticker}), a {asset_class} ETF{f' tracking the {benchmark}' if benchmark else ''}.

Key fund facts:
- AUM: {aum}
- Expense ratio: {expense}
- Asset class: {asset_class}
{f'- Benchmark: {benchmark}' if benchmark else ''}
{f'- Fund description: {description[:400]}' if description else ''}

Return a JSON object with exactly this key:
{{
  "summary": "<2-3 sentences. Describe what this ETF does and why investors use it. Mention the benchmark/strategy, asset class, and key differentiator vs. similar funds. Mention cost efficiency if the expense ratio is notably low (under 0.10%).>"
}}

Only return the summary key."""


# ── Prompt router ──────────────────────────────────────────────────────

_PROMPT_BUILDERS = {
    "Company Overview": _prompt_overview,
    "Financial Analysis": _prompt_financials,
    "Risk Analysis": _prompt_risk,
    "Auditor Flags": _prompt_auditor,
    "Earnings Call": _prompt_earnings,
    "Sector & Peers": _prompt_sector,
    "Green/Red Flags": _prompt_flags,
    # ETF sections
    "ETF Overview": _prompt_etf_overview,
}

# Fields the LLM is allowed to overwrite (simple string fields)
_NARRATIVE_FIELDS: dict[str, list[str]] = {
    "Company Overview":   ["business_description", "competitive_position", "management_highlights"],
    "Financial Analysis": ["summary", "analysis"],
    "Risk Analysis":      [],   # handled via array merge
    "Auditor Flags":      ["summary", "auditor_assessment"],
    "Earnings Call":      ["summary", "forward_outlook"],
    "Sector & Peers":     ["sector_overview", "relative_valuation"],
    "Green/Red Flags":    ["overall_assessment", "investment_thesis_summary"],
    # ETF sections
    "ETF Overview":       ["summary"],
}

# List fields that are fully replaced if LLM returns a non-empty list
_LIST_OVERWRITE_FIELDS: dict[str, list[str]] = {
    "Earnings Call":  ["key_themes", "analyst_concerns"],
    "Sector & Peers": ["tailwinds", "headwinds"],
}

# Array-of-object fields where we merge per-item narrative sub-fields
_ARRAY_MERGE_CONFIG: dict[str, dict[str, list[str]]] = {
    "Risk Analysis": {
        "risks": ["description", "evidence"],
    },
    "Auditor Flags": {
        "flags": ["description", "recommendation"],
    },
    "Green/Red Flags": {
        "green_flags": ["evidence"],
        "red_flags":   ["evidence"],
    },
}

# Nested dict fields (e.g., guidance.commentary)
_NESTED_FIELDS: dict[str, dict[str, tuple[str, str]]] = {
    "Earnings Call": {"guidance_commentary": ("guidance", "commentary")},
}


# ── Core enhancement function ─────────────────────────────────────────

async def enhance_narrative(
    agent_name: str,
    computed_data: dict,
    ticker: str,
    company_name: str,
    sector: str = "",
    industry: str = "",
    prior_sections: dict | None = None,
    filing_context: str = "",
) -> dict:
    """Enhance narrative fields in computed_data using GPT-4o.

    On ANY error, returns the original computed_data unchanged.
    """
    if not llm_available():
        return computed_data

    builder = _PROMPT_BUILDERS.get(agent_name)
    if not builder:
        logger.warning("No prompt template for agent: %s", agent_name)
        return computed_data

    cfg = _AGENT_CONFIG.get(agent_name, _DEFAULT_AGENT_CONFIG)
    sector_ctx = _sector_context(sector, industry)

    try:
        # Build prompt — each agent has slightly different signature
        if agent_name in ("Company Overview", "ETF Overview"):
            user_prompt = builder(ticker, company_name, sector, industry, computed_data, filing_context)
        elif agent_name == "Green/Red Flags":
            user_prompt = builder(ticker, company_name, computed_data, prior_sections, sector_ctx)
        elif agent_name == "Sector & Peers":
            user_prompt = builder(ticker, company_name, computed_data, sector_ctx)
        elif agent_name in ("Risk Analysis", "Auditor Flags", "Earnings Call", "Financial Analysis"):
            user_prompt = builder(ticker, company_name, computed_data, filing_context)
        else:
            user_prompt = builder(ticker, company_name, computed_data)

        llm_output = await asyncio.wait_for(
            _call_llm(user_prompt, max_tokens=cfg["max_tokens"], temperature=cfg["temperature"]),
            timeout=40.0,
        )

        if not llm_output:
            return computed_data

        parsed = json.loads(llm_output)
        return _merge_narrative(agent_name, computed_data, parsed)

    except asyncio.TimeoutError:
        logger.warning("LLM timeout for %s on %s", agent_name, ticker)
        return computed_data
    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON for %s on %s: %s | raw: %.200s",
                       agent_name, ticker, e, llm_output if 'llm_output' in dir() else "")
        return computed_data
    except Exception as e:
        logger.warning("LLM enhancement failed for %s on %s: %s", agent_name, ticker, e)
        return computed_data


async def _call_llm(
    user_prompt: str,
    max_retries: int = 2,
    max_tokens: int = 1500,
    temperature: float = 0.3,
) -> str | None:
    """Call GPT-4o and return the response content as a raw string.

    Strips markdown code fences before returning so callers can always
    call json.loads() directly without silent fallbacks.
    """
    client = _get_client()

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            content = content.strip()

            # Strip markdown code fences — GPT sometimes wraps JSON in ```json ... ```
            # even with response_format=json_object set (happens on some versions).
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*\n?", "", content)
                content = re.sub(r"\n?```\s*$", "", content).strip()

            return content

        except RateLimitError:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 3
                logger.warning("OpenAI rate limited (attempt %d), waiting %ds", attempt + 1, wait)
                await asyncio.sleep(wait)
            else:
                logger.warning("OpenAI rate limit exceeded after %d attempts", max_retries)
                return None
        except Exception as e:
            logger.warning("OpenAI API error: %s", e)
            return None

    return None


def _merge_narrative(agent_name: str, computed: dict, llm_output: dict) -> dict:
    """Deep-merge LLM narrative fields into computed data.

    Only overwrites fields explicitly listed in _NARRATIVE_FIELDS,
    _LIST_OVERWRITE_FIELDS, and _ARRAY_MERGE_CONFIG.
    All numeric/structural data is preserved.
    """
    result = copy.deepcopy(computed)

    # 1. Simple string field overwrites
    for field in _NARRATIVE_FIELDS.get(agent_name, []):
        if field in llm_output and isinstance(llm_output[field], str) and llm_output[field].strip():
            result[field] = llm_output[field]

    # 2. List field overwrites (e.g., key_themes, analyst_concerns, tailwinds, headwinds)
    for field in _LIST_OVERWRITE_FIELDS.get(agent_name, []):
        llm_val = llm_output.get(field)
        if isinstance(llm_val, list) and llm_val:
            # Filter to non-empty strings
            clean = [item for item in llm_val if isinstance(item, str) and item.strip()]
            if clean:
                result[field] = clean

    # 3. Array-of-object field merges (per-item, narrative sub-fields only)
    for array_key, sub_fields in _ARRAY_MERGE_CONFIG.get(agent_name, {}).items():
        llm_array = llm_output.get(array_key, [])
        result_array = result.get(array_key, [])

        if not isinstance(llm_array, list):
            continue

        for i, llm_item in enumerate(llm_array):
            if i >= len(result_array):
                break
            if not isinstance(llm_item, dict):
                continue
            for sub_field in sub_fields:
                if sub_field in llm_item and isinstance(llm_item[sub_field], str) and llm_item[sub_field].strip():
                    result_array[i][sub_field] = llm_item[sub_field]

    # 4. Nested dict fields (e.g., guidance.commentary)
    for llm_key, (parent_key, child_key) in _NESTED_FIELDS.get(agent_name, {}).items():
        if llm_key in llm_output and isinstance(llm_output[llm_key], str) and llm_output[llm_key].strip():
            if parent_key in result and isinstance(result[parent_key], dict):
                result[parent_key][child_key] = llm_output[llm_key]

    return result

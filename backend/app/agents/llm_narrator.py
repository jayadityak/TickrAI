"""LLM Narrative Enhancement Layer for TickrAI reports.

Takes the computed data from fmp_report_builder and enhances narrative text
fields using GPT-4o while preserving all numeric/structured data unchanged.

Graceful fallback: on ANY error, returns the original computed data.
"""

import asyncio
import copy
import json
import logging

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


# ── Shared system prompt ───────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior equity research analyst at a top-tier investment bank. \
You write clear, incisive analysis that connects data points to tell a story. Your audience \
is investors who need actionable insights, not just numbers.

Rules:
- Ground every claim in the specific data provided. Never fabricate numbers.
- Use precise financial language but keep it accessible.
- Highlight non-obvious patterns: divergences, inflection points, what the numbers imply about the business trajectory.
- Be direct about risks and uncertainties. Don't hedge excessively.
- Write in present tense for current state, past tense for historical.
- Keep each field concise but substantive — quality over length.
- Return valid JSON matching the exact schema specified."""


# ── Per-agent prompt builders ──────────────────────────────────────────

def _prompt_overview(ticker: str, company_name: str, sector: str, industry: str, data: dict, filing_context: str = "") -> str:
    filing_block = f"\n=== SEC 10-K BUSINESS DESCRIPTION (authoritative source) ===\n{filing_context}\n" if filing_context else ""
    return f"""Analyze {company_name} ({ticker}) and write analyst-grade narrative for a company overview.

=== COMPUTED DATA ===
{json.dumps(data, indent=2)}
{filing_block}
=== INSTRUCTIONS ===
Return a JSON object with exactly these keys:
{{
  "business_description": "<2-4 sentences. Go beyond restating — identify the core value proposition, what makes the business defensible, and where it sits in its lifecycle (early growth, mature, turnaround). Reference the sector ({sector}) and industry ({industry}).{' Ground in the 10-K text above.' if filing_context else ''}>",
  "competitive_position": "<Analyze moat strength, market position, key competitive advantages and vulnerabilities. Reference market cap and any available data. Connect to sector dynamics and peer landscape.>",
  "management_highlights": "<Key leadership observations tied to strategic direction and execution track record.>"
}}

Only return these 3 keys. Do not include other fields."""


def _prompt_financials(ticker: str, company_name: str, data: dict) -> str:
    return f"""Write analyst-grade financial analysis narrative for {company_name} ({ticker}).

=== COMPUTED FINANCIAL DATA ===
{json.dumps(data, indent=2)}

=== INSTRUCTIONS ===
Return a JSON object with exactly these keys:
{{
  "summary": "<2-3 sentence executive summary. Lead with the most important signal — accelerating growth? margin compression? cash flow inflection? Include specific numbers from the data.>",
  "analysis": "<Cover: (1) revenue trajectory and what's driving it, (2) margin trends and sustainability, (3) notable inflection points or divergences, (4) what the financial profile implies for forward outlook. Connect metrics to business quality — e.g., if margins expand while revenue grows, that suggests operating leverage.>"
}}"""


def _prompt_risk(ticker: str, company_name: str, data: dict, filing_context: str = "") -> str:
    # Compact risk summary — only category, severity, and key numbers
    risks = data.get("risks", [])
    compact = [{"category": r["category"], "severity": r["severity"],
                "current_desc": r.get("description", "")[:80]} for r in risks]
    filing_block = f"\n=== SEC 10-K RISK FACTORS (disclosed risks) ===\n{filing_context}\n" if filing_context else ""
    return f"""Rewrite risk descriptions for {company_name} ({ticker}). Overall: {data.get("overall_risk_level")}.
{filing_block}
Risks: {json.dumps(compact)}

Return JSON: {{"risks": [{{"category":"<same>","severity":<same>,"description":"<1-2 sentences: what this means for the business{'. Reference 10-K risks if relevant.' if filing_context else ''}>","evidence":"<key numbers in context>"}}]}}
Return exactly {len(risks)} risks, same order. Keep category and severity identical. Be concise."""


def _prompt_auditor(ticker: str, company_name: str, data: dict, filing_context: str = "") -> str:
    flags = data.get("flags", [])
    compact = [{"type": f["type"], "severity": f["severity"],
                "current_desc": f.get("description", "")[:80]} for f in flags]
    filing_block = f"\n=== SEC 10-K AUDITOR/CONTROLS SECTION ===\n{filing_context}\n" if filing_context else ""
    return f"""Write forensic accounting analysis for {company_name} ({ticker}).
{filing_block}
Flags: {json.dumps(compact)}

Return JSON:
{{
  "summary": "<2-3 sentence forensic analyst brief{'. Reference auditor opinion from 10-K if available.' if filing_context else ''}>",
  "auditor_assessment": "<what needs deeper review>",
  "flags": [{{"type":"<same>","severity":"<same>","description":"<forensic analysis of this signal>","recommendation":"<specific actionable next step>"}}]
}}
Return exactly {len(flags)} flags, same order. Keep type and severity identical. Be concise."""


def _prompt_earnings(ticker: str, company_name: str, data: dict, filing_context: str = "") -> str:
    filing_block = f"\n=== ACTUAL EARNINGS CALL TRANSCRIPT (most recent) ===\n{filing_context}\n" if filing_context else ""
    return f"""Write earnings analysis narrative for {company_name} ({ticker}).

=== COMPUTED EARNINGS DATA ===
{json.dumps(data, indent=2)}
{filing_block}
=== INSTRUCTIONS ===
Return a JSON object with exactly these keys:
{{
  "summary": "<2-3 sentences. Frame around the earnings trajectory — are estimates being revised up or down? Is there a beat/miss pattern? What does the forward EPS trajectory imply?{' Quote management language from the transcript if available.' if filing_context else ''}>",
  "forward_outlook": "<Synthesize the growth trajectory, analyst consensus, and valuation implications. What should an investor watch for next quarter? What would change the thesis?{' Ground in actual guidance language from the transcript.' if filing_context else ''}>",
  "guidance_commentary": "<Analyst consensus context with price target analysis. Frame the upside/downside in terms of risk-reward.>"
}}"""


def _prompt_sector(ticker: str, company_name: str, data: dict) -> str:
    return f"""Write sector and peer analysis narrative for {company_name} ({ticker}).

=== COMPUTED PEER DATA ===
{json.dumps(data, indent=2)}

=== INSTRUCTIONS ===
Return a JSON object with exactly these keys:
{{
  "sector_overview": "<Where does this company sit within its sector? Reference the peer comparison data — is it the growth leader? The value play? The premium name? Connect market cap positioning to competitive dynamics.>",
  "relative_valuation": "<Compare valuation multiples against peers with specific numbers. Is the premium/discount justified by growth differential? Margin superiority? Identify the closest comparable and explain why.>"
}}"""


def _prompt_flags(ticker: str, company_name: str, data: dict, prior_sections: dict | None = None) -> str:
    prior_context = ""
    cross_signal_context = ""
    if prior_sections:
        summaries = {}
        for name, section_data in prior_sections.items():
            if name == "cross_signals":
                continue  # handled separately
            if isinstance(section_data, dict):
                for key in ("summary", "overall_risk_level", "management_tone", "auditor_assessment"):
                    if key in section_data:
                        val = section_data[key]
                        summaries[f"{name} — {key}"] = val[:150] if isinstance(val, str) else val
        if summaries:
            prior_context = f"\nPrior findings: {json.dumps(summaries)}\n"

        # Cross-signal data for synthesis
        cross = prior_sections.get("cross_signals")
        if cross and isinstance(cross, dict):
            parts = []
            insider = cross.get("insider")
            if insider:
                parts.append(f"INSIDER TRADING: {insider.get('purchases', 0)} purchases, "
                             f"{insider.get('sales', 0)} sales, net value: ${insider.get('net_value', 0):,.0f}, "
                             f"signal: {insider.get('signal', 'N/A')}. "
                             f"Notable: {json.dumps(insider.get('notable_trades', [])[:3])}")
            congress = cross.get("congress")
            if congress:
                parts.append(f"CONGRESS TRADES: {congress.get('total_trades', 0)} total, "
                             f"{congress.get('recent_buys', 0)} buys / {congress.get('recent_sells', 0)} sells recent, "
                             f"signal: {congress.get('signal', 'N/A')}. "
                             f"Recent: {json.dumps(congress.get('recent_trades', [])[:3])}")
            news = cross.get("news")
            if news:
                parts.append(f"NEWS SENTIMENT: score {news.get('overall_score', 5)}/10 ({news.get('overall_label', 'neutral')}), "
                             f"{news.get('headline_count', 0)} headlines. "
                             f"Recent: {json.dumps(news.get('recent_headlines', [])[:3])}")
            if parts:
                cross_signal_context = "\n=== CROSS-SIGNAL DATA (synthesize these with fundamentals) ===\n" + "\n".join(parts) + "\n"

    green_flags = data.get("green_flags", [])
    red_flags = data.get("red_flags", [])
    compact_green = [{"flag": f["flag"], "significance": f["significance"]} for f in green_flags]
    compact_red = [{"flag": f["flag"], "significance": f["significance"]} for f in red_flags]

    synthesis_instruction = ""
    if cross_signal_context:
        synthesis_instruction = """
CRITICAL: In your overall_assessment and investment_thesis_summary, synthesize the cross-signal data with fundamentals.
Look for convergence/divergence patterns — e.g., insiders buying while short interest falls = convergence signal.
Congress trades + insider trades in same direction = stronger conviction signal.
News sentiment diverging from fundamentals = potential inflection point.
"""

    return f"""Investment scorecard for {company_name} ({ticker}). Score: {data.get("overall_score")}/10.
{prior_context}{cross_signal_context}
Green: {json.dumps(compact_green)}
Red: {json.dumps(compact_red)}
{synthesis_instruction}
Return JSON:
{{
  "overall_assessment": "<2-3 sentence verdict for an investor. Reference cross-signal data if available.>",
  "investment_thesis_summary": "<Bull case (2-3 points), bear case (2-3 risks), key monitoring points. Weave in insider/congress/news signals.>",
  "green_flags": [{{"flag":"<same>","evidence":"<why this matters for returns>","significance":"<same>"}}],
  "red_flags": [{{"flag":"<same>","evidence":"<quantify the risk, worst case>","significance":"<same>"}}]
}}
Return exactly {len(green_flags)} green and {len(red_flags)} red flags, same order. Keep flag and significance identical."""


# ── Prompt router ──────────────────────────────────────────────────────

_PROMPT_BUILDERS = {
    "Company Overview": _prompt_overview,
    "Financial Analysis": _prompt_financials,
    "Risk Analysis": _prompt_risk,
    "Auditor Flags": _prompt_auditor,
    "Earnings Call": _prompt_earnings,
    "Sector & Peers": _prompt_sector,
    "Green/Red Flags": _prompt_flags,
}

# Fields the LLM is allowed to overwrite (simple string fields)
_NARRATIVE_FIELDS: dict[str, list[str]] = {
    "Company Overview": ["business_description", "competitive_position", "management_highlights"],
    "Financial Analysis": ["summary", "analysis"],
    "Risk Analysis": [],  # handled via array merge
    "Auditor Flags": ["summary", "auditor_assessment"],
    "Earnings Call": ["summary", "forward_outlook"],
    "Sector & Peers": ["sector_overview", "relative_valuation"],
    "Green/Red Flags": ["overall_assessment", "investment_thesis_summary"],
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
        "red_flags": ["evidence"],
    },
}

# Nested dict fields (e.g., guidance.commentary)
_NESTED_FIELDS: dict[str, dict[str, str]] = {
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

    try:
        # Build prompt
        if agent_name == "Company Overview":
            user_prompt = builder(ticker, company_name, sector, industry, computed_data, filing_context)
        elif agent_name == "Green/Red Flags":
            user_prompt = builder(ticker, company_name, computed_data, prior_sections)
        elif filing_context and agent_name in ("Risk Analysis", "Auditor Flags", "Earnings Call"):
            user_prompt = builder(ticker, company_name, computed_data, filing_context)
        else:
            user_prompt = builder(ticker, company_name, computed_data)

        # Call LLM with timeout
        llm_output = await asyncio.wait_for(
            _call_llm(user_prompt),
            timeout=30.0,
        )

        if not llm_output:
            return computed_data

        # Parse JSON response
        parsed = json.loads(llm_output)

        # Merge LLM narrative into computed data
        return _merge_narrative(agent_name, computed_data, parsed)

    except asyncio.TimeoutError:
        logger.warning("LLM timeout for %s on %s", agent_name, ticker)
        return computed_data
    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON for %s on %s: %s", agent_name, ticker, e)
        return computed_data
    except Exception as e:
        logger.warning("LLM enhancement failed for %s on %s: %s", agent_name, ticker, e)
        return computed_data


async def _call_llm(user_prompt: str, max_retries: int = 2) -> str | None:
    """Call GPT-4o and return the response content."""
    client = _get_client()

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1500,
            )
            return response.choices[0].message.content
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

    Only overwrites fields explicitly listed in _NARRATIVE_FIELDS and
    _ARRAY_MERGE_CONFIG. All numeric/structural data is preserved.
    """
    result = copy.deepcopy(computed)

    # 1. Simple string field overwrites
    for field in _NARRATIVE_FIELDS.get(agent_name, []):
        if field in llm_output and isinstance(llm_output[field], str) and llm_output[field].strip():
            result[field] = llm_output[field]

    # 2. Array-of-object field merges (per-item, narrative sub-fields only)
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

    # 3. Nested dict fields (e.g., guidance.commentary)
    for llm_key, (parent_key, child_key) in _NESTED_FIELDS.get(agent_name, {}).items():
        if llm_key in llm_output and isinstance(llm_output[llm_key], str) and llm_output[llm_key].strip():
            if parent_key in result and isinstance(result[parent_key], dict):
                result[parent_key][child_key] = llm_output[llm_key]

    return result

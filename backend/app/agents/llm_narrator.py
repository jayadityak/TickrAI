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

SYSTEM_PROMPT = """You are a Managing Director of Equity Research at TickrAI, covering global equities. \
You previously spent 15 years writing research at Goldman Sachs and Bernstein. \
Your reports are known for being decisive, data-grounded, and written for investors who need signal — not summaries.

Voice and style:
- Write like a seasoned sell-side analyst, not a textbook. Confident, direct, specific.
- Lead with what matters: the insight, the anomaly, the implication — not the data recap.
- Use precise financial language: "operating leverage", "FCF conversion", "multiple compression risk", "re-rating catalyst", "beat-and-raise", "margin inflection".
- Compare to peers, to history, to sector norms — context is what separates analysis from description.
- Be opinionated. "Revenue growth is decelerating" is a fact. "That deceleration, combined with multiple expansion YTD, creates asymmetric downside risk" is analysis.
- Don't hedge excessively. If the data is mixed, say so directly: "The bull case depends on X; if X fails, the stock has Y% downside."

Rules:
- Ground every claim in the specific data provided. Never fabricate numbers.
- Write in present tense for current state, past tense for historical.
- Be concise: every sentence must earn its place.
- Return valid JSON matching the exact schema specified."""


# ── Per-agent prompt builders ──────────────────────────────────────────

def _prompt_overview(ticker: str, company_name: str, sector: str, industry: str, data: dict, filing_context: str = "") -> str:
    filing_block = f"\n=== SEC 10-K BUSINESS DESCRIPTION (authoritative source) ===\n{filing_context}\n" if filing_context else ""
    return f"""Write initiating-coverage-style narrative for {company_name} ({ticker}), a {industry} company in the {sector} sector.

=== COMPUTED DATA ===
{json.dumps(data, indent=2)}
{filing_block}
=== INSTRUCTIONS ===
Think like you're writing the opening page of a 20-page initiation report. Investors already know the company exists — tell them what actually matters.

Return a JSON object with exactly these keys:
{{
  "business_description": "<2-4 sentences. Skip generic descriptions. Lead with what makes this business competitively defensible or uniquely positioned. Identify where it sits in its growth lifecycle (early hypergrowth, scaling, mature compounder, turnaround). Reference specific revenue drivers or unit economics if available.{' Ground in the 10-K text above.' if filing_context else ''}>",
  "competitive_position": "<Analyst take on the moat: is it real, wide, narrowing? Cite specific advantages — switching costs, network effects, cost structure, brand, IP. Be honest about vulnerabilities. Reference market cap and sector positioning. Where does this company rank vs. peers — leader, challenger, niche player?>",
  "management_highlights": "<Specific assessment of leadership quality and track record. Have they executed on promises? What does their capital allocation history tell you about their priorities? Any red flags or green flags in how they communicate with the street?>"
}}

Only return these 3 keys. Do not include other fields."""


def _prompt_financials(ticker: str, company_name: str, data: dict) -> str:
    return f"""Write a sell-side financial analysis for {company_name} ({ticker}).

=== COMPUTED FINANCIAL DATA ===
{json.dumps(data, indent=2)}

=== INSTRUCTIONS ===
This is the core of the research note. Don't recap the data — interpret it. What does it tell you about business quality, trajectory, and what investors should watch?

Return a JSON object with exactly these keys:
{{
  "summary": "<2-3 sentences. Lead with the single most important financial signal — is this a beat-and-raise story? A margin compression concern? A FCF inflection? Cite the exact number and what it implies. E.g.: 'Operating margins expanded 240bps YoY to 31.2% — accelerating despite revenue growth slowing to 8%, suggesting structural operating leverage rather than cost-cutting.'>",
  "analysis": "<Analyst-grade narrative covering: (1) Revenue trajectory: is growth accelerating, decelerating, or stable — and why? What are the highest-quality revenue streams? (2) Margin story: gross, operating, and net margin trends. Is the business gaining or losing pricing power? (3) Cash flow quality: is net income supported by FCF, or are there accrual gaps? (4) The one thing that could break the bull thesis: identify the financial metric most at risk and what the downside scenario looks like. Use specific numbers throughout.>"
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
    return f"""Write earnings call analysis for {company_name} ({ticker}) as a buy-side analyst would brief their portfolio manager.

=== COMPUTED EARNINGS DATA ===
{json.dumps(data, indent=2)}
{filing_block}
=== INSTRUCTIONS ===
The PM has 30 seconds. Lead with what matters most: did they beat, guide up, guide down? What was the one takeaway from the call?

Return a JSON object with exactly these keys:
{{
  "summary": "<2-3 sentences. Open with the headline verdict — beat/miss/in-line on revenue and EPS, and whether guidance came in ahead or behind consensus. Then the one key insight from the quarter that changes how you think about the next 12 months.{' If transcript available, quote management directly — their exact language on guidance matters.' if filing_context else ''}>",
  "forward_outlook": "<What should investors monitor over the next 1-2 quarters? Identify the specific metric or event that will confirm or deny the thesis. What's the bar for the next print — what do they need to show to justify current multiples? Be specific about what would make you more or less constructive.{' Reference actual guidance ranges from the transcript.' if filing_context else ''}>",
  "guidance_commentary": "<Frame the consensus estimate picture: are estimates going up or down? What's the EPS power scenario if the company executes? Identify the specific risk that would cause a guidance cut — and what the stock would do if that happens.>"
}}"""


def _prompt_sector(ticker: str, company_name: str, data: dict) -> str:
    return f"""Write a peer comparison and relative valuation section for {company_name} ({ticker}).

=== COMPUTED PEER DATA ===
{json.dumps(data, indent=2)}

=== INSTRUCTIONS ===
This section answers the question every investor asks: "Why own this vs. the peer group?"

Return a JSON object with exactly these keys:
{{
  "sector_overview": "<Position this company within its competitive landscape. Is it the sector leader, the fastest grower, the cheapest name, or the highest quality? Reference the peer group specifically — who is the closest comparable and how does management execution compare? Identify whether the sector has tailwinds (rising tide) or headwinds (zero-sum competition) that affect all names.>",
  "relative_valuation": "<This is the key question: is the valuation premium or discount justified? Compare specific multiples (P/E, EV/EBITDA, P/S) to peers with exact numbers. Then do the work — if company A grows twice as fast as peer B but trades at only a 20% premium, that's a compelling risk/reward. If it trades at a 50% premium to slower-growing peers, that premium needs justification. State whether you think the current spread is too wide, fair, or too narrow.>"
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
CRITICAL — Cross-signal synthesis:
When writing overall_assessment and investment_thesis_summary, look for convergence and divergence:
- Insiders buying + congress buying + improving news sentiment = high-conviction bull signal
- Insiders selling + bearish news + fundamental deterioration = high-conviction bear signal
- Mixed signals (insiders buying but news bearish) = identify which signal is more informative and why
- Call out the most significant cross-signal observation explicitly in your assessment
"""

    return f"""Write the investment scorecard verdict for {company_name} ({ticker}). Composite score: {data.get("overall_score")}/10.

This is the final word — the section where an analyst commits to a view. Don't summarize what came before. Synthesize it into actionable conclusions.
{prior_context}{cross_signal_context}
Signals identified:
GREEN: {json.dumps(compact_green)}
RED: {json.dumps(compact_red)}
{synthesis_instruction}
Return JSON:
{{
  "overall_assessment": "<2-3 sentences. Open with your verdict — are the bulls or bears in control of this story right now? Cite the 1-2 most decisive data points. If cross-signal data is present, incorporate what insiders/congress/news are telling you and whether they confirm or contradict the fundamentals.>",
  "investment_thesis_summary": "<Structure as: BULL CASE: [2-3 specific, numbered reasons to own the stock with data]. BEAR CASE: [2-3 specific risks that would derail the thesis]. WHAT TO MONITOR: [1-2 specific metrics or events that will prove who's right in the next 2 quarters]. If insider/congress/news data is available, weave it in as supporting or conflicting evidence.>",
  "green_flags": [{{"flag":"<same>","evidence":"<connect this flag to its return implication — what does it mean for the stock if this persists? Quantify if possible.>","significance":"<same>"}}],
  "red_flags": [{{"flag":"<same>","evidence":"<worst-case scenario if this materializes — what's the magnitude of the impact? What multiple/price does the stock deserve if this plays out?>","significance":"<same>"}}]
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

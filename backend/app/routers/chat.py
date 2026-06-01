"""AI Chat with Report — lets users ask follow-up questions about a company.

The full report data (all 7 agent outputs) is injected as context so GPT
answers are grounded in real financials. GPT-4o can also use its general
financial knowledge to enrich answers — it flags when data isn't in the report.
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI

from ..config import settings
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

SYSTEM_PROMPT = """You are a senior equity research analyst and portfolio manager at TickrAI. You spent 12 years at Goldman Sachs and Morgan Stanley covering {sector} stocks before joining TickrAI. You are known for having decisive, well-reasoned views and being direct.

You are currently covering **{ticker} ({company_name})**.

A comprehensive research report has been generated for this company:

=== RESEARCH REPORT ===
{report_data}
=== END REPORT ===

---

## Your analytical voice

**Lead with the call.** When asked for an opinion, give it first — "I'm constructive on this name here because..." or "I'd be cautious at current levels given..." Don't open with summaries or preamble.

**Use precise analyst language naturally:**
- "The street is underestimating..." / "consensus is pricing in..."
- "Multiple expansion / compression", "re-rating catalyst", "derating risk"
- "Beat-and-raise pattern", "margin inflection", "operating leverage kicking in"
- "FCF yield", "EV/EBITDA vs peers", "NTM P/E", "EPS power"
- "I'd be a buyer at X", "I'd fade this rally until...", "near-term entry point at..."
- "The risk/reward is attractive at X: upside to $Y vs support at $Z"

**Give concrete views when asked:**
- Price targets with methodology: "18x forward EPS on $12 gets you to $216, call it $200–220 base case"
- Positioning: "Long here / trim above $X / avoid until Y clears"
- Catalyst timeline: "Watch Q3 earnings — that's where the margin story either gets validated or falls apart"
- Peer comparison: "Trading at a 15% discount to [Peer] despite growing twice as fast — that gap should close"

**On data:**
- For numbers IN the report: cite them precisely with context ("Revenue grew 12% YoY to $X — that's an acceleration from 8% last quarter")
- For questions the report doesn't cover: answer from your broader analyst knowledge, flag it clearly ("This isn't in the report, but from what I know about the sector...")
- Never fabricate specific figures — say "I'd need to check the latest filings for that exact number" instead

**Response format:**
- Skip the preamble. No "Great question!" or "Based on the report, I can see that..."
- Use **bold** for the key number, rating, or conclusion in every response
- Bullet points for 3+ items; flowing prose for 1-2 points
- Match depth to complexity: "what's the P/E?" = one line. "should I buy this stock?" = structured analysis
- Hedge funds don't have time for padding — be concise and sharp
"""


def _extract_report_context(report_data: dict, ticker: str) -> tuple[str, str, str]:
    """Extract company name, sector, and compact report context from report data.

    Returns (company_name, sector, compact_json_string).
    Uses compact JSON (no indent) to maximize content within token budget.
    Sections are ordered by relevance: overview first, then financials, flags last.
    """
    company_name = ticker.upper()
    sector = "Technology"  # sensible default
    sections_by_name: dict[str, dict] = {}

    # Flatten the report_data structure
    for key, val in report_data.items():
        if isinstance(val, dict):
            agent_name = val.get("agent_name", key)
            data = val.get("data", val)
            sections_by_name[agent_name] = data

            # Extract company name and sector from Overview
            if isinstance(data, dict):
                if data.get("company_name"):
                    company_name = data["company_name"]
                if data.get("sector"):
                    sector = data["sector"]

    # Preferred section order
    order = [
        "Company Overview",
        "Financial Analysis",
        "Green/Red Flags",
        "Risk Analysis",
        "Earnings Call",
        "Sector & Peers",
        "Auditor Flags",
    ]

    ordered: dict = {}
    for name in order:
        if name in sections_by_name:
            ordered[name] = sections_by_name[name]
    # Append any remaining sections
    for name, data in sections_by_name.items():
        if name not in ordered:
            ordered[name] = data

    # Compact JSON — no indentation, saves ~30% tokens
    compact = json.dumps(ordered, default=str, separators=(",", ":"))

    # GPT-4o supports 128K context — use up to 60K chars (well within budget)
    MAX_CHARS = 60000
    if len(compact) > MAX_CHARS:
        # Truncate least-important sections from the end
        compact = compact[:MAX_CHARS] + "...}"
        logger.info("Report context truncated to %d chars for %s", MAX_CHARS, ticker)

    return company_name, sector, compact


class ChatRequest(BaseModel):
    message: str
    report_data: dict
    history: list[dict] = []  # [{role: "user"/"assistant", content: "..."}]


@router.post("/api/reports/{ticker}/chat")
async def chat_with_report(
    ticker: str,
    body: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Stream an AI response to a user question about a report."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    company_name, sector, report_context = _extract_report_context(body.report_data, ticker.upper())

    system = SYSTEM_PROMPT.format(
        ticker=ticker.upper(),
        company_name=company_name,
        sector=sector,
        report_data=report_context,
    )

    # Build message history (last 20 messages = 10 exchanges)
    messages = [{"role": "system", "content": system}]
    for msg in body.history[-20:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": body.message})

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            stream = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                stream=True,
                max_tokens=1500,
                temperature=0.4,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield f"data: {json.dumps({'content': delta.content})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.exception("Chat error for %s", ticker)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

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

SYSTEM_PROMPT = """You are a senior equity research analyst at TickrAI. You have deep expertise in fundamental analysis, valuation, sector dynamics, and financial statement analysis.

You are analyzing {ticker} ({company_name}). A comprehensive research report has been generated covering all major aspects of the company.

=== FULL RESEARCH REPORT ===
{report_data}
=== END REPORT ===

Your capabilities:
- Answer ANY question about {ticker} — business model, competitors, industry trends, valuation frameworks, historical context, macro factors, management, products, etc.
- For questions covered in the report above: cite specific numbers and data points. Be precise.
- For questions NOT fully covered in the report: use your financial knowledge to provide context, but clearly note what comes from the report vs. your general knowledge.
- Never fabricate specific numbers that aren't in the report. If you don't have a number, say so and explain the framework instead.
- Give opinions when asked — frame them as analyst perspective, not personal financial advice.

Response style:
- Lead with the most important insight, not a preamble.
- Use **bold** for key figures and conclusions.
- Use bullet points for lists of 3+ items.
- Keep answers focused and actionable — investors need signal, not noise.
- Match length to complexity: simple questions get direct answers, deep analysis gets structured breakdown.
"""


def _extract_report_context(report_data: dict, ticker: str) -> tuple[str, str]:
    """Extract company name and compact report context from report data.

    Returns (company_name, compact_json_string).
    Uses compact JSON (no indent) to maximize content within token budget.
    Sections are ordered by relevance: overview first, then financials, flags last.
    """
    company_name = ticker.upper()
    sections_by_name: dict[str, dict] = {}

    # Flatten the report_data structure
    for key, val in report_data.items():
        if isinstance(val, dict):
            agent_name = val.get("agent_name", key)
            data = val.get("data", val)
            sections_by_name[agent_name] = data

            # Extract company name from Overview
            if isinstance(data, dict) and data.get("company_name"):
                company_name = data["company_name"]

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

    return company_name, compact


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

    company_name, report_context = _extract_report_context(body.report_data, ticker.upper())

    system = SYSTEM_PROMPT.format(
        ticker=ticker.upper(),
        company_name=company_name,
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

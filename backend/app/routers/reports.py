import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..utils.auth import get_current_user

from ..config import settings
from ..data_sources.ticker_list import get_ticker
from ..data_sources.fmp import get_profile
from ..agents.orchestrator import run_all_agents, run_all_agents_sync
from ..agents.fmp_report_builder import build_all_sections
from ..models.report import ReportResponse, AgentResult
from .trending import log_research

logger = logging.getLogger(__name__)

router = APIRouter()


def _use_ai() -> bool:
    return bool(settings.openai_api_key)


def _use_fmp() -> bool:
    return bool(settings.fmp_api_key)


async def _resolve_company(ticker: str) -> dict | None:
    """Look up ticker in local list first, then fall back to FMP profile."""
    local = get_ticker(ticker)
    if local:
        return local
    if not settings.fmp_api_key:
        return None
    try:
        profile = await get_profile(ticker)
        if profile and profile.get("companyName"):
            return {
                "symbol": profile["symbol"],
                "company_name": profile["companyName"],
                "exchange": profile.get("exchange", ""),
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
            }
    except Exception:
        pass
    return None


@router.post("/api/reports/{ticker}", response_model=ReportResponse)
async def create_report(ticker: str, user: dict = Depends(get_current_user)):
    upper = ticker.upper()
    company_data = await _resolve_company(upper)

    if not company_data:
        raise HTTPException(status_code=404, detail=f"Ticker '{upper}' not found")

    if _use_fmp():
        agent_results = await build_all_sections(upper)
    elif _use_ai():
        agent_results = await run_all_agents_sync(upper, company_data)
    else:
        raise HTTPException(status_code=503, detail="No API keys configured. Set OPENAI_API_KEY or FMP_API_KEY.")

    log_research(upper)

    report = ReportResponse(
        id=str(uuid.uuid4()),
        ticker=upper,
        company_name=company_data["company_name"],
        exchange=company_data["exchange"],
        status="completed",
        created_at=datetime.now(timezone.utc).isoformat(),
        agent_results=[AgentResult(**r) for r in agent_results],
        metadata={"sector": company_data.get("sector", "")},
    )
    return report


@router.get("/api/reports/{ticker}/stream")
async def stream_report(ticker: str, user: dict = Depends(get_current_user)):
    upper = ticker.upper()
    company_data = await _resolve_company(upper)
    log_research(upper)

    async def event_generator():
        yield f"event: report_start\ndata: {json.dumps({'ticker': upper})}\n\n"

        if not company_data:
            yield f"event: error\ndata: {json.dumps({'error': f'Ticker {upper} not found'})}\n\n"
            return

        if _use_fmp():
            try:
                sections = await build_all_sections(upper)
                for section in sections:
                    await asyncio.sleep(0.3)
                    yield f"event: agent_complete\ndata: {json.dumps(section)}\n\n"
            except Exception as e:
                logger.exception("FMP report error for %s", upper)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                return
        elif _use_ai():
            async for result in run_all_agents(upper, company_data):
                yield f"event: agent_complete\ndata: {json.dumps(result)}\n\n"
        else:
            yield f"event: error\ndata: {json.dumps({'error': 'No API keys configured'})}\n\n"
            return

        yield f"event: report_complete\ndata: {json.dumps({'status': 'completed'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..utils.auth import get_current_user

from ..config import settings
from ..data_sources.ticker_list import get_ticker
from ..data_sources.fmp import get_profile
from ..agents.orchestrator import run_all_agents, run_all_agents_sync
from ..agents.fmp_report_builder import build_all_sections
from ..agents.fmp_etf_builder import build_etf_sections
from ..models.report import ReportResponse, AgentResult
from .trending import log_research

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Report-level cache ────────────────────────────────────────────────────────
# Caches the full build_all_sections() result per ticker for 1 hour.
# Prevents duplicate pipelines when multiple users hit the same popular ticker.
# Also deduplicates concurrent in-flight requests for the same ticker.
_report_cache: dict[str, tuple[float, list]] = {}  # ticker -> (timestamp, sections)
_REPORT_CACHE_TTL = 3600  # 1 hour
_report_in_flight: dict[str, asyncio.Event] = {}   # ticker -> Event, set when build completes
_report_build_tasks: dict[str, asyncio.Task] = {}  # ticker -> background build Task (keeps ref alive)
_report_errors: dict[str, str] = {}               # ticker -> error from last failed build


def _use_ai() -> bool:
    return bool(settings.openai_api_key)


def _use_fmp() -> bool:
    return bool(settings.fmp_api_key)


def _yfinance_resolve(ticker: str) -> dict | None:
    """Synchronous yfinance fallback — resolves any US-listed ticker for free."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        # yfinance can return a list for ambiguous tickers — skip those
        if not isinstance(info, dict) or not info:
            return None
        name = info.get("shortName") or info.get("longName")
        if not name:
            return None
        return {
            "symbol": ticker,
            "company_name": name,
            "exchange": info.get("exchange", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
        }
    except Exception:
        return None


async def _resolve_company(ticker: str) -> dict | None:
    """Look up ticker: static list → FMP profile → yfinance (free fallback)."""
    # 1. Static list — instant, no API call
    local = get_ticker(ticker)
    if local:
        return local

    # 2. FMP profile — more metadata, requires API key
    if settings.fmp_api_key:
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

    # 3. yfinance — free, covers all US-listed tickers
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _yfinance_resolve, ticker)


async def _do_build(ticker: str, event: asyncio.Event) -> None:
    """Background task: build sections for *ticker*, cache on success, always signal event.

    Running as an independent Task means client disconnects (SSE drops, page refresh,
    React StrictMode double-mount) cannot cancel the build mid-flight.
    """
    try:
        sections = await build_all_sections(ticker)
        _report_cache[ticker] = (time.time(), sections)
        _report_errors.pop(ticker, None)
        logger.info("Report built and cached for %s", ticker)
    except Exception as e:
        _report_errors[ticker] = str(e)
        logger.exception("Report build failed for %s", ticker)
    finally:
        event.set()
        _report_in_flight.pop(ticker, None)
        _report_build_tasks.pop(ticker, None)


async def _get_or_build_sections(ticker: str) -> list:
    """Return cached sections or build fresh, deduplicating concurrent requests.

    - Cache hit  (< 1 h old): returns instantly from memory.
    - In-flight  : waits for the background build Task to complete.
    - Miss        : launches a background Task (immune to client cancellation),
                    then waits for it.
    """
    now = time.time()

    # 1. Cache hit
    if ticker in _report_cache:
        ts, sections = _report_cache[ticker]
        if now - ts < _REPORT_CACHE_TTL:
            logger.debug("Report cache hit for %s (age %.0fs)", ticker, now - ts)
            return sections

    # 2. Another Task is already building — wait for it
    if ticker in _report_in_flight:
        logger.debug("Report in-flight for %s — waiting", ticker)
        await _report_in_flight[ticker].wait()
        if ticker in _report_cache:
            return _report_cache[ticker][1]
        err = _report_errors.get(ticker, f"Build for {ticker} failed")
        raise RuntimeError(err)

    # 3. Cache miss — launch an independent background Task so that if this
    #    coroutine is cancelled (e.g. SSE client disconnects) the build keeps
    #    running and the next request finds the result in cache.
    event = asyncio.Event()
    _report_in_flight[ticker] = event
    task = asyncio.create_task(_do_build(ticker, event))
    _report_build_tasks[ticker] = task   # keep a reference so GC can't collect it

    await event.wait()   # wait for the background task to finish

    if ticker in _report_cache:
        return _report_cache[ticker][1]
    err = _report_errors.get(ticker, f"Build for {ticker} failed")
    raise RuntimeError(err)


@router.post("/api/reports/{ticker}", response_model=ReportResponse)
async def create_report(ticker: str, user: dict = Depends(get_current_user)):
    upper = ticker.upper()
    company_data = await _resolve_company(upper)

    if not company_data:
        raise HTTPException(status_code=404, detail=f"Ticker '{upper}' not found")

    if _use_fmp():
        agent_results = await _get_or_build_sections(upper)
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

    # Detect ETF via FMP profile (cached after first call)
    is_etf = False
    if settings.fmp_api_key:
        try:
            profile = await get_profile(upper)
            is_etf = bool(profile.get("isEtf", False))
        except Exception:
            pass

    async def event_generator():
        yield f"event: report_start\ndata: {json.dumps({'ticker': upper, 'is_etf': is_etf})}\n\n"

        if not company_data:
            yield f"event: error\ndata: {json.dumps({'error': f'Ticker {upper} not found'})}\n\n"
            return

        if is_etf:
            try:
                sections = await build_etf_sections(upper)
                for section in sections:
                    await asyncio.sleep(0.15)
                    yield f"event: agent_complete\ndata: {json.dumps(section)}\n\n"
            except Exception as e:
                logger.exception("ETF report error for %s", upper)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                return
        elif _use_fmp():
            try:
                sections = await _get_or_build_sections(upper)
                for section in sections:
                    await asyncio.sleep(0.15)   # brief delay so UI feels live
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

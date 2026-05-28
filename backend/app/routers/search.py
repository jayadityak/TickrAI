import httpx
from fastapi import APIRouter, Query

from ..config import settings
from ..data_sources.ticker_list import search_tickers
from ..schemas.search import SearchResponse

router = APIRouter()


@router.get("/api/search", response_model=SearchResponse)
async def search(q: str = Query("", description="Search query for ticker symbol or company name")):
    local_results = search_tickers(q)

    if len(local_results) >= 5 or not settings.fmp_api_key or len(q) < 1:
        return SearchResponse(
            results=[
                {"symbol": r["symbol"], "company_name": r["company_name"], "exchange": r["exchange"]}
                for r in local_results
            ]
        )

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                "https://financialmodelingprep.com/stable/search-name",
                params={"query": q, "apikey": settings.fmp_api_key, "limit": "20"},
            )
            r.raise_for_status()
            fmp_results = r.json()
    except Exception:
        fmp_results = []

    local_symbols = {r["symbol"] for r in local_results}
    combined = [
        {"symbol": r["symbol"], "company_name": r["company_name"], "exchange": r["exchange"]}
        for r in local_results
    ]
    us_exchanges = {"NYSE", "NASDAQ", "AMEX", "NYQ", "NMS"}
    for item in fmp_results:
        sym = item.get("symbol", "")
        exchange = item.get("exchange", "")
        exchange_full = item.get("exchangeFullName", "")
        is_us = exchange in us_exchanges or "New York" in exchange_full or "NASDAQ" in exchange_full
        if sym not in local_symbols and is_us and "." not in sym:
            combined.append({
                "symbol": sym,
                "company_name": item.get("name", sym),
                "exchange": exchange,
            })
            local_symbols.add(sym)

    return SearchResponse(results=combined[:10])

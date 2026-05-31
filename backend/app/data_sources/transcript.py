"""Earnings press release fetcher via SEC EDGAR 8-K filings.

When FMP earnings transcript endpoint is unavailable (paid tier),
falls back to SEC EDGAR 8-K Exhibit 99.1 — the earnings press release
companies file when reporting quarterly/annual results.

This is free, public, and contains:
- Revenue/EPS summary
- Management commentary
- Forward guidance language

Token-optimized: hard-truncated to ~1,500 chars before injection into
Agent 5's LLM prompt. No extra LLM calls.

Cache: 6 hours per ticker.
"""

import logging
import re
import time

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_EDGAR_BASE = "https://data.sec.gov"
_EDGAR_ARCHIVES = "https://www.sec.gov"
_HEADERS = {"User-Agent": "TickrAI research@tickr.ai"}

# Cache: ticker -> (timestamp, result_dict)
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 21600  # 6 hours

# Char budgets
_PREPARED_LIMIT = 800
_GUIDANCE_LIMIT = 500
_QA_LIMIT = 300

# Forward-looking sentence signals
_GUIDANCE_KEYWORDS = re.compile(
    r"\b(expect|guidance|outlook|forecast|anticipate|project|target|estimate|"
    r"quarter|full.year|revenue|margin|growth|EPS|earnings per share|raise|lower|"
    r"increase|decrease|headwind|tailwind|momentum|confident|next|fiscal)\b",
    re.IGNORECASE,
)

_FMP_V3_BASE = "https://financialmodelingprep.com/api/v3"


async def get_earnings_transcript(ticker: str) -> dict:
    """Return a token-optimized earnings context summary for Agent 5.

    Tries FMP transcripts first (paid accounts), then falls back to
    SEC EDGAR 8-K press release. Returns empty dict on all failures.

    Result keys: prepared_remarks, guidance_snippets, qa_highlights, period
    """
    symbol = ticker.upper()
    now = time.time()

    if symbol in _cache:
        ts, data = _cache[symbol]
        if now - ts < _CACHE_TTL:
            return data

    result = {}

    # Try FMP transcript first (works for paid accounts)
    if settings.fmp_api_key:
        result = await _try_fmp_transcript(symbol)

    # Fall back to EDGAR 8-K press release
    if not result:
        result = await _try_edgar_8k(symbol)

    if result:
        _cache[symbol] = (now, result)
        logger.info(
            "Earnings context for %s (%s) — prepared=%d, guidance=%d chars",
            symbol,
            result.get("period", "?"),
            len(result.get("prepared_remarks", "")),
            len(result.get("guidance_snippets", "")),
        )

    return result


async def _try_fmp_transcript(symbol: str) -> dict:
    """Attempt to fetch earnings transcript from FMP (paid tier only)."""
    try:
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS) as client:
            r = await client.get(
                f"{_FMP_V3_BASE}/earning_call_transcript/{symbol}",
                params={"limit": 1, "apikey": settings.fmp_api_key},
            )
            if r.status_code in (402, 403, 429):
                return {}
            if r.status_code != 200:
                return {}
            raw = r.json()
            if not raw or not isinstance(raw, list) or not raw[0].get("content"):
                return {}

            item = raw[0]
            content = item.get("content", "")
            quarter = item.get("quarter", "")
            year = item.get("year", "")

            result = _parse_transcript(content)
            result["period"] = f"Q{quarter} {year}" if quarter and year else ""
            return result
    except Exception as e:
        logger.debug("FMP transcript failed for %s: %s", symbol, e)
        return {}


async def _try_edgar_8k(symbol: str) -> dict:
    """Fetch the most recent 8-K earnings press release from EDGAR."""
    try:
        async with httpx.AsyncClient(timeout=25, headers=_HEADERS) as client:
            # Step 1: Get CIK
            cik = await _get_cik(client, symbol)
            if not cik:
                return {}

            # Step 2: Find most recent 8-K with EX-99 exhibit
            filing_url, period = await _get_latest_8k_url(client, cik)
            if not filing_url:
                return {}

            # Step 3: Fetch and parse press release
            r = await client.get(filing_url, timeout=30)
            if r.status_code != 200:
                return {}

            text = _clean_html(r.text)
            result = _parse_press_release(text)
            result["period"] = period
            return result

    except Exception as e:
        logger.warning("EDGAR 8-K fetch failed for %s: %s", symbol, e)
        return {}


async def _get_cik(client: httpx.AsyncClient, symbol: str) -> str | None:
    """Lookup CIK from company tickers JSON."""
    try:
        r = await client.get("https://www.sec.gov/files/company_tickers.json")
        if r.status_code == 200:
            for entry in r.json().values():
                if entry.get("ticker", "").upper() == symbol:
                    return str(entry["cik_str"]).zfill(10)
    except Exception as e:
        logger.debug("CIK lookup failed for %s: %s", symbol, e)
    return None


_EARNINGS_KEYWORDS = re.compile(
    r"results of operations|financial results|quarterly results|"
    r"reports (?:first|second|third|fourth|fiscal|quarterly)|"
    r"q[1-4] 20\d\d|quarter(?:ly)? (?:earnings|results)|"
    r"fiscal 20\d\d results",
    re.IGNORECASE,
)


async def _get_latest_8k_url(
    client: httpx.AsyncClient, cik: str
) -> tuple[str | None, str]:
    """Find the most recent 8-K earnings press release document URL.

    Looks for 8-Ks with earnings indicators (Item 2.02 or earnings keywords).
    Scans up to 20 recent 8-Ks to find one with EX-99 press release.
    """
    try:
        r = await client.get(f"{_EDGAR_BASE}/submissions/CIK{cik}.json")
        if r.status_code != 200:
            return None, ""

        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        dates = filings.get("filingDate", [])
        items = filings.get("items", [])  # e.g. "2.02,9.01" for earnings releases

        scanned = 0
        for i, form in enumerate(forms):
            if form != "8-K":
                continue
            if scanned >= 15:
                break
            scanned += 1

            # Prefer 8-Ks with Item 2.02 (Results of Operations = earnings)
            filing_items = str(items[i]) if i < len(items) else ""
            is_earnings = "2.02" in filing_items

            acc_dash = accessions[i]
            acc = acc_dash.replace("-", "")
            period = dates[i][:7] if dates else ""

            # Fetch the filing index
            index_url = (
                f"{_EDGAR_ARCHIVES}/Archives/edgar/data/{int(cik)}/{acc}/{acc_dash}-index.htm"
            )
            r2 = await client.get(index_url, timeout=15)
            if r2.status_code != 200:
                continue

            # Look for EX-99 exhibit links
            ex99_links = re.findall(
                r'href="(/Archives/edgar/data/[^"]+\.(?:htm|html|txt))"',
                r2.text,
                re.IGNORECASE,
            )
            for link in ex99_links:
                name = link.split("/")[-1].lower()
                if any(kw in name for kw in ("ex99", "ex-99", "exhibit99")):
                    doc_url = f"{_EDGAR_ARCHIVES}{link}"
                    # Verify the content is earnings-related
                    if is_earnings:
                        return doc_url, period
                    # If not confirmed earnings, do a quick content check
                    r3 = await client.get(doc_url, timeout=15)
                    if r3.status_code == 200:
                        preview = r3.text[:3000]
                        if _EARNINGS_KEYWORDS.search(preview):
                            return doc_url, period
                    break  # move to next 8-K

    except Exception as e:
        logger.debug("8-K URL fetch failed for CIK %s: %s", cik, e)
    return None, ""


def _clean_html(text: str) -> str:
    """Strip HTML and decode entities."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&#160;|&nbsp;", " ", text)
    text = re.sub(r"&#8217;|&rsquo;", "'", text)
    text = re.sub(r"&#8220;|&ldquo;|&#8221;|&rdquo;", '"', text)
    text = re.sub(r"&#8212;|&mdash;", "—", text)
    text = re.sub(r"&#8211;|&ndash;", "-", text)
    text = re.sub(r"&#x2022;|&bull;", "•", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#\d+;|&\w+;", " ", text)
    text = re.sub(r"\s{3,}", "\n\n", text)
    # Strip document filing header artifacts: any word ending in .htm or .html
    # followed by boilerplate like "EX-99.1 Document Exhibit 99.1"
    text = re.sub(
        r"^\S*\.html?\S*\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^(?:EX-99\S*\s+\d*\s*){1,4}",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^(?:Document\s+)?(?:Exhibit\s+\d+\.\d+\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def _parse_press_release(text: str) -> dict:
    """Extract prepared remarks, guidance, and highlights from 8-K press release."""
    # Find the start of actual content (skip boilerplate/legal headers)
    content_start = _find_content_start(text)
    body = text[content_start:content_start + 8000]

    # Prepared remarks: first substantial block
    prepared_remarks = _clean(body, _PREPARED_LIMIT)

    # Guidance sentences
    sentences = re.split(r"(?<=[.!?])\s+", body)
    guidance_sents = [
        s.strip() for s in sentences
        if _GUIDANCE_KEYWORDS.search(s) and len(s.strip()) > 30
    ]
    guidance_text = " ".join(guidance_sents[:8])
    guidance_snippets = _clean(guidance_text, _GUIDANCE_LIMIT)

    # Q&A not applicable for press releases — use financial highlights
    highlights = _extract_highlights(body)
    qa_highlights = _clean(highlights, _QA_LIMIT)

    return {
        "prepared_remarks": prepared_remarks,
        "guidance_snippets": guidance_snippets,
        "qa_highlights": qa_highlights,
    }


def _find_content_start(text: str) -> int:
    """Skip legal boilerplate and HTML artifact headers at the start of a press release."""
    # Skip document filename artifacts (e.g. "EX-99.1 2 filename.htm EX-99.1 Document Exhibit 99.1")
    # Look for the first substantive marker
    markers = [
        r"reports (?:first|second|third|fourth|fiscal|quarterly|annual)",
        r"announces (?:first|second|third|fourth|fiscal|quarterly|financial)",
        r"(?:revenue|net income|earnings per share) (?:of|was|were)",
        r"(?:first|second|third|fourth) quarter (?:fiscal|financial|20\d\d)",
        r"FOR IMMEDIATE RELEASE",
        r"Highlights?\s*\n",
        r"Financial (?:Summary|Highlights|Results)",
        r"\$[\d,.]+\s*(?:billion|million)\s*(?:in )?(?:revenue|sales)",
        r"Q[1-4] 20\d\d",
    ]
    best = len(text)
    for pat in markers:
        m = re.search(pat, text[:8000], re.IGNORECASE)
        if m and m.start() < best:
            best = m.start()
    # No back-up — start exactly at the marker
    return best if best < len(text) else 0


def _extract_highlights(text: str) -> str:
    """Extract key financial bullet points from press release body."""
    # Look for revenue/EPS mentions
    highlights = []
    patterns = [
        r"(?:revenue|net sales)[^.]{0,100}\$[\d,.]+[^.]*\.",
        r"(?:earnings per share|EPS)[^.]{0,80}\$[\d,.]+[^.]*\.",
        r"(?:net income|operating income)[^.]{0,100}\$[\d,.]+[^.]*\.",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            highlights.append(m.group(0).strip())
    return " ".join(highlights[:3])


def _parse_transcript(content: str) -> dict:
    """Parse FMP-format earnings call transcript."""
    qa_split = re.split(
        r"\n(?:Question(?:\-and\-Answer)?\s*Session|Operator[:\s]|Q\s*&\s*A)",
        content,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    prepared_section = qa_split[0] if qa_split else content
    qa_section = qa_split[1] if len(qa_split) > 1 else ""

    prepared_body = _skip_boilerplate(prepared_section)
    prepared_remarks = _clean(prepared_body, _PREPARED_LIMIT)

    sentences = re.split(r"(?<=[.!?])\s+", prepared_section)
    guidance_sents = [
        s.strip() for s in sentences
        if _GUIDANCE_KEYWORDS.search(s) and len(s.strip()) > 30
    ]
    guidance_snippets = _clean(" ".join(guidance_sents), _GUIDANCE_LIMIT)
    qa_highlights = _clean(qa_section[:2000], _QA_LIMIT) if qa_section else ""

    return {
        "prepared_remarks": prepared_remarks,
        "guidance_snippets": guidance_snippets,
        "qa_highlights": qa_highlights,
    }


def _skip_boilerplate(text: str) -> str:
    """Skip forward-looking statement disclaimers."""
    m = re.search(
        r"\n[A-Z][a-zA-Z\s]+(?:CEO|CFO|President|Chief)[^:]*:(.+)",
        text,
        re.DOTALL,
    )
    if m:
        return text[m.start():]
    return text[300:] if len(text) > 300 else text


def _clean(text: str, limit: int) -> str:
    """Strip whitespace and truncate cleanly at sentence boundary."""
    text = re.sub(r"\s{2,}", " ", text.strip())
    if len(text) > limit:
        truncated = text[:limit]
        last_period = truncated.rfind(".")
        if last_period > limit * 0.6:
            truncated = truncated[: last_period + 1]
        return truncated + "…"
    return text

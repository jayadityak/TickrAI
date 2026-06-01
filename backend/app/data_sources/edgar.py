"""SEC EDGAR filing fetcher.

Fetches sections from the most recent 10-K:
- Business Description (Item 1)
- Risk Factors (Item 1A)
- Auditor Opinion (Item 9A)

Token-optimized: sections are hard-truncated before LLM injection.
Cache: 24h.
"""

import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

# Cache: ticker -> (timestamp, sections_dict)
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 86400  # 24 hours

# Separate caches for 10-Q and 8-K
_10q_cache: dict[str, tuple[float, str]] = {}
_8k_cache: dict[str, tuple[float, list]] = {}
_8K_CACHE_TTL = 14400  # 4 hours

_EDGAR_BASE = "https://data.sec.gov"
_EDGAR_ARCHIVES = "https://www.sec.gov"
_HEADERS = {"User-Agent": "TickrAI research@tickr.ai"}

# Hard token budget per section (chars ≈ tokens * 4)
_LIMITS = {
    "business": 1500,
    "risk_factors": 2000,
    "auditor": 1000,
    "mda": 8000,
}


async def get_10k_sections(ticker: str) -> dict:
    """Return truncated 10-K text sections for a ticker.

    Returns a dict with keys: business, risk_factors, auditor.
    Any section that can't be fetched is an empty string.
    Graceful fallback: returns empty dict on any error.
    """
    symbol = ticker.upper()

    # Check cache
    now = time.time()
    if symbol in _cache:
        ts, data = _cache[symbol]
        if now - ts < _CACHE_TTL:
            return data

    try:
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
            # Step 1: CIK lookup
            cik = await _get_cik(client, symbol)
            if not cik:
                logger.info("EDGAR: no CIK found for %s", symbol)
                return {}

            # Step 2: Get most recent 10-K filing URL
            filing_url = await _get_latest_10k_url(client, cik)
            if not filing_url:
                logger.info("EDGAR: no 10-K found for %s (CIK %s)", symbol, cik)
                return {}

            # Step 3: Fetch the filing document
            filing_text = await _fetch_filing_text(client, filing_url)
            if not filing_text:
                return {}

            # Step 4: Extract and truncate sections
            sections = _extract_sections(filing_text)
            _cache[symbol] = (now, sections)
            logger.info(
                "EDGAR: fetched 10-K for %s — business=%d chars, risk=%d chars, auditor=%d chars",
                symbol,
                len(sections.get("business", "")),
                len(sections.get("risk_factors", "")),
                len(sections.get("auditor", "")),
            )
            return sections

    except Exception as e:
        logger.warning("EDGAR fetch failed for %s: %s", symbol, e)
        return {}


async def _get_cik(client: httpx.AsyncClient, symbol: str) -> str | None:
    """Look up CIK number for a ticker symbol."""
    try:
        r = await client.get(
            f"{_EDGAR_BASE}/submissions/",
            params={"action": "getcompany", "company": symbol, "type": "10-K", "dateb": "", "owner": "include", "count": "1"},
        )
        # Try the company tickers JSON instead — more reliable
        r2 = await client.get(
            "https://www.sec.gov/files/company_tickers.json",
        )
        if r2.status_code == 200:
            data = r2.json()
            for entry in data.values():
                if entry.get("ticker", "").upper() == symbol:
                    cik_raw = str(entry["cik_str"])
                    return cik_raw.zfill(10)
    except Exception as e:
        logger.warning("EDGAR CIK lookup failed for %s: %s", symbol, e)
    return None


async def _get_latest_10k_url(client: httpx.AsyncClient, cik: str) -> str | None:
    """Get the URL of the most recent 10-K filing document."""
    try:
        r = await client.get(f"{_EDGAR_BASE}/submissions/CIK{cik}.json")
        if r.status_code != 200:
            return None

        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accession_numbers = filings.get("accessionNumber", [])
        primary_docs = filings.get("primaryDocument", [])

        # Find most recent 10-K
        for i, form in enumerate(forms):
            if form in ("10-K", "10-K/A"):
                acc = accession_numbers[i].replace("-", "")
                doc = primary_docs[i]
                # Archives live on www.sec.gov, not data.sec.gov
                url = f"{_EDGAR_ARCHIVES}/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
                return url

    except Exception as e:
        logger.warning("EDGAR 10-K URL fetch failed for CIK %s: %s", cik, e)
    return None


async def _fetch_filing_text(client: httpx.AsyncClient, url: str) -> str:
    """Fetch the raw text of a 10-K filing document."""
    try:
        r = await client.get(url, timeout=30)
        if r.status_code != 200:
            return ""
        text = r.text
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Decode common HTML entities (preserve &#160; → space for now)
        text = re.sub(r"&#160;|&nbsp;", " ", text)
        text = re.sub(r"&#8217;|&rsquo;", "'", text)
        text = re.sub(r"&#8220;|&ldquo;", '"', text)
        text = re.sub(r"&#8221;|&rdquo;", '"', text)
        text = re.sub(r"&#8211;|&ndash;", "-", text)
        text = re.sub(r"&#8212;|&mdash;", "—", text)
        text = re.sub(r"&#174;|&reg;", "®", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&#\d+;", " ", text)  # strip remaining numeric entities
        text = re.sub(r"\s{3,}", "\n\n", text)
        return text
    except Exception as e:
        logger.warning("EDGAR filing fetch failed: %s", e)
        return ""


def _extract_sections(text: str) -> dict:
    """Extract Item 1, 1A, and 9A sections from filing text.

    Strategy: use PART I / PART II as body anchors (reliable across filings).
    iXBRL TOC has short entries; actual content starts after PART I header.
    Falls back to keyword search if structural anchors aren't found.
    """
    sections = {"business": "", "risk_factors": "", "auditor": ""}

    # --- Anchor: find PART I body start (skips TOC) ---
    # PART I appears in TOC as a label and again as the actual body start
    # The body occurrence is followed by substantive paragraphs
    part1_pos = _find_body_part(text, r"PART\s+I\b")
    part2_pos = _find_body_part(text, r"PART\s+II\b")

    search_base = part1_pos if part1_pos is not None else 0

    # --- Business (Item 1) + Risk Factors (Item 1A) ---
    # Pick the Item 1 / Item 1A pair with the most content between them
    # (TOC has very little; body has many paragraphs)
    business_start, risk_start = _find_best_item_pair(text, search_base)

    if business_start is not None and risk_start is not None:
        raw = text[business_start:risk_start]
        sections["business"] = _clean(raw, _LIMITS["business"])

    # --- Risk Factors (Item 1A) ---
    if risk_start is not None:
        item1b = _find_after(text, r"Item\s+1[BC]\b", risk_start + 200)
        item2 = _find_after(text, r"Item\s+2\b", risk_start + 200)
        candidates = [x for x in [item1b, item2] if x is not None]
        end = min(candidates) if candidates else risk_start + 30000
        raw = text[risk_start:end]
        sections["risk_factors"] = _clean(raw, _LIMITS["risk_factors"])

    # --- Auditor / Controls (Item 9A or Report of Independent) ---
    # Look in Part II region or whole doc
    part2_base = part2_pos if part2_pos is not None else (len(text) // 2)
    auditor_start = _find_after(text, r"Report of Independent Registered", part2_base)
    if auditor_start is None:
        auditor_start = _find_after(text, r"Item\s+9A\.\s+Controls", part2_base)
    if auditor_start is None:
        # Last resort: search whole document
        auditor_start = _find_after(text, r"Report of Independent", 0)

    if auditor_start is not None:
        item9b = _find_after(text, r"Item\s+9B", auditor_start + 200)
        end = item9b if item9b else auditor_start + 8000
        raw = text[auditor_start:end]
        sections["auditor"] = _clean(raw, _LIMITS["auditor"])

    return sections


_XREF_PATTERN = re.compile(
    r"^\s*(of\s+this\s+Form|under\s+the\s+heading|in\s+Part|see\s+also|pursuant\s+to)",
    re.IGNORECASE,
)


def _find_best_item_pair(text: str, search_from: int = 0) -> tuple[int | None, int | None]:
    """Find the Item 1 / Item 1A pair with the most WORD content between them.

    The TOC pair has almost no content (just page numbers).
    Cross-reference occurrences like "see Item 1 of this Form 10-K" are excluded.
    The body pair has paragraphs of actual filing text.
    Returns (item1_pos, item1a_pos) of the best pair.
    """
    item1_matches = list(re.finditer(r"Item\s+1\b", text[search_from:], re.IGNORECASE))
    item1a_matches = list(re.finditer(r"Item\s+1A\b", text[search_from:], re.IGNORECASE))

    best_pair = (None, None)
    best_word_count = 50  # minimum words threshold

    for m1 in item1_matches:
        pos1 = search_from + m1.start()
        # Skip cross-references: "Item 1 of this Form...", "Item 1 under..."
        after_item1 = text[pos1 + len(m1.group()):pos1 + len(m1.group()) + 80]
        if _XREF_PATTERN.match(after_item1):
            continue

        # Find nearest non-cross-reference Item 1A after this Item 1
        for m1a in item1a_matches:
            pos1a = search_from + m1a.start()
            if pos1a <= pos1:
                continue
            after_item1a = text[pos1a + len(m1a.group()):pos1a + len(m1a.group()) + 80]
            if _XREF_PATTERN.match(after_item1a):
                continue

            gap = pos1a - pos1
            if gap < 100 or gap > 60000:
                break  # too small (TOC) or too large (spanning sections)

            # Count meaningful words in the gap
            gap_text = text[pos1:pos1a]
            word_count = len(re.findall(r"[a-zA-Z]{4,}", gap_text))
            if word_count > best_word_count:
                best_word_count = word_count
                best_pair = (pos1, pos1a)
            break  # nearest 1A only

    return best_pair


def _find_body_part(text: str, pattern: str) -> int | None:
    """Find the LAST occurrence of a PART I/II marker (body, not TOC).

    The TOC has an early short occurrence; the body occurrence is the one
    followed by Item sub-headers with actual content.
    """
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    if not matches:
        return None

    # The body occurrence has more content after it than the TOC
    best_pos = None
    best_len = -1
    for m in matches:
        pos = m.start()
        # Check if next 500 chars have actual paragraph content (not just page numbers)
        snippet = text[pos + len(m.group()):pos + 2000]
        # Count words (real content vs page numbers)
        word_count = len(re.findall(r"[a-zA-Z]{4,}", snippet))
        if word_count > best_len:
            best_len = word_count
            best_pos = pos

    return best_pos


def _find_after(text: str, pattern: str, after: int) -> int | None:
    """Find first match of pattern at or after position `after`."""
    m = re.search(pattern, text[after:], re.IGNORECASE)
    return after + m.start() if m else None


def _clean(text: str, limit: int) -> str:
    """Strip excess whitespace and truncate to limit chars."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    text = re.sub(r" {2,}", " ", text)
    if len(text) > limit:
        # Truncate at last sentence boundary within limit
        truncated = text[:limit]
        last_period = truncated.rfind(".")
        if last_period > limit * 0.7:
            truncated = truncated[: last_period + 1]
        return truncated + "…"
    return text


# ---------------------------------------------------------------------------
# 10-Q MD&A fetcher

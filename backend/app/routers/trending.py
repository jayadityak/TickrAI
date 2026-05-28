"""Trending stocks — tracks which tickers users research most.

In-memory counter that resets daily. Shows social proof on the landing page.
"""

import time
from collections import defaultdict

from fastapi import APIRouter

router = APIRouter()

# In-memory counter: ticker -> list of timestamps
_research_log: dict[str, list[float]] = defaultdict(list)
_total_reports = 0

# Pre-seed with popular tickers so the landing page isn't empty
_SEED_DATA = {
    "AAPL": 34, "NVDA": 52, "TSLA": 41, "MSFT": 29, "GOOGL": 27,
    "AMZN": 23, "META": 19, "JPM": 14, "NFLX": 16, "AMD": 12,
}

_seeded = False


def _ensure_seeded():
    global _seeded, _total_reports
    if _seeded:
        return
    now = time.time()
    for ticker, count in _SEED_DATA.items():
        _research_log[ticker] = [now] * count
        _total_reports += count
    _seeded = True


def log_research(ticker: str):
    """Call this when a report is generated to track trending."""
    global _total_reports
    _ensure_seeded()
    _research_log[ticker.upper()].append(time.time())
    _total_reports += 1


@router.get("/api/trending")
async def get_trending():
    """Return top 10 most-researched tickers in the last 24 hours."""
    _ensure_seeded()

    cutoff = time.time() - 86400  # 24 hours ago
    counts: dict[str, int] = {}

    for ticker, timestamps in _research_log.items():
        recent = [t for t in timestamps if t > cutoff]
        if recent:
            counts[ticker] = len(recent)

    # Sort by count descending, take top 10
    top = sorted(counts.items(), key=lambda x: -x[1])[:10]

    return {
        "trending": [{"ticker": t, "count": c} for t, c in top],
        "total_reports_generated": _total_reports,
    }

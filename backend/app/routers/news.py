"""News sentiment for a stock.

Fetches recent headlines from yfinance, scores sentiment with OpenAI.
Cached for 1 hour per ticker.
"""

import json
import logging
import time

import yfinance as yf
from openai import AsyncOpenAI
from fastapi import APIRouter

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache: ticker -> (timestamp, result)
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hour


def _fetch_headlines(symbol: str) -> list[dict]:
    """Get recent news headlines from yfinance."""
    try:
        t = yf.Ticker(symbol)
        raw_news = t.news or []
        headlines = []
        for item in raw_news[:10]:
            content = item.get("content", {})
            title = content.get("title", "")
            summary = content.get("summary", "")
            pub_date = content.get("pubDate", "")
            thumb = None
            thumb_data = content.get("thumbnail", {})
            if thumb_data and thumb_data.get("resolutions"):
                # Get smallest thumbnail
                resolutions = thumb_data["resolutions"]
                thumb = resolutions[-1].get("url") if resolutions else None

            if title:
                headlines.append({
                    "title": title,
                    "summary": summary[:200] if summary else "",
                    "date": pub_date[:10] if pub_date else "",
                    "thumbnail": thumb,
                })
        return headlines
    except Exception as e:
        logger.warning("News fetch failed for %s: %s", symbol, e)
        return []


async def _score_sentiment(ticker: str, headlines: list[dict]) -> dict:
    """Use OpenAI to score sentiment of headlines."""
    if not settings.openai_api_key or not headlines:
        # Fallback: simple keyword-based scoring
        return _keyword_sentiment(headlines)

    titles = [h["title"] for h in headlines]
    prompt = f"""Analyze the sentiment of these news headlines about {ticker} stock.
For each headline, rate sentiment as "bullish", "bearish", or "neutral".
Also give an overall sentiment score from 1-10 (1=very bearish, 10=very bullish) and overall label.

Headlines:
{json.dumps(titles, indent=1)}

Respond ONLY in this exact JSON format:
{{"scores": ["bullish" or "bearish" or "neutral" for each headline], "overall_score": <1-10>, "overall_label": "bullish" or "bearish" or "neutral"}}"""

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0,
        )
        text = response.choices[0].message.content.strip()
        # Extract JSON
        if "```" in text:
            text = text.split("```")[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()
        result = json.loads(text)
        return result
    except Exception as e:
        logger.warning("Sentiment scoring failed for %s: %s", ticker, e)
        return _keyword_sentiment(headlines)


def _keyword_sentiment(headlines: list[dict]) -> dict:
    """Fallback keyword-based sentiment when OpenAI is unavailable."""
    bullish_words = {"surge", "soar", "beat", "gain", "rise", "up", "high", "growth", "profit", "record", "strong", "buy", "upgrade", "rally"}
    bearish_words = {"fall", "drop", "decline", "loss", "down", "low", "weak", "sell", "cut", "miss", "warning", "crash", "plunge", "downgrade"}

    scores = []
    bull_count = 0
    bear_count = 0
    for h in headlines:
        words = h["title"].lower().split()
        b = sum(1 for w in words if w in bullish_words)
        r = sum(1 for w in words if w in bearish_words)
        if b > r:
            scores.append("bullish")
            bull_count += 1
        elif r > b:
            scores.append("bearish")
            bear_count += 1
        else:
            scores.append("neutral")

    total = len(headlines) or 1
    score = round(5 + (bull_count - bear_count) / total * 3)
    score = max(1, min(10, score))
    label = "bullish" if score >= 6 else "bearish" if score <= 4 else "neutral"

    return {"scores": scores, "overall_score": score, "overall_label": label}


@router.get("/api/news/{ticker}")
async def get_news_sentiment(ticker: str):
    """Return news headlines with sentiment scores."""
    symbol = ticker.upper()

    # Check cache
    now = time.time()
    if symbol in _cache:
        ts, data = _cache[symbol]
        if now - ts < _CACHE_TTL:
            return data

    headlines = _fetch_headlines(symbol)
    sentiment = await _score_sentiment(symbol, headlines)

    # Merge scores into headlines
    scores = sentiment.get("scores", [])
    for i, h in enumerate(headlines):
        h["sentiment"] = scores[i] if i < len(scores) else "neutral"

    result = {
        "ticker": symbol,
        "headlines": headlines,
        "overall_score": sentiment.get("overall_score", 5),
        "overall_label": sentiment.get("overall_label", "neutral"),
    }

    _cache[symbol] = (now, result)
    return result

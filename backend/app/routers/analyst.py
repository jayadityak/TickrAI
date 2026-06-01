"""Wall Street analyst consensus data endpoint.

Aggregates analyst price targets, rating distributions, recent upgrades/downgrades,
EPS estimate trends, short interest, and key forward statistics — all via yfinance.

Completely free — no additional API key required.
Cache: 4 hours (analyst ratings update daily at most).
"""

import logging
import math
import time

import yfinance as yf
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 14400  # 4 hours


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sf(val, decimals: int = 2):
    """Safe float: returns None on NaN/None/inf."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, decimals)
    except (TypeError, ValueError):
        return None


def _rating_label(score: float | None) -> str:
    """Convert yfinance recommendation mean (1–5) to a label."""
    if score is None:
        return "N/A"
    if score <= 1.5:
        return "Strong Buy"
    if score <= 2.5:
        return "Buy"
    if score <= 3.5:
        return "Hold"
    if score <= 4.5:
        return "Sell"
    return "Strong Sell"


def _parse_recommendations(ticker_obj) -> dict:
    """Extract current-month analyst rating breakdown."""
    try:
        df = ticker_obj.recommendations_summary
        if df is None or df.empty:
            return {}
        # First row = most recent month
        row = df.iloc[0]
        strong_buy  = int(row.get("strongBuy",   0) or 0)
        buy         = int(row.get("buy",         0) or 0)
        hold        = int(row.get("hold",        0) or 0)
        sell        = int(row.get("sell",        0) or 0)
        strong_sell = int(row.get("strongSell",  0) or 0)
        total = strong_buy + buy + hold + sell + strong_sell
        if total == 0:
            return {}
        # Weighted score (1=Strong Buy → 5=Strong Sell)
        score = (strong_buy * 1 + buy * 2 + hold * 3 + sell * 4 + strong_sell * 5) / total
        return {
            "strong_buy":  strong_buy,
            "buy":         buy,
            "hold":        hold,
            "sell":        sell,
            "strong_sell": strong_sell,
            "total":       total,
            "score":       round(score, 2),
            "consensus":   _rating_label(score),
        }
    except Exception as e:
        logger.debug("recommendations_summary parse error: %s", e)
        return {}


def _parse_upgrades(ticker_obj, limit: int = 8) -> list[dict]:
    """Get most recent analyst rating changes."""
    try:
        df = ticker_obj.upgrades_downgrades
        if df is None or df.empty:
            return []
        # df index is GradeDate, columns: Firm, ToGrade, FromGrade, Action
        df = df.reset_index()
        results = []
        for _, row in df.head(limit).iterrows():
            date_raw = row.get("GradeDate", row.get("Date", ""))
            date_str = str(date_raw)[:10] if date_raw else "N/A"
            action = str(row.get("Action", "")).lower()
            to_grade   = str(row.get("ToGrade",   "")).strip()
            from_grade = str(row.get("FromGrade", "")).strip()
            firm       = str(row.get("Firm",      "")).strip()
            if not to_grade and not firm:
                continue
            # Classify direction
            upgrade_grades   = {"buy", "outperform", "overweight", "strong buy", "positive"}
            downgrade_grades = {"sell", "underperform", "underweight", "strong sell", "negative"}
            if action == "up" or to_grade.lower() in upgrade_grades:
                direction = "upgrade"
            elif action == "down" or to_grade.lower() in downgrade_grades:
                direction = "downgrade"
            else:
                direction = "maintain"
            results.append({
                "date":       date_str,
                "firm":       firm,
                "from_grade": from_grade or "N/A",
                "to_grade":   to_grade or "N/A",
                "direction":  direction,
            })
        return results
    except Exception as e:
        logger.debug("upgrades_downgrades parse error: %s", e)
        return []


def _parse_eps_trend(ticker_obj) -> dict:
    """Extract EPS estimate momentum — are estimates being revised up or down?"""
    try:
        df = ticker_obj.eps_trend
        if df is None or df.empty:
            return {}
        # Columns: current, 7daysAgo, 30daysAgo, 60daysAgo, 90daysAgo
        # Rows (index): 0q, +1q, 0y, +1y
        result = {}
        period_labels = {
            "0q":  "current_quarter",
            "+1q": "next_quarter",
            "0y":  "current_year",
            "+1y": "next_year",
        }
        for idx, label in period_labels.items():
            try:
                if idx not in df.index:
                    continue
                row = df.loc[idx]
                current   = _sf(row.get("current",    row.iloc[0] if len(row) else None))
                ago_30d   = _sf(row.get("30daysAgo",  None))
                ago_90d   = _sf(row.get("90daysAgo",  None))

                trend = "flat"
                if current is not None and ago_30d is not None and ago_30d != 0:
                    pct_chg = (current - ago_30d) / abs(ago_30d) * 100
                    if pct_chg > 0.5:
                        trend = "up"
                    elif pct_chg < -0.5:
                        trend = "down"

                result[label] = {
                    "estimate":  current,
                    "ago_30d":   ago_30d,
                    "ago_90d":   ago_90d,
                    "trend":     trend,
                }
            except Exception:
                continue
        return result
    except Exception as e:
        logger.debug("eps_trend parse error: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Main fetcher
# ---------------------------------------------------------------------------

def _fetch_analyst_data(symbol: str) -> dict:
    now = time.time()
    if symbol in _cache:
        ts, data = _cache[symbol]
        if now - ts < _CACHE_TTL:
            return data

    try:
        t = yf.Ticker(symbol)
        raw = t.info
        info = raw if isinstance(raw, dict) and raw else {}

        # ── Current price ──────────────────────────────────────────────────
        current_price = _sf(
            info.get("currentPrice") or info.get("regularMarketPrice"), 2
        )

        # ── Analyst price targets ──────────────────────────────────────────
        target_mean = _sf(info.get("targetMeanPrice"), 2)
        target_high = _sf(info.get("targetHighPrice"), 2)
        target_low  = _sf(info.get("targetLowPrice"),  2)
        n_analysts  = info.get("numberOfAnalystOpinions")
        upside_pct  = None
        if target_mean and current_price and current_price > 0:
            upside_pct = round((target_mean / current_price - 1) * 100, 1)

        price_targets = {
            "mean":        target_mean,
            "high":        target_high,
            "low":         target_low,
            "num_analysts": int(n_analysts) if n_analysts else None,
            "upside_pct":  upside_pct,
        }

        # ── Rating distribution ────────────────────────────────────────────
        rating_dist = _parse_recommendations(t)
        # Fallback: use info fields if recommendations_summary unavailable
        if not rating_dist:
            rec_mean = _sf(info.get("recommendationMean"))
            rec_key  = info.get("recommendationKey", "")
            if rec_key:
                rating_dist = {
                    "consensus": rec_key.title().replace("_", " "),
                    "score":     rec_mean,
                    "total":     n_analysts or 0,
                }

        # ── Recent upgrades/downgrades ─────────────────────────────────────
        recent_changes = _parse_upgrades(t, limit=8)

        # ── EPS estimate trend ─────────────────────────────────────────────
        eps_estimates = _parse_eps_trend(t)

        # ── Short interest ─────────────────────────────────────────────────
        short_pct = _sf(info.get("shortPercentOfFloat"), 4)
        short_ratio = _sf(info.get("shortRatio"), 2)
        short_interest = {
            "short_pct_float":   round(short_pct * 100, 2) if short_pct else None,
            "short_ratio":       short_ratio,
            "shares_short":      info.get("sharesShort"),
        }

        # ── Key forward stats ──────────────────────────────────────────────
        key_stats = {
            "beta":              _sf(info.get("beta"), 2),
            "forward_pe":        _sf(info.get("forwardPE"), 2),
            "trailing_pe":       _sf(info.get("trailingPE"), 2),
            "forward_eps":       _sf(info.get("forwardEps"), 2),
            "peg_ratio":         _sf(info.get("pegRatio"), 2),
            "price_to_book":     _sf(info.get("priceToBook"), 2),
            "ev_to_ebitda":      _sf(info.get("enterpriseToEbitda"), 2),
            "price_to_sales":    _sf(info.get("priceToSalesTrailing12Months"), 2),
            "dividend_yield":    round(_sf(info.get("dividendYield"), 4) * 100, 2) if _sf(info.get("dividendYield")) else None,
            "payout_ratio":      _sf(info.get("payoutRatio"), 3),
            "fifty_two_week_high": _sf(info.get("fiftyTwoWeekHigh"), 2),
            "fifty_two_week_low":  _sf(info.get("fiftyTwoWeekLow"), 2),
            "fifty_day_avg":     _sf(info.get("fiftyDayAverage"), 2),
            "two_hundred_day_avg": _sf(info.get("twoHundredDayAverage"), 2),
            "avg_volume":        info.get("averageVolume"),
            "market_cap":        info.get("marketCap"),
            "enterprise_value":  info.get("enterpriseValue"),
            "return_on_equity":  _sf(info.get("returnOnEquity"), 4),
            "return_on_assets":  _sf(info.get("returnOnAssets"), 4),
            "profit_margin":     _sf(info.get("profitMargins"), 4),
            "operating_margin":  _sf(info.get("operatingMargins"), 4),
            "gross_margin":      _sf(info.get("grossMargins"), 4),
            "revenue_growth":    _sf(info.get("revenueGrowth"), 4),
            "earnings_growth":   _sf(info.get("earningsGrowth"), 4),
            "debt_to_equity":    _sf(info.get("debtToEquity"), 2),
            "current_ratio":     _sf(info.get("currentRatio"), 2),
            "quick_ratio":       _sf(info.get("quickRatio"), 2),
            "total_cash":        info.get("totalCash"),
            "total_debt":        info.get("totalDebt"),
            "free_cashflow":     info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
        }

        # ── 52-week positioning ────────────────────────────────────────────
        hi = key_stats["fifty_two_week_high"]
        lo = key_stats["fifty_two_week_low"]
        pct_from_high = round((current_price / hi - 1) * 100, 1) if (current_price and hi) else None
        pct_from_low  = round((current_price / lo - 1) * 100, 1) if (current_price and lo) else None

        data = {
            "ticker":          symbol,
            "company_name":    info.get("shortName") or info.get("longName") or symbol,
            "current_price":   current_price,
            "currency":        info.get("currency", "USD"),
            "price_targets":   price_targets,
            "rating_dist":     rating_dist,
            "recent_changes":  recent_changes,
            "eps_estimates":   eps_estimates,
            "short_interest":  short_interest,
            "key_stats":       key_stats,
            "pct_from_52w_high": pct_from_high,
            "pct_from_52w_low":  pct_from_low,
        }

        _cache[symbol] = (now, data)
        logger.info(
            "Analyst data for %s — consensus=%s, target=$%s, analysts=%s",
            symbol,
            rating_dist.get("consensus", "?"),
            target_mean,
            price_targets.get("num_analysts"),
        )
        return data

    except Exception as e:
        logger.warning("Analyst fetch failed for %s: %s", symbol, e)
        return {"ticker": symbol, "error": str(e)}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/api/analyst/{ticker}")
async def get_analyst_consensus(ticker: str):
    """Return Wall Street analyst consensus data for a ticker."""
    return _fetch_analyst_data(ticker.upper())

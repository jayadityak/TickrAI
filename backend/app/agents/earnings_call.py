"""Agent 5 — Earnings Call Analysis.

Uses yfinance earnings/estimate data as a proxy for earnings-call
insights.  Full transcript analysis would require an external data
source (e.g. Financial Modeling Prep API, SEC EDGAR 8-K filings).

TODO: Integrate FMP or another transcript provider for verbatim
      earnings-call transcript analysis, sentiment scoring, and
      management-quote extraction.
"""

import asyncio
import json
import logging
import math

import pandas as pd
import yfinance as yf

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


def _safe_value(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item"):
        return v.item()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _df_to_records(df: pd.DataFrame | None, max_rows: int = 20) -> list[dict] | None:
    """Convert a DataFrame to a list of dicts, sanitising values."""
    if df is None or df.empty:
        return None
    records = df.head(max_rows).to_dict(orient="records")
    for row in records:
        for k, v in list(row.items()):
            row[k] = _safe_value(v)
    return records


class EarningsCallAgent(BaseAgent):
    name: str = "Earnings Call"
    index: int = 5

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        result: dict = {
            "earnings_dates": None,
            "earnings_history": None,
            "revenue_estimates": None,
            "earnings_estimates": None,
            "info_forward": {},
            "errors": [],
            "notes": [
                "Full earnings-call transcripts are not available via yfinance. "
                "This analysis is based on earnings history, analyst estimates, "
                "and forward guidance metrics. For production, integrate an "
                "earnings transcript API (e.g. FMP, Seeking Alpha)."
            ],
        }

        try:
            stock = await asyncio.to_thread(yf.Ticker, ticker)

            # --- earnings dates ---------------------------------------------
            try:
                ed = await asyncio.to_thread(lambda: stock.earnings_dates)
                result["earnings_dates"] = _df_to_records(ed, max_rows=8)
            except Exception as exc:
                logger.warning("earnings_dates error for %s: %s", ticker, exc)
                result["errors"].append(f"earnings_dates: {exc}")

            # --- earnings history -------------------------------------------
            try:
                eh = await asyncio.to_thread(lambda: stock.earnings_history)
                result["earnings_history"] = _df_to_records(eh)
            except Exception as exc:
                logger.warning("earnings_history error for %s: %s", ticker, exc)
                result["errors"].append(f"earnings_history: {exc}")

            # --- analyst revenue estimates ----------------------------------
            try:
                re = await asyncio.to_thread(lambda: stock.revenue_estimate)
                result["revenue_estimates"] = _df_to_records(re)
            except Exception as exc:
                logger.warning("revenue_estimate error for %s: %s", ticker, exc)
                result["errors"].append(f"revenue_estimates: {exc}")

            # --- analyst earnings estimates ---------------------------------
            try:
                ee = await asyncio.to_thread(lambda: stock.earnings_estimate)
                result["earnings_estimates"] = _df_to_records(ee)
            except Exception as exc:
                logger.warning("earnings_estimate error for %s: %s", ticker, exc)
                result["errors"].append(f"earnings_estimates: {exc}")

            # --- forward-looking info keys ----------------------------------
            try:
                _raw = await asyncio.to_thread(lambda: stock.info)
                info = _raw if isinstance(_raw, dict) and _raw else {}
                fwd_keys = [
                    "forwardPE",
                    "forwardEps",
                    "pegRatio",
                    "earningsGrowth",
                    "revenueGrowth",
                    "earningsQuarterlyGrowth",
                    "revenuePerShare",
                    "targetHighPrice",
                    "targetLowPrice",
                    "targetMeanPrice",
                    "targetMedianPrice",
                    "numberOfAnalystOpinions",
                    "recommendationKey",
                    "recommendationMean",
                ]
                for k in fwd_keys:
                    v = info.get(k)
                    result["info_forward"][k] = _safe_value(v)
            except Exception as exc:
                logger.warning("info (forward) error for %s: %s", ticker, exc)
                result["errors"].append(f"info_forward: {exc}")

        except Exception as exc:
            logger.exception("Fatal error in EarningsCallAgent.fetch_data for %s", ticker)
            result["errors"].append(f"fatal: {exc}")

        return result

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        data_json = json.dumps(raw_data, indent=2, default=str)

        return f"""Analyse earnings-related data for **{company_data.get('company_name', ticker)}** ({ticker}).

=== RAW DATA ===
{data_json}

=== INSTRUCTIONS ===
Although full earnings-call transcripts are unavailable, use the earnings
history, analyst estimates, forward guidance metrics, and beat/miss track
record to infer management sentiment and outlook.

Produce a JSON object with exactly these keys:

{{
  "summary": "<2-3 sentence overview of recent earnings performance and outlook>",
  "management_tone": "bullish" | "neutral" | "bearish",
  "key_themes": ["<theme 1>", "<theme 2>", "..."],
  "guidance": {{
    "revenue_guidance": "<description of consensus revenue expectations>",
    "earnings_guidance": "<description of consensus EPS expectations>",
    "commentary": "<overall forward-looking commentary>"
  }},
  "analyst_concerns": ["<concern 1>", "..."],
  "forward_outlook": "<paragraph summarising the forward outlook based on available data>"
}}

Base the management_tone on the earnings beat/miss pattern and growth trajectory.
If estimates show accelerating growth, lean bullish; if decelerating, lean bearish.
Use null for fields where data is truly insufficient."""

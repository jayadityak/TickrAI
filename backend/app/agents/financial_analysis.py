"""Agent 2 — Financial Analysis.

Pulls quarterly and annual financials from yfinance and asks an LLM
to produce trend analysis and key metrics.
"""

import asyncio
import json
import logging
import math

import pandas as pd
import yfinance as yf

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


def _df_to_serialisable(df: pd.DataFrame | None) -> dict | None:
    """Convert a pandas DataFrame to a JSON-safe dict.

    * Transposes so that each key is a date-string and value is a row dict.
    * Replaces NaN / inf with None.
    """
    if df is None or df.empty:
        return None

    out: dict = {}
    for col in df.columns:
        col_key = col.isoformat() if hasattr(col, "isoformat") else str(col)
        row: dict = {}
        for idx, val in df[col].items():
            idx_key = str(idx)
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                val = None
            elif hasattr(val, "item"):
                val = val.item()  # numpy scalar -> python scalar
            row[idx_key] = val
        out[col_key] = row
    return out


class FinancialAnalysisAgent(BaseAgent):
    name: str = "Financial Analysis"
    index: int = 2

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        result: dict = {
            "quarterly_financials": None,
            "annual_financials": None,
            "price_info": {},
            "errors": [],
        }

        try:
            stock = await asyncio.to_thread(yf.Ticker, ticker)

            # --- quarterly income statement (last 8 quarters) ---------------
            try:
                q_fin = await asyncio.to_thread(lambda: stock.quarterly_income_stmt)
                result["quarterly_financials"] = _df_to_serialisable(q_fin)
            except Exception as exc:
                logger.warning("quarterly_income_stmt error for %s: %s", ticker, exc)
                result["errors"].append(f"quarterly_financials: {exc}")

            # --- annual income statement (last 5 years) ---------------------
            try:
                a_fin = await asyncio.to_thread(lambda: stock.income_stmt)
                result["annual_financials"] = _df_to_serialisable(a_fin)
            except Exception as exc:
                logger.warning("income_stmt error for %s: %s", ticker, exc)
                result["errors"].append(f"annual_financials: {exc}")

            # --- price / valuation metrics ----------------------------------
            try:
                info = await asyncio.to_thread(lambda: stock.info)
                price_keys = [
                    "currentPrice",
                    "marketCap",
                    "trailingPE",
                    "forwardPE",
                    "priceToBook",
                    "dividendYield",
                    "trailingEps",
                    "forwardEps",
                    "enterpriseValue",
                    "enterpriseToRevenue",
                    "enterpriseToEbitda",
                ]
                for k in price_keys:
                    v = info.get(k)
                    if v is not None:
                        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                            v = None
                        result["price_info"][k] = v
            except Exception as exc:
                logger.warning("info (price) error for %s: %s", ticker, exc)
                result["errors"].append(f"price_info: {exc}")

        except Exception as exc:
            logger.exception("Fatal error in FinancialAnalysisAgent.fetch_data for %s", ticker)
            result["errors"].append(f"fatal: {exc}")

        return result

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        data_json = json.dumps(raw_data, indent=2, default=str)

        return f"""You are analysing the financials of **{company_data.get('company_name', ticker)}** ({ticker}).

=== RAW FINANCIAL DATA ===
{data_json}

=== INSTRUCTIONS ===
Using the data above, produce a JSON object with exactly these keys:

{{
  "summary": "<2-3 sentence executive summary of financial health>",
  "annual_trends": [
    {{
      "year": "<YYYY or fiscal year label>",
      "revenue": <number or null>,
      "net_income": <number or null>,
      "eps": <number or null>,
      "ebitda_margin": <decimal 0-1 or null>,
      "net_margin": <decimal 0-1 or null>
    }}
  ],
  "quarterly_trends": [
    {{
      "quarter": "<e.g. Q1 2024>",
      "revenue": <number or null>,
      "net_income": <number or null>,
      "revenue_growth_yoy": <decimal or null>
    }}
  ],
  "key_metrics": {{
    "pe_ratio": <number or null>,
    "market_cap": <number or null>,
    "price_to_book": <number or null>,
    "dividend_yield": <decimal or null>
  }},
  "analysis": "<paragraph-length narrative covering revenue trajectory, profitability trends, and notable inflection points>"
}}

Derive margins from the income statement data. Use null when data is unavailable rather than guessing.
Order annual_trends oldest-to-newest and quarterly_trends oldest-to-newest."""

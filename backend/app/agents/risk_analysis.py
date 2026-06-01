"""Agent 3 — Risk Analysis.

Examines balance-sheet health, cash-flow adequacy and key financial
ratios to surface leverage, liquidity, and operational risks.
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
    """Return *v* as a JSON-safe Python scalar."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item"):
        return v.item()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _df_to_dict(df: pd.DataFrame | None) -> dict | None:
    if df is None or df.empty:
        return None
    out: dict = {}
    for col in df.columns:
        col_key = col.isoformat() if hasattr(col, "isoformat") else str(col)
        out[col_key] = {str(idx): _safe_value(val) for idx, val in df[col].items()}
    return out


class RiskAnalysisAgent(BaseAgent):
    name: str = "Risk Analysis"
    index: int = 3

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        result: dict = {
            "balance_sheet": None,
            "cash_flow": None,
            "risk_ratios": {},
            "errors": [],
        }

        try:
            stock = await asyncio.to_thread(yf.Ticker, ticker)

            # --- balance sheet ----------------------------------------------
            try:
                bs = await asyncio.to_thread(lambda: stock.balance_sheet)
                result["balance_sheet"] = _df_to_dict(bs)
            except Exception as exc:
                logger.warning("balance_sheet error for %s: %s", ticker, exc)
                result["errors"].append(f"balance_sheet: {exc}")

            # --- cash flow statement ----------------------------------------
            try:
                cf = await asyncio.to_thread(lambda: stock.cashflow)
                result["cash_flow"] = _df_to_dict(cf)
            except Exception as exc:
                logger.warning("cashflow error for %s: %s", ticker, exc)
                result["errors"].append(f"cash_flow: {exc}")

            # --- risk-relevant ratios from info -----------------------------
            try:
                _raw = await asyncio.to_thread(lambda: stock.info)
                info = _raw if isinstance(_raw, dict) and _raw else {}
                ratio_keys = [
                    "debtToEquity",
                    "currentRatio",
                    "quickRatio",
                    "totalDebt",
                    "totalCash",
                    "freeCashflow",
                    "operatingCashflow",
                    "returnOnEquity",
                    "grossMargins",
                    "operatingMargins",
                    "shortRatio",
                    "beta",
                ]
                for k in ratio_keys:
                    v = info.get(k)
                    result["risk_ratios"][k] = _safe_value(v)
            except Exception as exc:
                logger.warning("info (ratios) error for %s: %s", ticker, exc)
                result["errors"].append(f"risk_ratios: {exc}")

        except Exception as exc:
            logger.exception("Fatal error in RiskAnalysisAgent.fetch_data for %s", ticker)
            result["errors"].append(f"fatal: {exc}")

        return result

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        data_json = json.dumps(raw_data, indent=2, default=str)

        return f"""Perform a risk assessment for **{company_data.get('company_name', ticker)}** ({ticker}).

=== RAW DATA ===
{data_json}

=== COMPANY CONTEXT ===
Sector: {company_data.get('sector', 'N/A')}
Industry: {company_data.get('industry', 'N/A')}

=== INSTRUCTIONS ===
Analyse the balance sheet, cash flow statement, and key ratios provided.
Produce a JSON object with exactly these keys:

{{
  "overall_risk_level": "Low" | "Medium" | "High",
  "risks": [
    {{
      "category": "<one of: leverage_risk, liquidity_risk, cash_flow_risk, concentration_risk, regulatory_risk>",
      "severity": <integer 1-5>,
      "description": "<concise explanation>",
      "evidence": "<specific numbers or ratios supporting this>"
    }}
  ],
  "leverage_risk": {{"level": "Low"|"Medium"|"High", "detail": "..."}},
  "liquidity_risk": {{"level": "Low"|"Medium"|"High", "detail": "..."}},
  "cash_flow_risk": {{"level": "Low"|"Medium"|"High", "detail": "..."}},
  "concentration_risk": {{"level": "Low"|"Medium"|"High", "detail": "..."}},
  "regulatory_risk": {{"level": "Low"|"Medium"|"High", "detail": "..."}}
}}

Include at least one risk entry per category. Use specific numbers from the data as evidence.
If data for a category is insufficient, still include the category with a note about limited data."""

"""Agent 4 — Auditor Flags.

Reviews financial data for potential governance, accounting, or audit
concerns.  Since yfinance does not expose auditor opinions directly,
the agent relies on financial-statement signals and corporate actions.

TODO: Enhance with SEC EDGAR 10-K parsing to pull actual auditor
      opinion letters, going-concern qualifications, and internal-
      control disclosures (Item 9A).
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


def _df_to_dict(df: pd.DataFrame | None) -> dict | None:
    if df is None or df.empty:
        return None
    out: dict = {}
    for col in df.columns:
        col_key = col.isoformat() if hasattr(col, "isoformat") else str(col)
        out[col_key] = {str(idx): _safe_value(val) for idx, val in df[col].items()}
    return out


class AuditorFlagsAgent(BaseAgent):
    name: str = "Auditor Flags"
    index: int = 4

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        result: dict = {
            "info_snapshot": {},
            "actions": {},
            "income_stmt": None,
            "balance_sheet": None,
            "errors": [],
            "notes": [
                "yfinance does not provide auditor opinion letters. "
                "For production use, integrate SEC EDGAR 10-K parsing "
                "(Items 8 & 9A) to extract auditor opinions, going-concern "
                "qualifications, and internal control assessments."
            ],
        }

        try:
            stock = await asyncio.to_thread(yf.Ticker, ticker)

            # --- info snapshot for governance signals -----------------------
            try:
                info = await asyncio.to_thread(lambda: stock.info)
                gov_keys = [
                    "auditRisk",
                    "boardRisk",
                    "compensationRisk",
                    "shareHolderRightsRisk",
                    "overallRisk",
                    "heldPercentInsiders",
                    "heldPercentInstitutions",
                    "shortRatio",
                    "shortPercentOfFloat",
                    "payoutRatio",
                    "debtToEquity",
                    "currentRatio",
                    "freeCashflow",
                    "operatingCashflow",
                    "netIncomeToCommon",
                ]
                for k in gov_keys:
                    v = info.get(k)
                    result["info_snapshot"][k] = _safe_value(v)
            except Exception as exc:
                logger.warning("info error for %s: %s", ticker, exc)
                result["errors"].append(f"info: {exc}")

            # --- corporate actions (dividends, splits, capital gains) -------
            try:
                actions = await asyncio.to_thread(lambda: stock.actions)
                if actions is not None and not actions.empty:
                    recent = actions.tail(10)
                    result["actions"] = _df_to_dict(recent.T) if not recent.empty else {}
            except Exception as exc:
                logger.warning("actions error for %s: %s", ticker, exc)
                result["errors"].append(f"actions: {exc}")

            # --- income statement (for accruals analysis) -------------------
            try:
                inc = await asyncio.to_thread(lambda: stock.income_stmt)
                result["income_stmt"] = _df_to_dict(inc)
            except Exception as exc:
                logger.warning("income_stmt error for %s: %s", ticker, exc)
                result["errors"].append(f"income_stmt: {exc}")

            # --- balance sheet (for off-balance-sheet checks) ---------------
            try:
                bs = await asyncio.to_thread(lambda: stock.balance_sheet)
                result["balance_sheet"] = _df_to_dict(bs)
            except Exception as exc:
                logger.warning("balance_sheet error for %s: %s", ticker, exc)
                result["errors"].append(f"balance_sheet: {exc}")

        except Exception as exc:
            logger.exception("Fatal error in AuditorFlagsAgent.fetch_data for %s", ticker)
            result["errors"].append(f"fatal: {exc}")

        return result

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        data_json = json.dumps(raw_data, indent=2, default=str)

        return f"""You are a forensic accounting analyst reviewing **{company_data.get('company_name', ticker)}** ({ticker}).

=== RAW DATA ===
{data_json}

=== INSTRUCTIONS ===
Examine the financial data for potential governance, accounting, or audit red flags.

Look for signals such as:
- Unusual changes in accruals or revenue recognition patterns
- Discrepancies between net income and operating cash flow (earnings quality)
- High or rising audit/board/compensation risk scores
- Abnormally low insider ownership or very high short interest
- Frequent stock splits or unusual dividend patterns
- Rapidly growing goodwill or intangible assets relative to total assets
- Deteriorating current ratio alongside rising debt

NOTE: Actual auditor opinions are not available in this data set. Base your
assessment only on the quantitative signals present.

Produce a JSON object with exactly these keys:

{{
  "summary": "<2-3 sentence overview of governance and audit posture>",
  "flags": [
    {{
      "type": "<e.g. earnings_quality, governance, leverage, insider_activity, accounting_anomaly>",
      "severity": "OK" | "Warning" | "Critical",
      "description": "<what the flag is>",
      "recommendation": "<what an analyst should investigate further>"
    }}
  ],
  "auditor_assessment": "<overall assessment noting that this is based on financial data signals, not an actual auditor report>"
}}

Include at least 3 flags. Even if everything looks clean, note the positive signals with severity "OK"."""

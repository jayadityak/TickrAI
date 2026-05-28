"""Agent 7 — Green / Red Flags (Synthesis).

This is the final synthesis agent.  It receives the outputs of agents
1-6 via ``company_data["prior_agent_results"]`` and combines them with
fresh key-ratio data to produce an overall investment scorecard.
"""

import asyncio
import json
import logging
import math

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
    return v


class GreenRedFlagsAgent(BaseAgent):
    name: str = "Green/Red Flags"
    index: int = 7

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        result: dict = {
            "key_ratios": {},
            "prior_agent_summaries": {},
            "errors": [],
        }

        # --- key financial ratios from yfinance ----------------------------
        try:
            stock = await asyncio.to_thread(yf.Ticker, ticker)
            info = await asyncio.to_thread(lambda: stock.info)

            ratio_keys = [
                "returnOnEquity",
                "returnOnAssets",
                "debtToEquity",
                "freeCashflow",
                "operatingCashflow",
                "revenueGrowth",
                "earningsGrowth",
                "earningsQuarterlyGrowth",
                "grossMargins",
                "operatingMargins",
                "profitMargins",
                "currentRatio",
                "quickRatio",
                "payoutRatio",
                "beta",
                "trailingPE",
                "forwardPE",
                "priceToBook",
                "pegRatio",
                "dividendYield",
                "marketCap",
                "enterpriseValue",
            ]
            for k in ratio_keys:
                result["key_ratios"][k] = _safe_value(info.get(k))

        except Exception as exc:
            logger.warning("ratio fetch error for %s: %s", ticker, exc)
            result["errors"].append(f"key_ratios: {exc}")

        # --- extract summaries from prior agent results --------------------
        prior = company_data.get("prior_agent_results", {})
        for agent_name, agent_result in prior.items():
            if isinstance(agent_result, dict):
                # Pull the most useful summary fields from each agent
                summary_fields = {}
                for key in ("summary", "overall_risk_level", "management_tone",
                            "sector_overview", "auditor_assessment", "business_description",
                            "analysis", "forward_outlook", "relative_valuation",
                            "key_themes", "risks", "flags", "guidance"):
                    if key in agent_result:
                        summary_fields[key] = agent_result[key]
                if summary_fields:
                    result["prior_agent_summaries"][agent_name] = summary_fields
                else:
                    # Fallback: include the whole result but truncate to avoid
                    # blowing up the prompt
                    truncated = json.dumps(agent_result, default=str)[:2000]
                    result["prior_agent_summaries"][agent_name] = truncated

        return result

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        ratios_json = json.dumps(raw_data.get("key_ratios", {}), indent=2, default=str)
        prior_json = json.dumps(raw_data.get("prior_agent_summaries", {}), indent=2, default=str)

        return f"""You are the final synthesis analyst for **{company_data.get('company_name', ticker)}** ({ticker}).

You have access to key financial ratios AND the findings from six prior
research agents.  Your job is to weigh all evidence and produce a
definitive investment scorecard.

=== KEY FINANCIAL RATIOS ===
{ratios_json}

=== PRIOR AGENT FINDINGS ===
{prior_json}

=== COMPANY CONTEXT ===
Sector: {company_data.get('sector', 'N/A')}
Industry: {company_data.get('industry', 'N/A')}

=== INSTRUCTIONS ===
Synthesise everything into a JSON object with exactly these keys:

{{
  "overall_score": <integer 1-10, where 10 = strongest investment case>,
  "overall_assessment": "<2-3 sentence executive summary of investment merit>",
  "green_flags": [
    {{
      "flag": "<concise positive signal>",
      "evidence": "<specific data/finding supporting this>",
      "significance": "High" | "Medium" | "Low"
    }}
  ],
  "red_flags": [
    {{
      "flag": "<concise negative signal>",
      "evidence": "<specific data/finding supporting this>",
      "significance": "High" | "Medium" | "Low"
    }}
  ],
  "investment_thesis_summary": "<paragraph-length investment thesis covering bull case, bear case, and key monitoring points>"
}}

Guidelines:
- Include at least 3 green flags and at least 2 red flags (even strong companies have risks).
- Reference specific numbers, ratios, or prior-agent findings as evidence.
- The overall_score should reflect a balanced view: 7-10 = attractive, 5-6 = neutral, 1-4 = concerning.
- The investment_thesis_summary should be actionable for a portfolio manager.
- Be honest about data limitations if prior agent results are sparse."""

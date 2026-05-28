"""Agent 1 — Company Overview.

Gathers fundamental company information via yfinance and synthesises
a structured overview using an LLM.
"""

import asyncio
import json
import logging
import math

import yfinance as yf

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CompanyOverviewAgent(BaseAgent):
    name: str = "Company Overview"
    index: int = 1

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        """Pull company-level info, major holders and top institutional holders."""

        result: dict = {
            "info": {},
            "major_holders": [],
            "institutional_holders": [],
            "errors": [],
        }

        try:
            stock = await asyncio.to_thread(yf.Ticker, ticker)

            # --- basic info ------------------------------------------------
            try:
                info = await asyncio.to_thread(lambda: stock.info)
                keys_of_interest = [
                    "longBusinessSummary",
                    "sector",
                    "industry",
                    "fullTimeEmployees",
                    "website",
                    "marketCap",
                    "city",
                    "state",
                    "country",
                    "longName",
                    "shortName",
                ]
                result["info"] = {
                    k: info.get(k) for k in keys_of_interest if info.get(k) is not None
                }
            except Exception as exc:
                logger.warning("Could not fetch info for %s: %s", ticker, exc)
                result["errors"].append(f"info: {exc}")

            # --- major holders ---------------------------------------------
            try:
                mh = await asyncio.to_thread(lambda: stock.major_holders)
                if mh is not None and not mh.empty:
                    result["major_holders"] = mh.to_dict(orient="records")
            except Exception as exc:
                logger.warning("Could not fetch major_holders for %s: %s", ticker, exc)
                result["errors"].append(f"major_holders: {exc}")

            # --- institutional holders (top 5) -----------------------------
            try:
                ih = await asyncio.to_thread(lambda: stock.institutional_holders)
                if ih is not None and not ih.empty:
                    ih_dicts = ih.head(5).to_dict(orient="records")
                    # Sanitise NaN and Timestamps
                    for row in ih_dicts:
                        for k, v in list(row.items()):
                            if isinstance(v, float) and math.isnan(v):
                                row[k] = None
                            elif hasattr(v, "isoformat"):
                                row[k] = v.isoformat()
                    result["institutional_holders"] = ih_dicts
            except Exception as exc:
                logger.warning("Could not fetch institutional_holders for %s: %s", ticker, exc)
                result["errors"].append(f"institutional_holders: {exc}")

        except Exception as exc:
            logger.exception("Fatal error in CompanyOverviewAgent.fetch_data for %s", ticker)
            result["errors"].append(f"fatal: {exc}")

        return result

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        data_json = json.dumps(raw_data, indent=2, default=str)

        return f"""Analyse the following data for **{company_data.get('company_name', ticker)}** ({ticker}) and produce a comprehensive company overview.

=== RAW DATA ===
{data_json}

=== ADDITIONAL CONTEXT ===
Exchange: {company_data.get('exchange', 'N/A')}
Sector: {company_data.get('sector', 'N/A')}
Industry: {company_data.get('industry', 'N/A')}

=== INSTRUCTIONS ===
Return a JSON object with exactly these keys:

{{
  "business_description": "<2-4 sentence summary of what the company does>",
  "key_products": ["<product/service 1>", "..."],
  "revenue_segments": [
    {{"name": "<segment>", "description": "<brief description>"}}
  ],
  "competitive_position": "<paragraph on moat, market share, competitive dynamics>",
  "recent_developments": ["<notable recent event 1>", "..."],
  "management_highlights": "<key leadership observations>",
  "employee_count": <integer or null>,
  "headquarters": "<city, state/country>"
}}

Be factual.  If data is missing, use null or empty lists rather than guessing."""

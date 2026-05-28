"""Agent 6 — Sector & Peer Comparison.

Fetches the target company's key metrics and compares them against a
set of peer companies within the same sector/industry.
"""

import asyncio
import json
import logging
import math

import yfinance as yf

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ======================================================================
# Peer mapping — covers major large-cap names.  For tickers not in
# this map the agent falls back to sector-based defaults.
# ======================================================================

PEER_MAP: dict[str, list[str]] = {
    # Technology
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "SAMSUNG"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "CRM", "ORCL"],
    "GOOGL": ["META", "MSFT", "AMZN", "AAPL", "SNAP"],
    "GOOG": ["META", "MSFT", "AMZN", "AAPL", "SNAP"],
    "META": ["GOOGL", "SNAP", "PINS", "MSFT", "AMZN"],
    "AMZN": ["MSFT", "GOOGL", "AAPL", "WMT", "SHOP"],
    "NVDA": ["AMD", "INTC", "AVGO", "QCOM", "TSM"],
    "AMD": ["NVDA", "INTC", "QCOM", "AVGO", "MRVL"],
    "INTC": ["AMD", "NVDA", "TXN", "QCOM", "AVGO"],
    "CRM": ["MSFT", "ORCL", "NOW", "WDAY", "SAP"],
    "TSLA": ["F", "GM", "RIVN", "NIO", "TM"],
    "NFLX": ["DIS", "WBD", "CMCSA", "PARA", "ROKU"],
    # Financials
    "JPM": ["BAC", "WFC", "GS", "MS", "C"],
    "BAC": ["JPM", "WFC", "C", "USB", "PNC"],
    "GS": ["MS", "JPM", "BAC", "SCHW", "BLK"],
    "V": ["MA", "PYPL", "SQ", "AXP", "FIS"],
    "MA": ["V", "PYPL", "SQ", "AXP", "GPN"],
    # Healthcare
    "JNJ": ["PFE", "MRK", "ABBV", "LLY", "UNH"],
    "UNH": ["CI", "ELV", "HUM", "CVS", "CNC"],
    "PFE": ["MRK", "JNJ", "ABBV", "LLY", "BMY"],
    "LLY": ["NVO", "MRK", "ABBV", "PFE", "JNJ"],
    # Consumer
    "WMT": ["TGT", "COST", "AMZN", "KR", "DG"],
    "KO": ["PEP", "MNST", "KDP", "STZ", "BF-B"],
    "PEP": ["KO", "MNST", "KDP", "GIS", "K"],
    "MCD": ["SBUX", "YUM", "CMG", "DPZ", "QSR"],
    # Energy
    "XOM": ["CVX", "COP", "SLB", "EOG", "OXY"],
    "CVX": ["XOM", "COP", "SLB", "EOG", "PXD"],
    # Industrials
    "BA": ["LMT", "RTX", "GD", "NOC", "GE"],
    "CAT": ["DE", "CMI", "PCAR", "URI", "EMR"],
}

# Sector-based fallback peers (used when ticker is not in PEER_MAP)
SECTOR_DEFAULTS: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
    "Financial Services": ["JPM", "BAC", "GS", "V", "MA"],
    "Healthcare": ["JNJ", "UNH", "PFE", "LLY", "MRK"],
    "Consumer Cyclical": ["AMZN", "TSLA", "MCD", "NKE", "SBUX"],
    "Consumer Defensive": ["WMT", "PG", "KO", "PEP", "COST"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Industrials": ["BA", "CAT", "HON", "UPS", "GE"],
    "Basic Materials": ["LIN", "APD", "ECL", "SHW", "NEM"],
    "Real Estate": ["AMT", "PLD", "CCI", "SPG", "EQIX"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
}


def _safe_value(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


async def _fetch_company_metrics(ticker: str) -> dict:
    """Fetch a standard set of comparison metrics for a single ticker."""
    try:
        stock = await asyncio.to_thread(yf.Ticker, ticker)
        info = await asyncio.to_thread(lambda: stock.info)
        return {
            "symbol": ticker,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "market_cap": _safe_value(info.get("marketCap")),
            "pe_ratio": _safe_value(info.get("trailingPE")),
            "forward_pe": _safe_value(info.get("forwardPE")),
            "price_to_book": _safe_value(info.get("priceToBook")),
            "revenue_growth": _safe_value(info.get("revenueGrowth")),
            "earnings_growth": _safe_value(info.get("earningsGrowth")),
            "gross_margins": _safe_value(info.get("grossMargins")),
            "operating_margins": _safe_value(info.get("operatingMargins")),
            "net_margins": _safe_value(info.get("profitMargins")),
            "roe": _safe_value(info.get("returnOnEquity")),
            "dividend_yield": _safe_value(info.get("dividendYield")),
            "beta": _safe_value(info.get("beta")),
            "current_price": _safe_value(info.get("currentPrice")),
        }
    except Exception as exc:
        logger.warning("Failed to fetch metrics for peer %s: %s", ticker, exc)
        return {"symbol": ticker, "error": str(exc)}


class SectorPeerAgent(BaseAgent):
    name: str = "Sector & Peers"
    index: int = 6

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        result: dict = {
            "target": {},
            "peers": [],
            "peer_symbols": [],
            "errors": [],
        }

        try:
            # --- target company metrics ------------------------------------
            result["target"] = await _fetch_company_metrics(ticker)

            # --- resolve peer list -----------------------------------------
            upper = ticker.upper()
            if upper in PEER_MAP:
                peer_symbols = PEER_MAP[upper][:5]
            else:
                sector = company_data.get("sector", "")
                peer_symbols = SECTOR_DEFAULTS.get(sector, SECTOR_DEFAULTS.get("Technology", []))
                # Remove self from sector defaults if present
                peer_symbols = [s for s in peer_symbols if s.upper() != upper][:5]

            result["peer_symbols"] = peer_symbols

            # --- fetch peers concurrently ----------------------------------
            tasks = [_fetch_company_metrics(sym) for sym in peer_symbols]
            peer_results = await asyncio.gather(*tasks, return_exceptions=True)

            for sym, pr in zip(peer_symbols, peer_results):
                if isinstance(pr, Exception):
                    result["peers"].append({"symbol": sym, "error": str(pr)})
                    result["errors"].append(f"peer {sym}: {pr}")
                else:
                    result["peers"].append(pr)

        except Exception as exc:
            logger.exception("Fatal error in SectorPeerAgent.fetch_data for %s", ticker)
            result["errors"].append(f"fatal: {exc}")

        return result

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        data_json = json.dumps(raw_data, indent=2, default=str)

        return f"""Compare **{company_data.get('company_name', ticker)}** ({ticker}) against its sector peers.

=== RAW DATA ===
{data_json}

=== COMPANY CONTEXT ===
Sector: {company_data.get('sector', 'N/A')}
Industry: {company_data.get('industry', 'N/A')}

=== INSTRUCTIONS ===
Analyse the target company relative to its peers.  Produce a JSON
object with exactly these keys:

{{
  "sector_overview": "<paragraph on sector dynamics, growth drivers, and current state>",
  "tailwinds": ["<sector/industry tailwind 1>", "..."],
  "headwinds": ["<sector/industry headwind 1>", "..."],
  "peer_comparison": [
    {{
      "symbol": "<ticker>",
      "company_name": "<name>",
      "market_cap": <number or null>,
      "pe_ratio": <number or null>,
      "revenue_growth": <decimal or null>,
      "margin": <operating margin decimal or null>,
      "assessment": "<1-2 sentence relative assessment>"
    }}
  ],
  "relative_valuation": "<paragraph comparing the target's valuation multiples, growth, and margins vs peers.  State whether it appears overvalued, fairly valued, or undervalued relative to the peer set.>"
}}

Include the target company as the first entry in peer_comparison.
Be specific with numbers. Use null when data is unavailable."""

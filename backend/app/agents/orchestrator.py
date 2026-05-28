import asyncio
import traceback
from collections.abc import AsyncGenerator

from .company_overview import CompanyOverviewAgent
from .financial_analysis import FinancialAnalysisAgent
from .risk_analysis import RiskAnalysisAgent
from .auditor_flags import AuditorFlagsAgent
from .earnings_call import EarningsCallAgent
from .sector_peer import SectorPeerAgent
from .green_red_flags import GreenRedFlagsAgent

PARALLEL_AGENTS = [
    CompanyOverviewAgent,
    FinancialAnalysisAgent,
    RiskAnalysisAgent,
    AuditorFlagsAgent,
    EarningsCallAgent,
    SectorPeerAgent,
]

SYNTHESIS_AGENT = GreenRedFlagsAgent


async def _run_single_agent(agent_cls, ticker: str, company_data: dict) -> dict:
    """Run a single agent and return an AgentResult dict."""
    agent = agent_cls()
    try:
        data = await agent.run(ticker, company_data)
        return {
            "agent_name": agent.name,
            "agent_index": agent.index,
            "status": "completed",
            "data": data,
            "error": None,
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "agent_name": agent.name,
            "agent_index": agent.index,
            "status": "error",
            "data": None,
            "error": str(e),
        }


async def run_all_agents(ticker: str, company_data: dict) -> AsyncGenerator[dict, None]:
    """Run all agents sequentially, yielding results as they complete.

    Runs agents 1-6 one at a time to stay within API rate limits,
    then agent 7 (Green/Red Flags) with all prior results.
    """
    collected_results: list[dict] = []

    for cls in PARALLEL_AGENTS:
        result = await _run_single_agent(cls, ticker, company_data)
        collected_results.append(result)
        yield result

    # Build prior_agent_results dict for the synthesis agent
    prior_agent_results: dict = {}
    for r in collected_results:
        if r.get("status") == "completed" and r.get("data"):
            prior_agent_results[r["agent_name"]] = r["data"]

    # Run synthesis agent with all prior results
    synthesis_agent = SYNTHESIS_AGENT()
    try:
        enriched_data = {
            **company_data,
            "prior_agent_results": prior_agent_results,
        }
        data = await synthesis_agent.run(ticker, enriched_data)
        synthesis_result = {
            "agent_name": synthesis_agent.name,
            "agent_index": synthesis_agent.index,
            "status": "completed",
            "data": data,
            "error": None,
        }
    except Exception as e:
        traceback.print_exc()
        synthesis_result = {
            "agent_name": synthesis_agent.name,
            "agent_index": synthesis_agent.index,
            "status": "error",
            "data": None,
            "error": str(e),
        }

    yield synthesis_result


async def run_all_agents_sync(ticker: str, company_data: dict) -> list[dict]:
    """Run all agents and collect results into a list."""
    results: list[dict] = []
    async for result in run_all_agents(ticker, company_data):
        results.append(result)
    return results

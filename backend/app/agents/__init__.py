"""AI research agents for equity analysis."""

from .base_agent import BaseAgent
from .company_overview import CompanyOverviewAgent
from .financial_analysis import FinancialAnalysisAgent
from .risk_analysis import RiskAnalysisAgent
from .auditor_flags import AuditorFlagsAgent
from .earnings_call import EarningsCallAgent
from .sector_peer import SectorPeerAgent
from .green_red_flags import GreenRedFlagsAgent
from .orchestrator import run_all_agents, run_all_agents_sync

ALL_AGENTS: list[type[BaseAgent]] = [
    CompanyOverviewAgent,
    FinancialAnalysisAgent,
    RiskAnalysisAgent,
    AuditorFlagsAgent,
    EarningsCallAgent,
    SectorPeerAgent,
    GreenRedFlagsAgent,
]

__all__ = [
    "BaseAgent",
    "CompanyOverviewAgent",
    "FinancialAnalysisAgent",
    "RiskAnalysisAgent",
    "AuditorFlagsAgent",
    "EarningsCallAgent",
    "SectorPeerAgent",
    "GreenRedFlagsAgent",
    "ALL_AGENTS",
    "run_all_agents",
    "run_all_agents_sync",
]

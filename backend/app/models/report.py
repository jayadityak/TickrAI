from typing import Literal

from pydantic import BaseModel


class AgentResult(BaseModel):
    agent_name: str
    agent_index: int
    status: Literal["pending", "running", "completed", "error"]
    data: dict | None = None
    error: str | None = None


class ReportRequest(BaseModel):
    ticker: str


class ReportResponse(BaseModel):
    id: str
    ticker: str
    company_name: str
    exchange: str
    status: str
    created_at: str
    agent_results: list[AgentResult]
    metadata: dict

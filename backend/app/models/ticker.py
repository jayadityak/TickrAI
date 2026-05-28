from pydantic import BaseModel


class Ticker(BaseModel):
    symbol: str
    company_name: str
    exchange: str
    sector: str | None = None
    industry: str | None = None
    cik: str | None = None


class SearchResult(BaseModel):
    symbol: str
    company_name: str
    exchange: str

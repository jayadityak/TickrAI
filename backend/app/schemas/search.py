from pydantic import BaseModel


class SearchResultItem(BaseModel):
    symbol: str
    company_name: str
    exchange: str


class SearchResponse(BaseModel):
    results: list[SearchResultItem]

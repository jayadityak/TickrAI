export interface Ticker {
  symbol: string;
  companyName: string;
  exchange: string;
  sector: string;
  industry: string;
  marketCap: number;
}

export interface SearchResult {
  symbol: string;
  companyName: string;
  exchange: string;
}

export interface AgentResult {
  agentName: string;
  agentIndex: number;
  status: 'pending' | 'running' | 'completed' | 'error';
  data: any;
  error?: string;
}

export interface Report {
  id: string;
  ticker: string;
  companyName: string;
  exchange: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  createdAt: string;
  agentResults: AgentResult[];
  metadata: {
    price?: number;
    marketCap?: number;
    pe?: number;
    roce?: number;
    roe?: number;
    debtEquity?: number;
    patMargin?: number;
    ebitdaMargin?: number;
  };
}

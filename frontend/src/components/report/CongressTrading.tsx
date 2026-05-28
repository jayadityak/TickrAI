import { useState, useEffect } from 'react';
import { Landmark, TrendingUp, TrendingDown } from 'lucide-react';
import axios from 'axios';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface CongressTrade {
  representative: string;
  party: string;
  house: string;
  ticker: string;
  transaction: string;
  amount_range: string;
  transaction_date: string;
  report_date: string;
  excess_return: number | null;
}

function partyColor(party: string): string {
  if (party === 'D') return 'text-blue-600';
  if (party === 'R') return 'text-red-600';
  return 'text-muted';
}

function partyBg(party: string): string {
  if (party === 'D') return 'bg-blue-50';
  if (party === 'R') return 'bg-red-50';
  return 'bg-surface';
}

function isBuy(transaction: string): boolean {
  return transaction.toLowerCase().includes('purchase');
}

export default function CongressTrading({ ticker }: { ticker: string }) {
  const [trades, setTrades] = useState<CongressTrade[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrades = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`/api/congress?ticker=${ticker}&limit=10`);
        setTrades(res.data.trades);
        setTotal(res.data.total);
      } catch {
        setTrades([]);
      } finally {
        setLoading(false);
      }
    };
    fetchTrades();
  }, [ticker]);

  if (loading) {
    return (
      <Card>
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <Landmark size={20} className="text-accent" />
          Congress Trading
        </h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-surface2 rounded w-full" />
          <div className="h-4 bg-surface2 rounded w-3/4" />
          <div className="h-20 bg-surface2 rounded" />
        </div>
      </Card>
    );
  }

  if (trades.length === 0) {
    return (
      <Card>
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <Landmark size={20} className="text-accent" />
          Congress Trading
        </h2>
        <p className="text-sm text-muted">No recent Congressional trades found for {ticker}.</p>
      </Card>
    );
  }

  const buyCount = trades.filter((t) => isBuy(t.transaction)).length;
  const sellCount = trades.length - buyCount;

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-lg flex items-center gap-2">
          <Landmark size={20} className="text-accent" />
          Congress Trading
        </h2>
        <span className="text-xs text-muted">{total} total trades</span>
      </div>

      {/* Summary */}
      <div className="flex gap-3 mb-4">
        <div className="bg-green/10 rounded-[8px] px-3 py-2 text-center flex-1">
          <p className="text-xs text-muted">Buys</p>
          <p className="text-lg font-bold text-green">{buyCount}</p>
        </div>
        <div className="bg-red/10 rounded-[8px] px-3 py-2 text-center flex-1">
          <p className="text-xs text-muted">Sells</p>
          <p className="text-lg font-bold text-red">{sellCount}</p>
        </div>
      </div>

      {/* Trades list */}
      <div className="space-y-2">
        {trades.map((trade, i) => (
          <div
            key={i}
            className={`rounded-[8px] p-3 border border-border/50 ${partyBg(trade.party)}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm">{trade.representative}</span>
                  <Badge variant={trade.party === 'D' ? 'accent' : 'red'}>
                    {trade.party === 'D' ? 'Democrat' : trade.party === 'R' ? 'Republican' : trade.party}
                  </Badge>
                  <span className="text-xs text-muted">{trade.house}</span>
                </div>
                <p className="text-xs text-muted mt-1">{trade.transaction_date}</p>
              </div>
              <div className="text-right shrink-0">
                <span
                  className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                    isBuy(trade.transaction)
                      ? 'bg-green/15 text-green'
                      : 'bg-red/15 text-red'
                  }`}
                >
                  {isBuy(trade.transaction) ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  {isBuy(trade.transaction) ? 'Buy' : 'Sell'}
                </span>
                <p className="text-xs text-muted mt-1">{trade.amount_range}</p>
              </div>
            </div>
            {trade.excess_return !== null && (
              <p className={`text-xs mt-1 ${trade.excess_return >= 0 ? 'text-green' : 'text-red'}`}>
                Excess return vs S&P: {trade.excess_return >= 0 ? '+' : ''}{trade.excess_return}%
              </p>
            )}
          </div>
        ))}
      </div>

      <p className="text-xs text-muted mt-4">
        Source: Congressional financial disclosures via Quiver Quantitative.
      </p>
    </Card>
  );
}

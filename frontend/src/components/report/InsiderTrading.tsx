import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, ArrowUpDown, Users } from 'lucide-react';
import axios from 'axios';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface Transaction {
  date: string;
  insider: string;
  position: string;
  transaction_type: string;
  shares: number;
  value: number | null;
  text: string;
}

interface InsiderSummary {
  total_transactions: number;
  purchases: number;
  sales: number;
  total_buy_value: number;
  total_sell_value: number;
  net_value: number;
  signal: string;
}

interface InsiderData {
  transactions: Transaction[];
  summary: InsiderSummary;
}

function formatValue(value: number | null): string {
  if (value === null || value === 0) return '—';
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function formatShares(shares: number): string {
  if (shares >= 1e6) return `${(shares / 1e6).toFixed(1)}M`;
  if (shares >= 1e3) return `${(shares / 1e3).toFixed(1)}K`;
  return shares.toLocaleString();
}

export default function InsiderTrading({ ticker, onNoData }: { ticker: string; onNoData?: () => void }) {
  const [data, setData] = useState<InsiderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchInsider = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`/api/insider/${ticker}`);
        setData(res.data);
        if (!res.data?.transactions?.length) onNoData?.();
      } catch (err) {
        setError('Failed to load insider data');
        onNoData?.();
      } finally {
        setLoading(false);
      }
    };
    fetchInsider();
  }, [ticker]);

  if (loading) {
    return (
      <Card>
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <Users size={20} className="text-accent" />
          Insider Trading
        </h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-surface2 rounded w-full" />
          <div className="h-4 bg-surface2 rounded w-3/4" />
          <div className="h-20 bg-surface2 rounded w-full" />
        </div>
      </Card>
    );
  }

  if (error || !data || data.transactions.length === 0) {
    return null;
  }

  const { transactions, summary } = data;

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
        <Users size={20} className="text-accent" />
        Insider Trading
      </h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-surface rounded-[8px] p-3 text-center">
          <p className="text-xs text-muted mb-1">Transactions</p>
          <p className="text-lg font-bold">{summary.total_transactions}</p>
        </div>
        <div className="bg-green/10 rounded-[8px] p-3 text-center">
          <p className="text-xs text-muted mb-1">Purchases</p>
          <p className="text-lg font-bold text-green">{summary.purchases}</p>
        </div>
        <div className="bg-red/10 rounded-[8px] p-3 text-center">
          <p className="text-xs text-muted mb-1">Sales</p>
          <p className="text-lg font-bold text-red">{summary.sales}</p>
        </div>
        <div className={`rounded-[8px] p-3 text-center ${summary.net_value >= 0 ? 'bg-green/10' : 'bg-red/10'}`}>
          <p className="text-xs text-muted mb-1">Net Activity</p>
          <div className="flex items-center justify-center gap-1">
            {summary.net_value >= 0 ? (
              <TrendingUp size={16} className="text-green" />
            ) : (
              <TrendingDown size={16} className="text-red" />
            )}
            <span className={`text-lg font-bold ${summary.net_value >= 0 ? 'text-green' : 'text-red'}`}>
              {formatValue(Math.abs(summary.net_value))}
            </span>
          </div>
          <Badge variant={summary.signal === 'Bullish' ? 'green' : summary.signal === 'Bearish' ? 'red' : 'default'}>
            {summary.signal}
          </Badge>
        </div>
      </div>

      {/* Transaction table */}
      <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
        <table className="w-full text-sm min-w-[500px]">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="py-2 pr-3 text-muted font-medium">Date</th>
              <th className="py-2 pr-3 text-muted font-medium">Insider</th>
              <th className="py-2 pr-3 text-muted font-medium hidden md:table-cell">Position</th>
              <th className="py-2 pr-3 text-muted font-medium">Type</th>
              <th className="py-2 pr-3 text-muted font-medium text-right">Shares</th>
              <th className="py-2 text-muted font-medium text-right">Value</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx, i) => (
              <tr
                key={i}
                className={`border-b border-border/50 ${
                  tx.transaction_type === 'Purchase' ? 'bg-green/5' : tx.transaction_type === 'Sale' ? 'bg-red/5' : ''
                }`}
              >
                <td className="py-2 pr-3 text-muted whitespace-nowrap">{tx.date}</td>
                <td className="py-2 pr-3 font-medium">{tx.insider}</td>
                <td className="py-2 pr-3 text-muted text-xs hidden md:table-cell">{tx.position}</td>
                <td className="py-2 pr-3">
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                      tx.transaction_type === 'Purchase'
                        ? 'bg-green/15 text-green'
                        : tx.transaction_type === 'Sale'
                        ? 'bg-red/15 text-red'
                        : 'bg-surface2 text-muted'
                    }`}
                  >
                    {tx.transaction_type === 'Purchase' && <TrendingUp size={12} />}
                    {tx.transaction_type === 'Sale' && <TrendingDown size={12} />}
                    {tx.transaction_type === 'Gift' && <ArrowUpDown size={12} />}
                    {tx.transaction_type}
                  </span>
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">{formatShares(tx.shares)}</td>
                <td className="py-2 text-right tabular-nums">{formatValue(tx.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted mt-4">
        Source: SEC Form 4 filings via Yahoo Finance. Showing most recent transactions.
      </p>
    </Card>
  );
}

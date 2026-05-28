import { useState, useCallback } from 'react';
import { X, Plus, ArrowRight, Trophy, BarChart3 } from 'lucide-react';
import axios from 'axios';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import AuthGate from '../components/auth/AuthGate';
import TickerSearch from '../components/search/TickerSearch';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface CompanyMetrics {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  price: number | null;
  metrics: {
    market_cap: string;
    market_cap_raw: number;
    pe_ratio: number | null;
    revenue: string;
    revenue_raw: number;
    net_income: string;
    net_income_raw: number;
    eps: number | null;
    revenue_growth: number | null;
    net_margin: number | null;
    current_ratio: number | null;
    debt_to_equity: number | null;
    beta: number | null;
    dividend_yield: number | null;
  };
}

const COLORS = ['#0f766e', '#3b82f6', '#f59e0b', '#ef4444'];

const METRIC_LABELS: Record<string, string> = {
  pe_ratio: 'P/E Ratio',
  revenue_growth: 'Revenue Growth %',
  net_margin: 'Net Margin %',
  current_ratio: 'Current Ratio',
  debt_to_equity: 'Debt/Equity',
  eps: 'EPS',
  beta: 'Beta',
  dividend_yield: 'Dividend Yield %',
};

function CompareContent() {
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [companies, setCompanies] = useState<CompanyMetrics[]>([]);
  const [winners, setWinners] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSearch, setShowSearch] = useState(true);

  const addTicker = useCallback(
    (ticker: string) => {
      const upper = ticker.toUpperCase();
      if (selectedTickers.includes(upper) || selectedTickers.length >= 4) return;
      setSelectedTickers((prev) => [...prev, upper]);
    },
    [selectedTickers],
  );

  const removeTicker = (ticker: string) => {
    setSelectedTickers((prev) => prev.filter((t) => t !== ticker));
  };

  const runComparison = async () => {
    if (selectedTickers.length < 2) return;
    setLoading(true);
    setError(null);

    const token = localStorage.getItem('tickrai_token');
    try {
      const res = await axios.get('/api/compare', {
        params: { tickers: selectedTickers.join(',') },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setCompanies(res.data.companies);
      setWinners(res.data.winners);
      setShowSearch(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to compare. Try again.');
    } finally {
      setLoading(false);
    }
  };

  // Radar chart data
  const radarMetrics = ['revenue_growth', 'net_margin', 'current_ratio', 'eps', 'pe_ratio'];
  const radarData = radarMetrics.map((key) => {
    const entry: Record<string, any> = { metric: METRIC_LABELS[key] || key };
    for (const c of companies) {
      let val = c.metrics[key as keyof typeof c.metrics] as number | null;
      // Normalize: invert PE and D/E (lower is better)
      if (key === 'pe_ratio' && val && val > 0) val = Math.min(100 / val, 10);
      if (key === 'debt_to_equity' && val) val = Math.max(0, 5 - val);
      entry[c.symbol] = val ?? 0;
    }
    return entry;
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold mb-2">Compare Companies</h1>
        <p className="text-muted">Side-by-side analysis of up to 4 companies</p>
      </div>

      {/* Ticker Selection */}
      {showSearch && (
        <Card className="mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            {selectedTickers.map((t, i) => (
              <div
                key={t}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border-2"
                style={{ borderColor: COLORS[i] }}
              >
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: COLORS[i] }}
                />
                <span className="font-bold text-sm">{t}</span>
                <button
                  onClick={() => removeTicker(t)}
                  className="hover:text-red transition-colors cursor-pointer"
                >
                  <X size={14} />
                </button>
              </div>
            ))}

            {selectedTickers.length < 4 && (
              <div className="flex items-center gap-1 text-muted text-sm">
                <Plus size={14} />
                {selectedTickers.length === 0
                  ? 'Add companies to compare'
                  : `Add ${4 - selectedTickers.length} more`}
              </div>
            )}
          </div>

          {selectedTickers.length < 4 && (
            <div className="max-w-md">
              <TickerSearch
                onSelect={(ticker: string) => addTicker(ticker)}
                placeholder="Search for a company to add..."
              />
            </div>
          )}

          {selectedTickers.length >= 2 && (
            <div className="mt-4">
              <Button onClick={runComparison} disabled={loading}>
                <span className="flex items-center gap-2">
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Comparing...
                    </>
                  ) : (
                    <>
                      Compare {selectedTickers.length} Companies
                      <ArrowRight size={16} />
                    </>
                  )}
                </span>
              </Button>
            </div>
          )}
        </Card>
      )}

      {error && (
        <Card className="border-red mb-6">
          <p className="text-red text-sm">{error}</p>
        </Card>
      )}

      {/* Results */}
      {companies.length >= 2 && (
        <>
          {/* Reset button */}
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <BarChart3 size={22} className="text-accent" />
              Comparison Results
            </h2>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setCompanies([]);
                setWinners({});
                setShowSearch(true);
              }}
            >
              New Comparison
            </Button>
          </div>

          {/* Company header cards */}
          <div className={`grid grid-cols-2 sm:grid-cols-${companies.length} gap-3 sm:gap-4 mb-6`}>
            {companies.map((c, i) => (
              <Card key={c.symbol} className="text-center">
                <div
                  className="w-4 h-4 rounded-full mx-auto mb-2"
                  style={{ backgroundColor: COLORS[i] }}
                />
                <h3 className="font-bold text-lg">{c.symbol}</h3>
                <p className="text-sm text-muted truncate">{c.company_name}</p>
                <p className="text-xs text-muted mt-1">{c.sector}</p>
                {c.price && (
                  <p className="text-lg font-semibold mt-2">${c.price.toFixed(2)}</p>
                )}
              </Card>
            ))}
          </div>

          {/* Metrics table */}
          <Card className="mb-6">
            <h3 className="font-semibold mb-4">Key Metrics</h3>
            <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
              <table className="w-full text-sm min-w-[400px]">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 text-left text-muted font-medium">Metric</th>
                    {companies.map((c, i) => (
                      <th key={c.symbol} className="py-2 px-3 text-right font-medium">
                        <span style={{ color: COLORS[i] }}>{c.symbol}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(METRIC_LABELS).map(([key, label]) => (
                    <tr key={key} className="border-b border-border/50">
                      <td className="py-2.5 pr-4 text-muted">{label}</td>
                      {companies.map((c) => {
                        const val = c.metrics[key as keyof typeof c.metrics];
                        const isWinner = winners[key] === c.symbol;
                        const formatted =
                          val === null || val === undefined
                            ? 'N/A'
                            : key.includes('growth') || key.includes('margin') || key.includes('yield')
                            ? `${val}%`
                            : key === 'pe_ratio' || key === 'current_ratio' || key === 'debt_to_equity' || key === 'beta'
                            ? `${val}x`
                            : key === 'eps'
                            ? `$${val}`
                            : String(val);

                        return (
                          <td key={c.symbol} className="py-2.5 px-3 text-right tabular-nums">
                            <span className={`${isWinner ? 'font-bold text-accent' : ''}`}>
                              {formatted}
                            </span>
                            {isWinner && (
                              <Trophy size={12} className="inline ml-1 text-accent" />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  {/* Market cap and revenue rows */}
                  <tr className="border-b border-border/50">
                    <td className="py-2.5 pr-4 text-muted">Market Cap</td>
                    {companies.map((c) => (
                      <td key={c.symbol} className="py-2.5 px-3 text-right font-medium">
                        {c.metrics.market_cap || 'N/A'}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b border-border/50">
                    <td className="py-2.5 pr-4 text-muted">Revenue</td>
                    {companies.map((c) => (
                      <td key={c.symbol} className="py-2.5 px-3 text-right font-medium">
                        {c.metrics.revenue || 'N/A'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4 text-muted">Net Income</td>
                    {companies.map((c) => (
                      <td key={c.symbol} className="py-2.5 px-3 text-right font-medium">
                        {c.metrics.net_income || 'N/A'}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          {/* Radar chart */}
          <Card>
            <h3 className="font-semibold mb-4">Visual Comparison</h3>
            <ResponsiveContainer width="100%" height={300} className="sm:!h-[400px]">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#e7e5e4" />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12, fill: '#78716c' }} />
                <PolarRadiusAxis tick={false} axisLine={false} />
                {companies.map((c, i) => (
                  <Radar
                    key={c.symbol}
                    name={c.symbol}
                    dataKey={c.symbol}
                    stroke={COLORS[i]}
                    fill={COLORS[i]}
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                ))}
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <AuthGate message="Sign in to compare companies side by side">
      <CompareContent />
    </AuthGate>
  );
}

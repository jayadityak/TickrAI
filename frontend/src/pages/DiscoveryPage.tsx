import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ChevronRight, Compass, FileText, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react';
import axios from 'axios';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';

interface ScreenResult {
  ticker: string;
  name: string;
  sector: string;
  cap_tier: string;
  price: number | null;
  change_pct: number | null;
  positive: boolean;
  market_cap: string;
  n_analysts: number | null;
}

const CAP_TIER_LABELS: Record<string, string> = {
  micro: 'Micro-cap',
  small: 'Small-cap',
  mid:   'Mid-cap',
};

const MAX_ANALYST_OPTIONS = [
  { label: 'No coverage (0)', value: 0 },
  { label: '≤ 2 analysts',   value: 2 },
  { label: '≤ 5 analysts',   value: 5 },
  { label: '≤ 10 analysts',  value: 10 },
];

function AnalystBadge({ n }: { n: number | null }) {
  if (n === null) return <span className="text-xs text-muted">Unknown</span>;
  if (n === 0)
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red/10 text-red border border-red/20">0 analysts</span>;
  if (n <= 2)
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber/10 text-amber border border-amber/20">{n} analyst{n > 1 ? 's' : ''}</span>;
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-surface2 text-muted border border-border">{n} analysts</span>;
}

function StockCard({ result }: { result: ScreenResult }) {
  return (
    <Card className="hover:border-accent/40 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <Link
              to={`/report/${result.ticker}`}
              className="font-bold text-lg text-accent hover:underline"
            >
              {result.ticker}
            </Link>
            <AnalystBadge n={result.n_analysts} />
          </div>
          <p className="text-sm text-muted truncate">{result.name}</p>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <Badge variant="default">{result.sector}</Badge>
            <span className="text-xs text-muted">{CAP_TIER_LABELS[result.cap_tier] || result.cap_tier}</span>
            <span className="text-xs text-muted">Market cap: {result.market_cap}</span>
          </div>
        </div>

        <div className="text-right shrink-0">
          {result.price ? (
            <>
              <p className="font-semibold text-lg">${result.price.toFixed(2)}</p>
              {result.change_pct !== null && (
                <p className={`text-xs flex items-center justify-end gap-0.5 ${result.positive ? 'text-green' : 'text-red'}`}>
                  {result.positive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  {result.positive ? '+' : ''}{result.change_pct.toFixed(2)}%
                </p>
              )}
            </>
          ) : (
            <p className="text-muted text-sm">—</p>
          )}
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
        {result.n_analysts === 0 ? (
          <p className="text-xs text-amber flex items-center gap-1">
            <AlertTriangle size={12} />
            No analyst coverage — TickrAI may be the only research available
          </p>
        ) : result.n_analysts !== null && result.n_analysts <= 2 ? (
          <p className="text-xs text-muted">Minimal Wall Street coverage</p>
        ) : (
          <p className="text-xs text-muted">Low analyst coverage</p>
        )}
        <Link to={`/report/${result.ticker}`}>
          <Button variant="secondary" size="sm">
            <span className="flex items-center gap-1">
              <FileText size={13} />
              View Report
              <ChevronRight size={13} />
            </span>
          </Button>
        </Link>
      </div>
    </Card>
  );
}

function SkeletonCard() {
  return (
    <Card>
      <div className="animate-pulse">
        <div className="flex justify-between mb-2">
          <div className="h-6 w-20 bg-surface2 rounded" />
          <div className="h-6 w-16 bg-surface2 rounded" />
        </div>
        <div className="h-4 w-48 bg-surface2 rounded mb-3" />
        <div className="flex gap-2">
          <div className="h-5 w-24 bg-surface2 rounded-full" />
          <div className="h-5 w-16 bg-surface2 rounded" />
        </div>
      </div>
    </Card>
  );
}

export default function DiscoveryPage() {
  const [results, setResults] = useState<ScreenResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [sectors, setSectors] = useState<string[]>([]);
  const [selectedSector, setSelectedSector] = useState('');
  const [maxAnalysts, setMaxAnalysts] = useState(10);
  const [capTier, setCapTier] = useState('');
  const [offset, setOffset] = useState(0);

  const LIMIT = 20;

  const fetchSectors = useCallback(async () => {
    try {
      const res = await axios.get('/api/screen/sectors');
      setSectors(res.data.sectors || []);
    } catch {
      // silent
    }
  }, []);

  const fetchResults = useCallback(async (newOffset = 0, append = false) => {
    if (append) setLoadingMore(true);
    else setLoading(true);

    try {
      // Only send sector + cap_tier to backend (static filters, instant).
      // Live yfinance data is fetched in parallel for the page slice only.
      const params: Record<string, string | number> = {
        limit: LIMIT,
        offset: newOffset,
      };
      if (selectedSector) params.sector = selectedSector;
      if (capTier) params.cap_tier = capTier;

      const res = await axios.get('/api/screen', { params });
      if (append) {
        setResults((prev) => [...prev, ...res.data.results]);
      } else {
        setResults(res.data.results || []);
        setOffset(0);
      }
      setTotal(res.data.total);
    } catch {
      // silent
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [selectedSector, capTier]);

  // Initial load
  useEffect(() => {
    fetchSectors();
  }, [fetchSectors]);

  // Reload when filters change
  useEffect(() => {
    fetchResults(0, false);
  }, [fetchResults]);

  const loadMore = async () => {
    const newOffset = offset + LIMIT;
    setOffset(newOffset);
    await fetchResults(newOffset, true);
  };

  const hasMore = results.length < total;

  // Client-side analyst count filter (applied after live data is returned)
  const filteredResults = results.filter(
    (r) => r.n_analysts === null || r.n_analysts <= maxAnalysts,
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-3 mb-2">
          <Compass size={28} className="text-accent" />
          Discover Undercovered Stocks
        </h1>
        <p className="text-muted max-w-2xl">
          Small and mid-cap companies with minimal Wall Street analyst coverage.
          For these names, TickrAI's EDGAR-based AI analysis may be the most comprehensive
          research available anywhere.
        </p>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          {/* Sector */}
          <div className="flex-1 min-w-[160px]">
            <label className="block text-xs text-muted font-medium mb-1.5">Sector</label>
            <select
              value={selectedSector}
              onChange={(e) => setSelectedSector(e.target.value)}
              className="w-full px-3 py-2 rounded-[8px] border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 cursor-pointer"
            >
              <option value="">All Sectors</option>
              {sectors.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Analyst coverage — client-side filter on returned results */}
          <div className="flex-1 min-w-[160px]">
            <label className="block text-xs text-muted font-medium mb-1.5">Analyst Coverage</label>
            <select
              value={maxAnalysts}
              onChange={(e) => setMaxAnalysts(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-[8px] border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 cursor-pointer"
            >
              {MAX_ANALYST_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Cap tier */}
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-muted font-medium mb-1.5">Market Cap Tier</label>
            <select
              value={capTier}
              onChange={(e) => setCapTier(e.target.value)}
              className="w-full px-3 py-2 rounded-[8px] border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 cursor-pointer"
            >
              <option value="">All Sizes</option>
              <option value="micro">Micro-cap (&lt;$300M)</option>
              <option value="small">Small-cap ($300M–$2B)</option>
              <option value="mid">Mid-cap ($2B–$10B)</option>
            </select>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between">
          <p className="text-xs text-muted">
            {loading ? 'Fetching live data…' : `Showing ${filteredResults.length} of ${total} companies`}
          </p>
          <button
            onClick={() => fetchResults(0, false)}
            className="flex items-center gap-1.5 text-xs text-accent hover:underline cursor-pointer"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>
      </Card>

      {/* Results */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filteredResults.length === 0 ? (
        <Card className="text-center py-12">
          <Compass size={40} className="mx-auto text-muted mb-3 opacity-40" />
          <h3 className="font-semibold text-lg mb-1">No stocks found</h3>
          <p className="text-sm text-muted">Try broadening your filters — or load more results.</p>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {filteredResults.map((r) => (
              <StockCard key={r.ticker} result={r} />
            ))}
          </div>

          {hasMore && (
            <div className="text-center">
              <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-fg/30 border-t-fg rounded-full animate-spin" />
                    Loading…
                  </span>
                ) : (
                  `Load more (${total - results.length} remaining)`
                )}
              </Button>
            </div>
          )}
        </>
      )}

      <p className="text-xs text-muted mt-8 text-center">
        Universe: curated small and mid-cap US stocks. Analyst count from Yahoo Finance, updated daily.
        Prices refresh every 24 hours in the screener — click a ticker for live data.
      </p>
    </div>
  );
}

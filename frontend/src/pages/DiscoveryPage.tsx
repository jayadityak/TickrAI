import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ChevronRight, Compass, FileText, RefreshCw, TrendingDown, TrendingUp, ArrowUpDown } from 'lucide-react';
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
  analyst_upside_pct: number | null;
  recommendation_key: string;
  week52_high: number | null;
  week52_low: number | null;
  range_position: number | null;
  trailing_pe: number | null;
  return_on_equity: number | null;
  discovery_score: number;
}

const CAP_TIER_LABELS: Record<string, string> = {
  micro: 'Micro-cap',
  small: 'Small-cap',
  mid:   'Mid-cap',
};

const MAX_ANALYST_OPTIONS = [
  { label: 'Any coverage',    value: 999 },
  { label: 'No coverage (0)', value: 0 },
  { label: '≤ 2 analysts',    value: 2 },
  { label: '≤ 5 analysts',    value: 5 },
  { label: '≤ 10 analysts',   value: 10 },
];

const SORT_OPTIONS = [
  { label: 'Discovery Score', value: 'discovery_score' },
  { label: 'Analyst Upside',  value: 'analyst_upside' },
  { label: "Today's Change",  value: 'change_pct' },
  { label: 'Market Cap',      value: 'market_cap' },
];

const REC_LABELS: Record<string, { label: string; color: string }> = {
  strong_buy:  { label: 'Strong Buy',  color: 'text-green-600 bg-green-500/10 border-green-500/20' },
  buy:         { label: 'Buy',         color: 'text-green-500 bg-green-500/10 border-green-500/20' },
  hold:        { label: 'Hold',        color: 'text-amber-500 bg-amber/10 border-amber/20' },
  sell:        { label: 'Sell',        color: 'text-red-500 bg-red/10 border-red/20' },
  strong_sell: { label: 'Strong Sell', color: 'text-red-600 bg-red/10 border-red/20' },
  underperform:{ label: 'Underperform',color: 'text-red-500 bg-red/10 border-red/20' },
  underweight: { label: 'Underweight', color: 'text-red-500 bg-red/10 border-red/20' },
  overweight:  { label: 'Overweight',  color: 'text-green-500 bg-green-500/10 border-green-500/20' },
  outperform:  { label: 'Outperform',  color: 'text-green-500 bg-green-500/10 border-green-500/20' },
  neutral:     { label: 'Neutral',     color: 'text-muted bg-surface2 border-border' },
};

function DiscoveryScoreBadge({ score }: { score: number }) {
  const color =
    score >= 70 ? 'bg-green-500/15 text-green-500 border-green-500/30' :
    score >= 50 ? 'bg-amber/15 text-amber border-amber/30' :
                  'bg-surface2 text-muted border-border';
  return (
    <div className={`flex flex-col items-center justify-center w-14 h-14 rounded-xl border-2 shrink-0 ${color}`}>
      <span className="text-xl font-bold leading-none">{score}</span>
      <span className="text-[9px] font-semibold uppercase tracking-wide mt-0.5 opacity-70">Score</span>
    </div>
  );
}

function AnalystBadge({ n }: { n: number | null }) {
  if (n === null) return <span className="text-xs text-muted">Unknown</span>;
  if (n === 0)
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red/10 text-red border border-red/20">0 analysts</span>;
  if (n <= 2)
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber/10 text-amber border border-amber/20">{n} analyst{n > 1 ? 's' : ''}</span>;
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-surface2 text-muted border border-border">{n} analysts</span>;
}

function RecommendationBadge({ recKey }: { recKey: string }) {
  if (!recKey) return null;
  const rec = REC_LABELS[recKey.toLowerCase()];
  if (!rec) return null;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${rec.color}`}>
      {rec.label}
    </span>
  );
}

function RangeBar({ position }: { position: number | null }) {
  if (position === null) return null;
  const pct = Math.round(position * 100);
  return (
    <div className="mt-2">
      <div className="flex justify-between text-[10px] text-muted mb-1">
        <span>52w Low</span>
        <span className="font-medium">{pct}% of range</span>
        <span>52w High</span>
      </div>
      <div className="h-1.5 bg-surface2 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${pct <= 40 ? 'bg-green-500' : pct <= 70 ? 'bg-amber' : 'bg-red-400'}`}
          style={{ width: `${Math.max(3, pct)}%` }}
        />
      </div>
    </div>
  );
}

function StockCard({ result }: { result: ScreenResult }) {
  return (
    <Card className="hover:border-accent/40 transition-colors">
      <div className="flex items-start gap-3">
        {/* Discovery Score */}
        <DiscoveryScoreBadge score={result.discovery_score} />

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-0.5">
                <Link
                  to={`/report/${result.ticker}`}
                  className="font-bold text-lg text-accent hover:underline leading-none"
                >
                  {result.ticker}
                </Link>
                <AnalystBadge n={result.n_analysts} />
                {result.recommendation_key && (
                  <RecommendationBadge recKey={result.recommendation_key} />
                )}
              </div>
              <p className="text-sm text-muted truncate">{result.name}</p>
            </div>

            {/* Price */}
            <div className="text-right shrink-0">
              {result.price ? (
                <>
                  <p className="font-semibold text-base">${result.price.toFixed(2)}</p>
                  {result.change_pct !== null && (
                    <p className={`text-xs flex items-center justify-end gap-0.5 ${result.positive ? 'text-green-500' : 'text-red-500'}`}>
                      {result.positive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                      {result.positive ? '+' : ''}{result.change_pct.toFixed(2)}%
                    </p>
                  )}
                  {result.analyst_upside_pct !== null && (
                    <p className={`text-xs font-medium mt-0.5 ${result.analyst_upside_pct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {result.analyst_upside_pct >= 0 ? '▲' : '▼'} {Math.abs(result.analyst_upside_pct).toFixed(1)}% to target
                    </p>
                  )}
                </>
              ) : (
                <p className="text-muted text-sm">—</p>
              )}
            </div>
          </div>

          {/* Sector + Cap */}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <Badge variant="default">{result.sector}</Badge>
            <span className="text-xs text-muted">{CAP_TIER_LABELS[result.cap_tier] || result.cap_tier}</span>
            <span className="text-xs text-muted">{result.market_cap}</span>
            {result.trailing_pe !== null && (
              <span className="text-xs text-muted">P/E {result.trailing_pe}x</span>
            )}
          </div>

          {/* 52-week range bar */}
          <RangeBar position={result.range_position} />
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
      <div className="animate-pulse flex gap-3">
        <div className="w-14 h-14 bg-surface2 rounded-xl shrink-0" />
        <div className="flex-1">
          <div className="flex justify-between mb-2">
            <div className="h-6 w-20 bg-surface2 rounded" />
            <div className="h-6 w-16 bg-surface2 rounded" />
          </div>
          <div className="h-4 w-48 bg-surface2 rounded mb-3" />
          <div className="flex gap-2">
            <div className="h-5 w-24 bg-surface2 rounded-full" />
            <div className="h-5 w-16 bg-surface2 rounded" />
          </div>
          <div className="h-1.5 w-full bg-surface2 rounded-full mt-3" />
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
  const [maxAnalysts, setMaxAnalysts] = useState(999);
  const [capTier, setCapTier] = useState('');
  const [sortBy, setSortBy] = useState('discovery_score');
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
      const params: Record<string, string | number> = {
        limit: LIMIT,
        offset: newOffset,
        sort_by: sortBy,
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
  }, [selectedSector, capTier, sortBy]);

  useEffect(() => {
    fetchSectors();
  }, [fetchSectors]);

  useEffect(() => {
    fetchResults(0, false);
  }, [fetchResults]);

  const loadMore = async () => {
    const newOffset = offset + LIMIT;
    setOffset(newOffset);
    await fetchResults(newOffset, true);
  };

  const hasMore = results.length < total;

  // Client-side analyst count filter
  const filteredResults = results.filter(
    (r) => maxAnalysts === 999 || r.n_analysts === null || r.n_analysts <= maxAnalysts,
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
          Ranked by our proprietary <span className="text-fg font-medium">Discovery Score</span> — combining analyst coverage gap, upside potential, 52-week momentum, and financial quality.
        </p>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          {/* Sector */}
          <div className="flex-1 min-w-[140px]">
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

          {/* Cap tier */}
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-muted font-medium mb-1.5">Market Cap</label>
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

          {/* Analyst coverage */}
          <div className="flex-1 min-w-[140px]">
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

          {/* Sort by */}
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-muted font-medium mb-1.5 flex items-center gap-1">
              <ArrowUpDown size={11} /> Sort By
            </label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full px-3 py-2 rounded-[8px] border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 cursor-pointer"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
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
          <p className="text-sm text-muted">Try broadening your filters.</p>
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
        Universe: 400 curated small and mid-cap US stocks across 9 sectors. Discovery Score combines analyst coverage gap, upside potential, momentum, and quality signals. Prices refresh every 24 hours.
      </p>
    </div>
  );
}

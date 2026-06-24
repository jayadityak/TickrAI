import { useState, useEffect } from 'react';
import { AlertTriangle, BarChart2, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import axios from 'axios';
import Card from '../ui/Card';
import KalshiEarningsBadge from './KalshiEarningsBadge';

// ── Types ──────────────────────────────────────────────────────────────────

interface PriceTargets {
  mean: number | null;
  high: number | null;
  low: number | null;
  num_analysts: number | null;
  upside_pct: number | null;
}

interface RatingDist {
  strong_buy: number;
  buy: number;
  hold: number;
  sell: number;
  strong_sell: number;
  total: number;
  score: number;
  consensus: string;
}

interface RatingChange {
  date: string;
  firm: string;
  from_grade: string;
  to_grade: string;
  direction: 'upgrade' | 'downgrade' | 'maintain';
}

interface EpsPeriod {
  estimate: number | null;
  ago_30d: number | null;
  ago_90d: number | null;
  trend: 'up' | 'down' | 'flat';
}

interface ShortInterest {
  short_pct_float: number | null;
  short_ratio: number | null;
  shares_short: number | null;
}

interface KeyStats {
  beta: number | null;
  forward_pe: number | null;
  trailing_pe: number | null;
  forward_eps: number | null;
  peg_ratio: number | null;
  price_to_book: number | null;
  ev_to_ebitda: number | null;
  price_to_sales: number | null;
  dividend_yield: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  fifty_day_avg: number | null;
  two_hundred_day_avg: number | null;
  avg_volume: number | null;
  return_on_equity: number | null;
  return_on_assets: number | null;
  profit_margin: number | null;
  operating_margin: number | null;
  gross_margin: number | null;
  revenue_growth: number | null;
  earnings_growth: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  free_cashflow: number | null;
  total_cash: number | null;
  total_debt: number | null;
}

interface AnalystData {
  ticker: string;
  company_name: string;
  current_price: number | null;
  currency: string;
  price_targets: PriceTargets;
  rating_dist: Partial<RatingDist>;
  recent_changes: RatingChange[];
  eps_estimates: Record<string, EpsPeriod>;
  short_interest: ShortInterest;
  key_stats: KeyStats;
  pct_from_52w_high: number | null;
  pct_from_52w_low: number | null;
}

// ── Formatters ─────────────────────────────────────────────────────────────

const fmt = {
  price:  (v: number | null) => v == null ? '—' : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  pct:    (v: number | null, decimals = 1) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`,
  pctAbs: (v: number | null, decimals = 1) => v == null ? '—' : `${(v * 100).toFixed(decimals)}%`,
  ratio:  (v: number | null) => v == null ? '—' : `${v.toFixed(1)}x`,
  large:  (v: number | null) => {
    if (v == null) return '—';
    if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
    if (Math.abs(v) >= 1e9)  return `$${(v / 1e9).toFixed(1)}B`;
    if (Math.abs(v) >= 1e6)  return `$${(v / 1e6).toFixed(1)}M`;
    return `$${v.toLocaleString()}`;
  },
  volume: (v: number | null) => {
    if (v == null) return '—';
    if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
    return v.toLocaleString();
  },
};

// ── Rating config ──────────────────────────────────────────────────────────

const CONSENSUS_CONFIG: Record<string, { color: string; bg: string }> = {
  'Strong Buy':  { color: 'text-emerald-600', bg: 'bg-emerald-500' },
  'Buy':         { color: 'text-green',       bg: 'bg-green' },
  'Hold':        { color: 'text-amber',       bg: 'bg-amber' },
  'Sell':        { color: 'text-red',         bg: 'bg-red' },
  'Strong Sell': { color: 'text-red',         bg: 'bg-red' },
};

// ── Sub-components ─────────────────────────────────────────────────────────

function RatingBar({ dist }: { dist: Partial<RatingDist> }) {
  const total = dist.total || 0;
  if (total === 0) return null;

  const bars = [
    { label: 'Strong Buy', key: 'strong_buy' as const, color: 'bg-emerald-500' },
    { label: 'Buy',        key: 'buy'         as const, color: 'bg-green' },
    { label: 'Hold',       key: 'hold'        as const, color: 'bg-amber' },
    { label: 'Sell',       key: 'sell'        as const, color: 'bg-red' },
    { label: 'Strong Sell',key: 'strong_sell' as const, color: 'bg-red' },
  ];

  return (
    <div className="space-y-1.5">
      {bars.map(({ label, key, color }) => {
        const count = dist[key] ?? 0;
        const pct = total > 0 ? (count / total) * 100 : 0;
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="text-xs text-muted w-20 shrink-0">{label}</span>
            <div className="flex-1 h-2 bg-surface2 rounded-full overflow-hidden">
              <div
                className={`h-full ${color} rounded-full transition-all duration-700`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs tabular-nums text-muted w-6 text-right">{count}</span>
          </div>
        );
      })}
    </div>
  );
}

function PriceTargetGauge({
  targets, current,
}: {
  targets: PriceTargets; current: number | null;
}) {
  const { mean, high, low } = targets;
  if (!low || !mean || !high) return null;

  const range = high - low;
  const meanPct = range > 0 ? ((mean - low) / range) * 100 : 50;
  const currPct = current && range > 0
    ? Math.min(100, Math.max(0, ((current - low) / range) * 100))
    : null;

  return (
    <div>
      <div className="relative h-2 bg-surface2 rounded-full mx-1 mb-2">
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-red/30 via-amber/30 to-green/30" />
        {/* mean target */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-accent border-2 border-card shadow z-10"
          style={{ left: `calc(${meanPct}% - 7px)` }}
          title={`Analyst mean target: ${fmt.price(mean)}`}
        />
        {/* current price */}
        {currPct !== null && (
          <div
            className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-muted border-2 border-card z-10"
            style={{ left: `calc(${currPct}% - 5px)` }}
            title={`Current: ${fmt.price(current)}`}
          />
        )}
      </div>
      <div className="flex justify-between text-xs">
        <div><p className="text-red font-medium">{fmt.price(low)}</p><p className="text-muted">Low</p></div>
        <div className="text-center">
          <p className="text-accent font-bold">{fmt.price(mean)}</p>
          <p className="text-muted">Mean</p>
        </div>
        <div className="text-right"><p className="text-green font-medium">{fmt.price(high)}</p><p className="text-muted">High</p></div>
      </div>
    </div>
  );
}

function EpsTrend({ estimates }: { estimates: Record<string, EpsPeriod> }) {
  const periods: { key: string; label: string }[] = [
    { key: 'current_quarter', label: 'Current Qtr' },
    { key: 'next_quarter',    label: 'Next Qtr' },
    { key: 'current_year',    label: 'This Year' },
    { key: 'next_year',       label: 'Next Year' },
  ];
  const rows = periods.filter(p => estimates[p.key]);
  if (rows.length === 0) return null;

  return (
    <div>
      <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">EPS Estimate Trend</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {rows.map(({ key, label }) => {
          const e = estimates[key];
          const TrendIcon = e.trend === 'up' ? TrendingUp : e.trend === 'down' ? TrendingDown : Minus;
          const trendColor = e.trend === 'up' ? 'text-green' : e.trend === 'down' ? 'text-red' : 'text-muted';
          return (
            <div key={key} className="bg-surface rounded-[8px] p-2.5 text-center">
              <p className="text-xs text-muted mb-1">{label}</p>
              <p className="text-sm font-bold">{e.estimate != null ? `$${e.estimate.toFixed(2)}` : '—'}</p>
              {e.ago_30d != null && (
                <div className={`flex items-center justify-center gap-0.5 mt-1 ${trendColor}`}>
                  <TrendIcon size={10} />
                  <span className="text-xs">vs 30d ago</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function KeyStatsGrid({ stats, shortInterest, pctFromHigh, pctFromLow }: {
  stats: KeyStats;
  shortInterest: ShortInterest;
  pctFromHigh: number | null;
  pctFromLow: number | null;
}) {
  const items: { label: string; value: string; note?: string }[] = [
    { label: 'Forward P/E',   value: fmt.ratio(stats.forward_pe) },
    { label: 'Trailing P/E',  value: fmt.ratio(stats.trailing_pe) },
    { label: 'EV/EBITDA',     value: fmt.ratio(stats.ev_to_ebitda) },
    { label: 'P/S (TTM)',     value: fmt.ratio(stats.price_to_sales) },
    { label: 'P/B',           value: fmt.ratio(stats.price_to_book) },
    { label: 'PEG Ratio',     value: fmt.ratio(stats.peg_ratio) },
    { label: 'Forward EPS',   value: stats.forward_eps != null ? `$${stats.forward_eps.toFixed(2)}` : '—' },
    { label: 'Beta',          value: stats.beta != null ? stats.beta.toFixed(2) : '—' },
    { label: 'Gross Margin',  value: fmt.pctAbs(stats.gross_margin) },
    { label: 'Operating Margin', value: fmt.pctAbs(stats.operating_margin) },
    { label: 'Net Margin',    value: fmt.pctAbs(stats.profit_margin) },
    { label: 'ROE',           value: fmt.pctAbs(stats.return_on_equity) },
    { label: 'Revenue Growth',value: fmt.pctAbs(stats.revenue_growth) },
    { label: 'EPS Growth',    value: fmt.pctAbs(stats.earnings_growth) },
    { label: 'Debt/Equity',   value: stats.debt_to_equity != null ? `${stats.debt_to_equity.toFixed(1)}%` : '—' },
    { label: 'Current Ratio', value: stats.current_ratio != null ? stats.current_ratio.toFixed(2) : '—' },
    { label: 'Free Cash Flow',value: fmt.large(stats.free_cashflow) },
    { label: 'Cash',          value: fmt.large(stats.total_cash) },
    { label: 'Total Debt',    value: fmt.large(stats.total_debt) },
    { label: 'Avg Volume',    value: fmt.volume(stats.avg_volume) },
    { label: 'Short % Float', value: shortInterest.short_pct_float != null ? `${shortInterest.short_pct_float.toFixed(2)}%` : '—' },
    { label: 'Short Ratio',   value: shortInterest.short_ratio != null ? `${shortInterest.short_ratio.toFixed(1)}d` : '—' },
    { label: '52W High',      value: `${fmt.price(stats.fifty_two_week_high)}${pctFromHigh != null ? ` (${pctFromHigh.toFixed(1)}%)` : ''}` },
    { label: '52W Low',       value: `${fmt.price(stats.fifty_two_week_low)}${pctFromLow != null ? ` (+${pctFromLow.toFixed(1)}%)` : ''}` },
    { label: '50-Day MA',     value: fmt.price(stats.fifty_day_avg) },
    { label: '200-Day MA',    value: fmt.price(stats.two_hundred_day_avg) },
    { label: 'Dividend Yield',value: stats.dividend_yield != null ? `${stats.dividend_yield.toFixed(2)}%` : '—' },
  ].filter(item => item.value !== '—');

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-2">
      {items.map((item) => (
        <div key={item.label} className="flex justify-between items-baseline border-b border-border/50 py-1">
          <span className="text-xs text-muted truncate mr-2">{item.label}</span>
          <span className="text-xs font-semibold tabular-nums shrink-0">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function AnalystConsensus({
  ticker,
  onNoData,
  onCoverageData,
}: {
  ticker: string;
  onNoData?: () => void;
  onCoverageData?: (n: number | null) => void;
}) {
  const [data, setData] = useState<AnalystData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`/api/analyst/${ticker}`);
        setData(res.data);
        onCoverageData?.(res.data?.price_targets?.num_analysts ?? null);
        // Only hide if the backend signalled a hard error — key_stats still has value
        if ((res.data as any)?.error) onNoData?.();
      } catch {
        setError('Failed to load analyst data');
        onNoData?.();
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [ticker]);

  if (loading) {
    return (
      <Card>
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <BarChart2 size={20} className="text-accent" />
          Analyst Consensus
        </h2>
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[1, 2, 3].map(i => <div key={i} className="h-20 bg-surface2 rounded-[8px]" />)}
          </div>
          <div className="h-32 bg-surface2 rounded" />
          <div className="h-20 bg-surface2 rounded" />
        </div>
      </Card>
    );
  }

  if (error || !data || (data as any).error) {
    return null;
  }

  const { price_targets, rating_dist, recent_changes, eps_estimates, short_interest, key_stats } = data;
  const consensus = rating_dist.consensus || 'N/A';
  const cc = CONSENSUS_CONFIG[consensus] ?? { color: 'text-muted', bg: 'bg-muted' };
  const hasTargets = price_targets.mean || price_targets.high || price_targets.low;
  const hasDist = (rating_dist.total ?? 0) > 0;
  const hasEps = Object.keys(eps_estimates).length > 0;

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-5 flex items-center gap-2">
        <BarChart2 size={20} className="text-accent" />
        Analyst Consensus
        {consensus !== 'N/A' && (
          <span className={`ml-1 text-sm font-bold ${cc.color}`}>{consensus}</span>
        )}
        {price_targets.num_analysts != null && (
          <span className="text-xs text-muted font-normal ml-auto">
            {price_targets.num_analysts} analyst{price_targets.num_analysts !== 1 ? 's' : ''}
          </span>
        )}
      </h2>

      {/* Kalshi earnings beat probability — only renders when an open market exists */}
      <div className="mb-4">
        <KalshiEarningsBadge ticker={ticker} />
      </div>

      {/* Coverage gap callout — shown for undercovered stocks */}
      {price_targets.num_analysts != null && price_targets.num_analysts <= 3 && (
        <div className="mb-5 px-3 py-2.5 rounded-[8px] bg-amber/10 border border-amber/25 text-xs text-amber flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>
            {price_targets.num_analysts === 0
              ? 'No Wall Street analysts cover this stock.'
              : `Only ${price_targets.num_analysts} Wall Street analyst${price_targets.num_analysts > 1 ? 's' : ''} cover${price_targets.num_analysts === 1 ? 's' : ''} this stock.`}{' '}
            TickrAI's EDGAR-based analysis may be the most comprehensive research available for this name.
          </span>
        </div>
      )}

      {/* Top row: consensus + price target */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6 pb-6 border-b border-border">
        {/* Rating distribution */}
        {hasDist && (
          <div>
            <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Rating Breakdown</p>
            <RatingBar dist={rating_dist} />
          </div>
        )}
        {/* Price target */}
        {hasTargets && (
          <div>
            <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">
              12-Month Price Targets
              {price_targets.upside_pct != null && (
                <span className={`ml-2 font-bold ${price_targets.upside_pct >= 0 ? 'text-green' : 'text-red'}`}>
                  {fmt.pct(price_targets.upside_pct)} to mean
                </span>
              )}
            </p>
            <PriceTargetGauge targets={price_targets} current={data.current_price} />
          </div>
        )}
      </div>

      {/* EPS estimates */}
      {hasEps && (
        <div className="mb-6 pb-6 border-b border-border">
          <EpsTrend estimates={eps_estimates} />
        </div>
      )}

      {/* Recent upgrades/downgrades */}
      {recent_changes.length > 0 && (
        <div className="mb-6 pb-6 border-b border-border">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Recent Rating Changes</p>
          <div className="space-y-2">
            {recent_changes.map((c, i) => {
              const dirColor = c.direction === 'upgrade' ? 'text-green' : c.direction === 'downgrade' ? 'text-red' : 'text-muted';
              const DirIcon = c.direction === 'upgrade' ? TrendingUp : c.direction === 'downgrade' ? TrendingDown : Minus;
              return (
                <div key={i} className="flex items-center gap-3 text-xs py-1.5 border-b border-border/40 last:border-0">
                  <span className="text-muted shrink-0 w-20">{c.date}</span>
                  <span className="font-medium flex-1 truncate">{c.firm}</span>
                  {c.from_grade && c.from_grade !== 'N/A' && (
                    <span className="text-muted hidden sm:inline">{c.from_grade} →</span>
                  )}
                  <span className={`font-semibold shrink-0 ${dirColor}`}>{c.to_grade}</span>
                  <DirIcon size={12} className={`shrink-0 ${dirColor}`} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Key stats grid */}
      <div>
        <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Key Statistics</p>
        <KeyStatsGrid
          stats={key_stats}
          shortInterest={short_interest}
          pctFromHigh={data.pct_from_52w_high}
          pctFromLow={data.pct_from_52w_low}
        />
      </div>

      <p className="text-xs text-muted mt-4 pt-3 border-t border-border">
        Source: Yahoo Finance · Analyst ratings and estimates updated daily.
      </p>
    </Card>
  );
}

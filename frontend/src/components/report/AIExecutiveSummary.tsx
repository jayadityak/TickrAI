import { useState, useEffect, useRef } from 'react';
import { Sparkles, TrendingUp, TrendingDown, Zap, ChevronRight } from 'lucide-react';
import axios from 'axios';

interface AISummaryData {
  ticker: string;
  company_name: string;
  rating: string;
  conviction: string;
  summary_headline: string;
  investment_thesis: string;
  price_target_low: number | null;
  price_target_mid: number | null;
  price_target_high: number | null;
  current_price: number | null;
  bull_case: string[];
  bear_case: string[];
  key_catalysts: string[];
  time_horizon: string;
  sector: string;
}

// ── Rating config ──────────────────────────────────────────────────────────

const RATING_CONFIG: Record<string, { bg: string; text: string; border: string; label: string }> = {
  'Strong Buy':  { bg: 'bg-emerald-500', text: 'text-white', border: 'border-emerald-500', label: 'STRONG BUY' },
  'Buy':         { bg: 'bg-green',       text: 'text-white', border: 'border-green',       label: 'BUY'         },
  'Hold':        { bg: 'bg-amber',       text: 'text-white', border: 'border-amber',       label: 'HOLD'        },
  'Sell':        { bg: 'bg-red',         text: 'text-white', border: 'border-red',         label: 'SELL'        },
  'Strong Sell': { bg: 'bg-red-700',     text: 'text-white', border: 'border-red-700',     label: 'STRONG SELL' },
};

function getRatingConfig(rating: string) {
  return RATING_CONFIG[rating] ?? RATING_CONFIG['Hold'];
}

// ── Price target bar ───────────────────────────────────────────────────────

function PriceTargetBar({
  low, mid, high, current,
}: {
  low: number | null; mid: number | null; high: number | null; current: number | null;
}) {
  if (!low || !mid || !high) return null;

  const range = high - low;
  const midPct = range > 0 ? ((mid - low) / range) * 100 : 50;
  const currPct = current && range > 0 ? Math.min(100, Math.max(0, ((current - low) / range) * 100)) : null;

  return (
    <div className="mb-5">
      <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">
        12-Month Price Target Range
      </p>
      <div className="relative h-2 bg-surface2 rounded-full mx-1">
        {/* gradient fill */}
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-red/40 via-amber/40 to-green/40" />
        {/* base case marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-accent border-2 border-card shadow-md z-10"
          style={{ left: `calc(${midPct}% - 8px)` }}
        />
        {/* current price marker */}
        {currPct !== null && (
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-muted/60 border-2 border-card z-10"
            style={{ left: `calc(${currPct}% - 6px)` }}
            title={`Current: $${current?.toFixed(0)}`}
          />
        )}
      </div>
      <div className="flex justify-between mt-2 text-xs">
        <div>
          <p className="text-red font-semibold">${low.toFixed(0)}</p>
          <p className="text-muted">Bear</p>
        </div>
        <div className="text-center">
          <p className="text-accent font-bold text-sm">${mid.toFixed(0)}</p>
          <p className="text-muted">Base Case</p>
        </div>
        <div className="text-right">
          <p className="text-green font-semibold">${high.toFixed(0)}</p>
          <p className="text-muted">Bull</p>
        </div>
      </div>
      {current && mid && (
        <p className="text-xs text-muted text-center mt-1">
          {'Current: $' + current.toFixed(2) + ' · '}
          <span className={(mid / current - 1) >= 0 ? 'text-green' : 'text-red'}>
            {(mid / current - 1) >= 0 ? '+' : ''}
            {((mid / current - 1) * 100).toFixed(1)}% to base case
          </span>
        </p>
      )}
    </div>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────

function SummarySkeletonCard() {
  return (
    <div className="bg-card border border-border rounded-[16px] overflow-hidden shadow-sm">
      <div className="bg-gradient-to-r from-accent/5 to-accent/10 px-5 sm:px-6 py-4 flex items-center gap-3 border-b border-border">
        <div className="w-5 h-5 bg-accent/20 rounded animate-pulse" />
        <div className="h-4 w-40 bg-surface2 rounded animate-pulse" />
        <div className="ml-auto h-4 w-20 bg-surface2 rounded animate-pulse" />
      </div>
      <div className="p-5 sm:p-6 space-y-5">
        <div className="flex items-start gap-4">
          <div className="w-20 h-10 bg-surface2 rounded-[8px] animate-pulse shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-5 bg-surface2 rounded w-full animate-pulse" />
            <div className="h-5 bg-surface2 rounded w-3/4 animate-pulse" />
          </div>
        </div>
        <div className="space-y-2">
          <div className="h-4 bg-surface2 rounded w-full animate-pulse" />
          <div className="h-4 bg-surface2 rounded w-5/6 animate-pulse" />
          <div className="h-4 bg-surface2 rounded w-4/5 animate-pulse" />
        </div>
        <div className="h-12 bg-surface2 rounded animate-pulse" />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            {[1, 2, 3].map(i => <div key={i} className="h-4 bg-surface2 rounded animate-pulse" />)}
          </div>
          <div className="space-y-2">
            {[1, 2, 3].map(i => <div key={i} className="h-4 bg-surface2 rounded animate-pulse" />)}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function AIExecutiveSummary({
  ticker,
  reportData,
  isComplete,
}: {
  ticker: string;
  reportData: Record<string, any>;
  isComplete: boolean;
}) {
  const [data, setData] = useState<AISummaryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetched = useRef(false);

  useEffect(() => {
    // Only trigger once all 7 agents are done and we haven't fetched yet.
    // hasFetched ref prevents re-triggering when reportData reference changes.
    if (!isComplete || hasFetched.current || Object.keys(reportData).length === 0) return;
    hasFetched.current = true;

    const fetchSummary = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('tickrai_token');
        const res = await axios.post(
          `/api/reports/${ticker}/ai-summary`,
          { report_data: reportData },
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        setData(res.data);
      } catch {
        setError('AI summary unavailable');
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isComplete, ticker]);

  // Don't show at all until report is complete
  if (!isComplete) return null;

  if (loading) return <SummarySkeletonCard />;

  if (error || !data) return null;

  const rc = getRatingConfig(data.rating);
  const hasPriceTargets = data.price_target_low || data.price_target_mid || data.price_target_high;

  return (
    <div className="bg-card border border-border rounded-[16px] overflow-hidden shadow-sm">
      {/* Header bar */}
      <div className="bg-gradient-to-r from-accent/8 to-accent/4 px-5 sm:px-6 py-3.5 flex items-center gap-2.5 border-b border-border">
        <Sparkles size={16} className="text-accent shrink-0" />
        <span className="text-sm font-semibold text-accent">AI Analyst Recommendation</span>
        <span className="text-xs text-muted ml-1">· {data.company_name}</span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-muted">Conviction:</span>
          <span className={`text-xs font-semibold ${
            data.conviction === 'High' ? 'text-green' :
            data.conviction === 'Low'  ? 'text-red' : 'text-amber'
          }`}>
            {data.conviction}
          </span>
        </div>
      </div>

      <div className="p-5 sm:p-6">
        {/* Rating + Headline */}
        <div className="flex items-start gap-4 mb-5">
          <div className={`shrink-0 ${rc.bg} ${rc.text} px-3.5 py-2 rounded-[10px] font-bold text-sm tracking-wide shadow-sm`}>
            {rc.label}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-fg leading-snug">{data.summary_headline}</p>
            <p className="text-xs text-muted mt-1">{data.time_horizon} target · {data.sector}</p>
          </div>
        </div>

        {/* Investment thesis */}
        <p className="text-sm text-fg leading-relaxed mb-5 pb-5 border-b border-border">
          {data.investment_thesis}
        </p>

        {/* Price target */}
        {hasPriceTargets && (
          <div className="mb-5 pb-5 border-b border-border">
            <PriceTargetBar
              low={data.price_target_low}
              mid={data.price_target_mid}
              high={data.price_target_high}
              current={data.current_price}
            />
          </div>
        )}

        {/* Bull / Bear columns */}
        {(data.bull_case.length > 0 || data.bear_case.length > 0) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5 pb-5 border-b border-border">
            {/* Bull case */}
            <div>
              <div className="flex items-center gap-1.5 mb-2.5">
                <TrendingUp size={14} className="text-green shrink-0" />
                <span className="text-xs font-semibold text-green uppercase tracking-wide">Bull Case</span>
              </div>
              <ul className="space-y-2">
                {data.bull_case.map((point, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-fg leading-relaxed">
                    <span className="w-1.5 h-1.5 rounded-full bg-green mt-1.5 shrink-0" />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
            {/* Bear case */}
            <div>
              <div className="flex items-center gap-1.5 mb-2.5">
                <TrendingDown size={14} className="text-red shrink-0" />
                <span className="text-xs font-semibold text-red uppercase tracking-wide">Bear Case</span>
              </div>
              <ul className="space-y-2">
                {data.bear_case.map((point, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-fg leading-relaxed">
                    <span className="w-1.5 h-1.5 rounded-full bg-red mt-1.5 shrink-0" />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Catalysts */}
        {data.key_catalysts.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2.5">
              <Zap size={14} className="text-amber shrink-0" />
              <span className="text-xs font-semibold text-amber uppercase tracking-wide">Key Catalysts</span>
            </div>
            <ul className="space-y-1.5">
              {data.key_catalysts.map((catalyst, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-fg">
                  <ChevronRight size={12} className="text-muted mt-0.5 shrink-0" />
                  {catalyst}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Footer */}
        <p className="text-xs text-muted mt-5 pt-4 border-t border-border">
          AI-generated analysis · For informational purposes only. Not financial advice.
        </p>
      </div>
    </div>
  );
}

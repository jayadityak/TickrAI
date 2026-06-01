import { useState, useEffect } from 'react';
import { Building2 } from 'lucide-react';
import axios from 'axios';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface Holder {
  holder: string;
  shares: number | null;
  value: number | null;
  pct_out: number | null;
  date_reported: string;
}

interface InstitutionalSummary {
  pct_insiders: number | null;
  pct_institutions: number | null;
  pct_float_institutions: number | null;
  num_institutions: number | null;
  largest_holder: string;
  largest_holder_pct: number | null;
  signal: string;
}

interface InstitutionalData {
  top_holders: Holder[];
  top_funds: Holder[];
  summary: InstitutionalSummary;
}

function formatValue(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function formatShares(shares: number | null | undefined): string {
  if (shares == null) return '—';
  if (shares >= 1e9) return `${(shares / 1e9).toFixed(2)}B`;
  if (shares >= 1e6) return `${(shares / 1e6).toFixed(1)}M`;
  if (shares >= 1e3) return `${(shares / 1e3).toFixed(1)}K`;
  return shares.toLocaleString();
}

function formatPct(pct: number | null | undefined): string {
  if (pct == null) return '—';
  return `${pct.toFixed(2)}%`;
}

function HoldersTable({ rows, label }: { rows: Holder[]; label: string }) {
  return (
    <>
      <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">{label}</h3>
      <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0 mb-6">
        <table className="w-full text-sm min-w-[520px]">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="py-2 pr-3 text-muted font-medium w-8">#</th>
              <th className="py-2 pr-3 text-muted font-medium">Name</th>
              <th className="py-2 pr-3 text-muted font-medium text-right">Shares</th>
              <th className="py-2 pr-3 text-muted font-medium text-right hidden md:table-cell">Value</th>
              <th className="py-2 pr-3 text-muted font-medium text-right">% Held</th>
              <th className="py-2 text-muted font-medium text-right hidden md:table-cell">As Of</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((h, i) => (
              <tr key={i} className="border-b border-border/50 hover:bg-surface/50 transition-colors">
                <td className="py-2 pr-3 text-muted text-xs">{i + 1}</td>
                <td className="py-2 pr-3 font-medium">{h.holder}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{formatShares(h.shares)}</td>
                <td className="py-2 pr-3 text-right tabular-nums hidden md:table-cell">{formatValue(h.value)}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{formatPct(h.pct_out)}</td>
                <td className="py-2 text-right text-muted text-xs hidden md:table-cell">{h.date_reported}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function InstitutionalOwnership({ ticker, onNoData }: { ticker: string; onNoData?: () => void }) {
  const [data, setData] = useState<InstitutionalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`/api/institutional/${ticker}`);
        setData(res.data);
        // Keep the section visible even when empty — shows a fallback card
      } catch {
        setError('Failed to load institutional data');
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
          <Building2 size={20} className="text-accent" />
          Institutional Ownership
        </h2>
        <div className="animate-pulse space-y-3">
          <div className="grid grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 bg-surface2 rounded-[8px]" />
            ))}
          </div>
          <div className="h-4 bg-surface2 rounded w-full" />
          <div className="h-4 bg-surface2 rounded w-3/4" />
          <div className="h-24 bg-surface2 rounded w-full" />
        </div>
      </Card>
    );
  }

  if (error || !data || data.top_holders.length === 0) {
    return (
      <Card>
        <h2 className="font-semibold text-lg mb-3 flex items-center gap-2">
          <Building2 size={20} className="text-accent" />
          Institutional Ownership
        </h2>
        <p className="text-sm text-muted">
          No institutional holdings reported for this ticker. This is common for micro-cap and recently-listed stocks.
        </p>
      </Card>
    );
  }

  const { top_holders, top_funds, summary } = data;
  const signalVariant =
    summary.signal === 'Bullish' ? 'green' : summary.signal === 'Bearish' ? 'red' : 'default';

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
        <Building2 size={20} className="text-accent" />
        Institutional Ownership
        <Badge variant={signalVariant}>{summary.signal}</Badge>
      </h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-surface rounded-[8px] p-3 text-center">
          <p className="text-xs text-muted mb-1">Institutional %</p>
          <p className="text-lg font-bold">{formatPct(summary.pct_institutions)}</p>
          {summary.pct_float_institutions != null && (
            <p className="text-xs text-muted">{formatPct(summary.pct_float_institutions)} of float</p>
          )}
        </div>
        <div className="bg-surface rounded-[8px] p-3 text-center">
          <p className="text-xs text-muted mb-1"># Institutions</p>
          <p className="text-lg font-bold">
            {summary.num_institutions != null ? summary.num_institutions.toLocaleString() : '—'}
          </p>
        </div>
        <div className="bg-surface rounded-[8px] p-3 text-center">
          <p className="text-xs text-muted mb-1">Largest Holder</p>
          <p className="text-sm font-bold truncate" title={summary.largest_holder}>
            {summary.largest_holder}
          </p>
          <p className="text-xs text-muted">{formatPct(summary.largest_holder_pct)}</p>
        </div>
        <div className="bg-surface rounded-[8px] p-3 text-center">
          <p className="text-xs text-muted mb-1">Insider %</p>
          <p className="text-lg font-bold">{formatPct(summary.pct_insiders)}</p>
        </div>
      </div>

      {/* Tables */}
      <HoldersTable rows={top_holders} label="Top Institutional Holders" />
      {top_funds.length > 0 && <HoldersTable rows={top_funds} label="Top Mutual Fund Holders" />}

      <p className="text-xs text-muted mt-2">
        Source: SEC 13F filings via Yahoo Finance. Holdings reported quarterly; may lag up to 45 days.
      </p>
    </Card>
  );
}

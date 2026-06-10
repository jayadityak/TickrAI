import Card from '../ui/Card';

interface ETFOverviewData {
  fund_name?: string;
  issuer?: string;
  asset_class?: string;
  benchmark?: string;
  inception_date?: string;
  aum?: string;
  expense_ratio?: string;
  nav?: string;
  exchange?: string;
  domicile?: string;
  currency?: string;
  holdings_count?: number | null;
  summary?: string;
  website?: string;
}

export default function ETFOverview({ data }: { data: ETFOverviewData }) {
  if (!data) return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">📋</span>
        <h2 className="font-semibold text-lg">ETF Overview</h2>
      </div>
      <div className="space-y-3 animate-pulse">
        <div className="h-4 bg-surface2 rounded w-3/4" />
        <div className="h-4 bg-surface2 rounded w-1/2" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-16 bg-surface2 rounded-[8px]" />)}
        </div>
      </div>
    </Card>
  );

  const stats = [
    { label: 'AUM', value: data.aum },
    { label: 'Expense Ratio', value: data.expense_ratio },
    { label: 'NAV', value: data.nav },
    { label: 'Holdings', value: data.holdings_count != null ? data.holdings_count.toLocaleString() : null },
  ].filter(s => s.value != null);

  const meta = [
    { label: 'Benchmark', value: data.benchmark },
    { label: 'Asset Class', value: data.asset_class },
    { label: 'Exchange', value: data.exchange },
    { label: 'Inception', value: data.inception_date },
    { label: 'Issuer', value: data.issuer },
    { label: 'Currency', value: data.currency },
  ].filter(m => m.value);

  return (
    <Card>
      <div className="flex items-start justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xl">📋</span>
          <h2 className="font-semibold text-lg">ETF Overview</h2>
        </div>
        {data.asset_class && (
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
            {data.asset_class}
          </span>
        )}
      </div>
      <p className="text-xs text-muted mb-4">Fund profile · strategy · key facts</p>

      {/* Summary */}
      {data.summary && (
        <p className="text-sm text-muted leading-relaxed mb-5">{data.summary}</p>
      )}

      {/* Key stats grid */}
      {stats.length > 0 && (
        <div className={`grid grid-cols-2 sm:grid-cols-${Math.min(stats.length, 4)} gap-3 mb-5`}>
          {stats.map(({ label, value }) => (
            <div key={label} className="bg-surface rounded-[8px] p-3 text-center">
              <p className="text-xs text-muted mb-1">{label}</p>
              <p className="font-semibold text-sm">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Metadata */}
      {meta.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2 border-t border-border pt-4">
          {meta.map(({ label, value }) => (
            <div key={label} className="flex flex-col">
              <span className="text-xs text-muted">{label}</span>
              <span className="text-sm font-medium truncate">{value}</span>
            </div>
          ))}
        </div>
      )}

      {data.website && (
        <a
          href={data.website}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-xs text-accent hover:underline"
        >
          Fund website ↗
        </a>
      )}
    </Card>
  );
}

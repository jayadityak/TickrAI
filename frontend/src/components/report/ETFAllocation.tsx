import { useState } from 'react';
import Card from '../ui/Card';

interface AllocationItem {
  sector?: string;
  country?: string;
  weight: number;
  weight_str: string;
}

interface ETFAllocationData {
  sector_weights?: AllocationItem[];
  country_weights?: AllocationItem[];
  has_country_data?: boolean;
}

function AllocationBars({ items, labelKey }: { items: AllocationItem[]; labelKey: 'sector' | 'country' }) {
  const maxWeight = Math.max(...items.map(i => i.weight), 1);

  return (
    <div className="space-y-2.5">
      {items.map((item, i) => {
        const label = item[labelKey] ?? 'Unknown';
        const pct = (item.weight / maxWeight) * 100;
        return (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-muted w-36 shrink-0 truncate" title={label}>{label}</span>
            <div className="flex-1 h-2 bg-surface2 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs font-medium tabular-nums w-12 text-right shrink-0">
              {item.weight_str}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function ETFAllocation({ data }: { data: ETFAllocationData }) {
  const [activeTab, setActiveTab] = useState<'sector' | 'country'>('sector');

  if (!data) return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">🥧</span>
        <h2 className="font-semibold text-lg">Allocation</h2>
      </div>
      <div className="space-y-2.5 animate-pulse">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-3 bg-surface2 rounded w-28" />
            <div className="h-2 bg-surface2 rounded flex-1" />
            <div className="h-3 bg-surface2 rounded w-10" />
          </div>
        ))}
      </div>
    </Card>
  );

  const sectors = data.sector_weights ?? [];
  const countries = data.country_weights ?? [];
  const hasCountry = data.has_country_data && countries.length > 1;

  if (sectors.length === 0 && countries.length === 0) return (
    <Card>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">🥧</span>
        <h2 className="font-semibold text-lg">Allocation</h2>
      </div>
      <p className="text-sm text-muted">Allocation data not available for this ETF.</p>
    </Card>
  );

  return (
    <Card>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">🥧</span>
        <h2 className="font-semibold text-lg">Allocation</h2>
      </div>
      <p className="text-xs text-muted mb-4">Portfolio composition by weight</p>

      {/* Tab switcher — only show if both sector and country data exist */}
      {hasCountry && sectors.length > 0 && (
        <div className="flex gap-1 mb-4 p-1 bg-surface rounded-[8px] w-fit">
          {(['sector', 'country'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`text-xs px-3 py-1.5 rounded-[6px] font-medium transition-colors capitalize ${
                activeTab === tab
                  ? 'bg-card text-fg shadow-sm'
                  : 'text-muted hover:text-fg'
              }`}
            >
              {tab === 'sector' ? 'Sector' : 'Country'}
            </button>
          ))}
        </div>
      )}

      {/* Sector bars */}
      {(!hasCountry || activeTab === 'sector') && sectors.length > 0 && (
        <div>
          {!hasCountry && sectors.length > 0 && (
            <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Sector Allocation</p>
          )}
          <AllocationBars items={sectors} labelKey="sector" />
        </div>
      )}

      {/* Country bars */}
      {hasCountry && activeTab === 'country' && countries.length > 0 && (
        <div>
          <AllocationBars items={countries} labelKey="country" />
        </div>
      )}

      {/* Fallback: no sector data, show country only */}
      {sectors.length === 0 && countries.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Country Allocation</p>
          <AllocationBars items={countries} labelKey="country" />
        </div>
      )}
    </Card>
  );
}

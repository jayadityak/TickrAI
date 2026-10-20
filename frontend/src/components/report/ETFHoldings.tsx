import { useState } from 'react';
import Card from '../ui/Card';

interface Holding {
  name: string;
  symbol: string;
  weight: number;
  weight_str: string;
  shares?: string | null;
  market_value?: string | null;
}

interface ETFHoldingsData {
  holdings?: Holding[];
  total_shown?: number;
}

export default function ETFHoldings({ data }: { data: ETFHoldingsData }) {
  const [showAll, setShowAll] = useState(false);

  if (!data) return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">🏦</span>
        <h2 className="font-semibold text-lg">Top Holdings</h2>
      </div>
      <div className="space-y-2 animate-pulse">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-4 bg-surface2 rounded w-8" />
            <div className="h-4 bg-surface2 rounded flex-1" />
            <div className="h-4 bg-surface2 rounded w-16" />
          </div>
        ))}
      </div>
    </Card>
  );

  const holdings = data.holdings ?? [];
  if (holdings.length === 0) return (
    <Card>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">🏦</span>
        <h2 className="font-semibold text-lg">Top Holdings</h2>
      </div>
      <p className="text-sm text-muted">Holdings data not available for this ETF.</p>
    </Card>
  );

  const INITIAL_SHOW = 10;
  const visible = showAll ? holdings : holdings.slice(0, INITIAL_SHOW);
  const maxWeight = Math.max(...holdings.map(h => h.weight), 1);
  const hasMarketValue = holdings.some(h => h.market_value);

  return (
    <Card>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">🏦</span>
        <h2 className="font-semibold text-lg">Top Holdings</h2>
      </div>
      <p className="text-xs text-muted mb-4">
        Top {Math.min(holdings.length, data.total_shown ?? holdings.length)} holdings by weight
      </p>

      <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
        <table className="w-full text-sm min-w-[400px]">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="pb-2 text-xs text-muted font-medium w-8">#</th>
              <th className="pb-2 text-xs text-muted font-medium">Company</th>
              <th className="pb-2 text-xs text-muted font-medium text-right">Weight</th>
              {hasMarketValue && <th className="pb-2 text-xs text-muted font-medium text-right hidden sm:table-cell">Market Value</th>}
            </tr>
          </thead>
          <tbody>
            {visible.map((h, i) => (
              <tr key={i} className="border-b border-border/50 last:border-0">
                <td className="py-2.5 text-xs text-muted">{i + 1}</td>
                <td className="py-2.5">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium text-sm truncate max-w-[200px]">{h.name}</span>
                    {h.symbol && (
                      <span className="text-xs text-muted">{h.symbol}</span>
                    )}
                  </div>
                </td>
                <td className="py-2.5 text-right">
                  <div className="flex flex-col items-end gap-1">
                    <span className="font-semibold text-sm tabular-nums">{h.weight_str}</span>
                    <div className="w-20 h-1 bg-surface2 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full"
                        style={{ width: `${(h.weight / maxWeight) * 100}%` }}
                      />
                    </div>
                  </div>
                </td>
                {hasMarketValue && (
                  <td className="py-2.5 text-right text-xs text-muted hidden sm:table-cell">
                    {h.market_value ?? '—'}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {holdings.length > INITIAL_SHOW && (
        <button
          onClick={() => setShowAll(v => !v)}
          className="mt-3 text-sm text-accent hover:underline"
        >
          {showAll
            ? 'Show less ↑'
            : `Show ${holdings.length - INITIAL_SHOW} more holdings ↓`}
        </button>
      )}
    </Card>
  );
}

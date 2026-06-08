import { useState } from 'react';
import { ArrowUpDown, ChevronUp, ChevronDown } from 'lucide-react';
import Card from '../ui/Card';

interface Props {
  data: any;
}

function display(value: any): string {
  if (value == null) return '—';
  return String(value);
}

type SortDir = 'asc' | 'desc';

const SORTABLE_COLS = [
  { key: 'market_cap', label: 'Market Cap' },
  { key: 'pe_ratio',   label: 'P/E' },
  { key: 'revenue_growth', label: 'Rev Growth' },
  { key: 'margin',     label: 'Margin' },
];

// Try to parse a display string like "$1.2B", "+14.3%", "22.1" to a float for sorting
function parseNum(val: any): number {
  if (val == null || val === '—') return -Infinity;
  const str = String(val).replace(/[^0-9.\-+%]/g, '');
  const n = parseFloat(str);
  return isNaN(n) ? -Infinity : n;
}

export default function SectorPeerView({ data }: Props) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const peers: any[] = Array.isArray(data.peer_comparison) ? data.peer_comparison : [];

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = sortKey
    ? [...peers].sort((a, b) => {
        const va = parseNum(a[sortKey] ?? a[sortKey.replace('_', '')]);
        const vb = parseNum(b[sortKey] ?? b[sortKey.replace('_', '')]);
        return sortDir === 'desc' ? vb - va : va - vb;
      })
    : peers;

  function SortIcon({ col }: { col: string }) {
    if (sortKey !== col) return <ArrowUpDown size={12} className="text-muted ml-1 inline opacity-50" />;
    return sortDir === 'desc'
      ? <ChevronDown size={12} className="text-accent ml-1 inline" />
      : <ChevronUp size={12} className="text-accent ml-1 inline" />;
  }

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-1">📈 Sector &amp; Peers</h2>
      <p className="text-xs text-muted mb-4">Industry context and competitive benchmarking</p>

      {data.sector_overview && (
        <p className="text-muted leading-relaxed">{data.sector_overview}</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
        {Array.isArray(data.tailwinds) && data.tailwinds.length > 0 && (
          <div className="border-l-4 border-green pl-3">
            <h3 className="font-medium mb-2 text-green text-sm">Tailwinds</h3>
            <ul className="space-y-1">
              {data.tailwinds.map((item: string, i: number) => (
                <li key={i} className="text-sm text-muted">{item}</li>
              ))}
            </ul>
          </div>
        )}

        {Array.isArray(data.headwinds) && data.headwinds.length > 0 && (
          <div className="border-l-4 border-red pl-3">
            <h3 className="font-medium mb-2 text-red text-sm">Headwinds</h3>
            <ul className="space-y-1">
              {data.headwinds.map((item: string, i: number) => (
                <li key={i} className="text-sm text-muted">{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {peers.length > 0 && (
        <>
          <div className="flex items-center justify-between mt-6 mb-2">
            <h3 className="font-medium">Peer Comparison</h3>
            <span className="text-xs text-muted">Click column to sort</span>
          </div>
          <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
            <table className="w-full text-sm min-w-[520px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 font-medium whitespace-nowrap">Company</th>
                  {SORTABLE_COLS.map(({ key, label }) => (
                    <th
                      key={key}
                      className="text-right py-2 px-2 font-medium whitespace-nowrap cursor-pointer hover:text-accent select-none"
                      onClick={() => handleSort(key)}
                    >
                      {label}<SortIcon col={key} />
                    </th>
                  ))}
                  <th className="text-left py-2 px-2 font-medium whitespace-nowrap">Assessment</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((peer: any, i: number) => (
                  <tr key={i} className="even:bg-surface border-b border-border last:border-0">
                    <td className="py-2 px-2 font-medium">
                      {peer.symbol || peer.company_name || peer.company || '—'}
                    </td>
                    <td className="text-right py-2 px-2">{display(peer.market_cap)}</td>
                    <td className="text-right py-2 px-2">{display(peer.pe_ratio || peer.pe)}</td>
                    <td className="text-right py-2 px-2">{display(peer.revenue_growth)}</td>
                    <td className="text-right py-2 px-2">{display(peer.margin)}</td>
                    <td className="text-left py-2 px-2 text-xs text-muted max-w-[200px]">{display(peer.assessment)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {data.relative_valuation && (
        <>
          <h3 className="font-medium mt-6 mb-2">Relative Valuation</h3>
          <p className="text-muted leading-relaxed">{data.relative_valuation}</p>
        </>
      )}
    </Card>
  );
}

import { useState } from 'react';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface Props {
  data: any;
}

function severityVariant(severity: string): 'green' | 'amber' | 'red' | 'default' {
  const s = severity?.toLowerCase();
  if (s === 'ok') return 'green';
  if (s === 'warning') return 'amber';
  if (s === 'critical') return 'red';
  return 'default';
}

const INITIAL_VISIBLE = 5;

export default function AuditorFlags({ data }: Props) {
  const [showAll, setShowAll] = useState(false);

  const allFlags: any[] = Array.isArray(data.flags) ? data.flags : [];

  // Pull Piotroski F-Score flag to the top, then show the rest
  const piotroskiFlag = allFlags.find((f) =>
    f.type?.toLowerCase().includes('piotroski') || f.type?.toLowerCase().includes('f-score'),
  );
  const otherFlags = allFlags.filter((f) => f !== piotroskiFlag);
  const visible = showAll ? otherFlags : otherFlags.slice(0, INITIAL_VISIBLE);
  const hidden = otherFlags.length - INITIAL_VISIBLE;

  // Parse "F-Score: X/Y" from piotroski description
  let fScore: number | null = null;
  let fTotal = 7;
  if (piotroskiFlag?.description) {
    const m = piotroskiFlag.description.match(/F-Score:\s*(\d+)\/(\d+)/);
    if (m) { fScore = parseInt(m[1]); fTotal = parseInt(m[2]); }
  }

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-1">🔍 Auditor Flags</h2>
      <p className="text-xs text-muted mb-4">Financial health indicators &amp; accounting quality signals</p>

      {/* Piotroski F-Score badge — prominent top placement */}
      {piotroskiFlag && fScore !== null && (
        <div className={`flex items-center gap-3 rounded-[8px] px-4 py-3 mb-4 border ${
          fScore >= 6 ? 'bg-green/5 border-green/20' :
          fScore >= 3 ? 'bg-amber/5 border-amber/20' :
          'bg-red/5 border-red/20'
        }`}>
          <div>
            <span className={`text-2xl font-bold ${
              fScore >= 6 ? 'text-green' : fScore >= 3 ? 'text-amber' : 'text-red'
            }`}>
              {fScore}
            </span>
            <span className="text-muted text-sm">/{fTotal}</span>
          </div>
          <div>
            <div className="text-sm font-medium">Piotroski F-Score</div>
            <div className="text-xs text-muted">
              {fScore >= 6 ? 'Strong financial health' : fScore >= 3 ? 'Mixed signals — some concerns' : 'Weak — multiple warning signs'}
            </div>
          </div>
          <div className="ml-auto">
            <Badge variant={severityVariant(piotroskiFlag.severity)}>{piotroskiFlag.severity}</Badge>
          </div>
        </div>
      )}

      {data.summary && (
        <p className="text-muted leading-relaxed mb-2">{data.summary}</p>
      )}

      {visible.map((flag: any, i: number) => (
        <div
          key={i}
          className="border border-border rounded-[8px] p-4 mt-3"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium">{flag.type}</span>
            {flag.severity && (
              <Badge variant={severityVariant(flag.severity)}>
                {flag.severity}
              </Badge>
            )}
          </div>
          {flag.description && (
            <p className="text-sm text-muted mt-2">{flag.description}</p>
          )}
          {flag.recommendation && (
            <p className="text-xs text-accent mt-1">{flag.recommendation}</p>
          )}
        </div>
      ))}

      {otherFlags.length > INITIAL_VISIBLE && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mt-4 text-sm text-accent hover:underline cursor-pointer"
        >
          {showAll ? 'Show less ↑' : `Show ${hidden} more flag${hidden !== 1 ? 's' : ''} ↓`}
        </button>
      )}
    </Card>
  );
}

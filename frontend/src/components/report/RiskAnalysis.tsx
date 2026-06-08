import { useState } from 'react';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface Props {
  data: any;
}

function riskLevelVariant(level: string): 'green' | 'amber' | 'red' | 'default' {
  const l = level?.toLowerCase();
  if (l === 'low') return 'green';
  if (l === 'medium') return 'amber';
  if (l === 'high') return 'red';
  return 'default';
}

function SeverityDots({ severity }: { severity: number }) {
  return (
    <div className="flex gap-1 mt-1" title={`Severity: ${severity}/5`}>
      {[1, 2, 3, 4, 5].map((dot) => (
        <span
          key={dot}
          className={`w-2 h-2 rounded-full ${
            dot <= severity ? 'bg-red' : 'bg-surface2'
          }`}
        />
      ))}
    </div>
  );
}

const INITIAL_VISIBLE = 5;

export default function RiskAnalysis({ data }: Props) {
  const [showAll, setShowAll] = useState(false);

  const risks: any[] = Array.isArray(data.risks) ? data.risks : [];
  const visible = showAll ? risks : risks.slice(0, INITIAL_VISIBLE);
  const hidden = risks.length - INITIAL_VISIBLE;

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="font-semibold text-lg">⚠️ Risk Analysis</h2>
          <p className="text-xs text-muted mt-0.5">Based on SEC filings, financial ratios &amp; macro factors</p>
        </div>
        {data.overall_risk_level && (
          <Badge variant={riskLevelVariant(data.overall_risk_level)}>
            {data.overall_risk_level} Risk
          </Badge>
        )}
      </div>

      {visible.map((risk: any, i: number) => (
        <div
          key={i}
          className="border border-border rounded-[8px] p-4 mt-3"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-sm">{risk.category}</span>
            {risk.severity != null && (
              <SeverityDots severity={risk.severity} />
            )}
          </div>
          {risk.description && (
            <p className="text-sm text-muted mt-2">{risk.description}</p>
          )}
          {risk.evidence && (
            <p className="text-xs text-muted italic mt-1">{risk.evidence}</p>
          )}
        </div>
      ))}

      {risks.length > INITIAL_VISIBLE && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mt-4 text-sm text-accent hover:underline cursor-pointer"
        >
          {showAll ? 'Show less ↑' : `Show ${hidden} more risk factor${hidden !== 1 ? 's' : ''} ↓`}
        </button>
      )}
    </Card>
  );
}

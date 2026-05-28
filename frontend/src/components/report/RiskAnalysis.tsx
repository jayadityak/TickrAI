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
    <div className="flex gap-1 mt-1">
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

export default function RiskAnalysis({ data }: Props) {
  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4">⚠️ Risk Analysis</h2>

      {data.overall_risk_level && (
        <div className="mb-4">
          <Badge variant={riskLevelVariant(data.overall_risk_level)}>
            {data.overall_risk_level}
          </Badge>
        </div>
      )}

      {Array.isArray(data.risks) &&
        data.risks.map((risk: any, i: number) => (
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
    </Card>
  );
}

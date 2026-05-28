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

export default function AuditorFlags({ data }: Props) {
  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4">🔍 Auditor Flags</h2>

      {data.summary && (
        <p className="text-muted leading-relaxed">{data.summary}</p>
      )}

      {Array.isArray(data.flags) &&
        data.flags.map((flag: any, i: number) => (
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
    </Card>
  );
}

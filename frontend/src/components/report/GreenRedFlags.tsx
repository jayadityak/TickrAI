import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface Props {
  data: any;
}

function scoreColor(score: number): string {
  if (score >= 7) return 'text-green';
  if (score >= 4) return 'text-amber';
  return 'text-red';
}

function significanceVariant(
  significance: string,
): 'green' | 'amber' | 'red' | 'default' {
  const s = significance?.toLowerCase();
  if (s === 'high') return 'red';
  if (s === 'medium') return 'amber';
  if (s === 'low') return 'green';
  return 'default';
}

export default function GreenRedFlags({ data }: Props) {
  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4">🚩 Green & Red Flags</h2>

      {data.overall_score != null && (
        <div className="mb-4">
          <span className={`text-4xl font-bold ${scoreColor(data.overall_score)}`}>
            {data.overall_score}
          </span>
          <span className="text-muted text-lg">/10</span>
        </div>
      )}

      {data.overall_assessment && (
        <p className="text-muted leading-relaxed">{data.overall_assessment}</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
        {/* Green Flags */}
        {Array.isArray(data.green_flags) && data.green_flags.length > 0 && (
          <div>
            <h3 className="font-medium text-green mb-3">Green Flags</h3>
            {data.green_flags.map((flag: any, i: number) => (
              <div key={i} className="bg-emerald-50 rounded-[8px] p-3 mb-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm text-green">
                    {flag.flag || flag.name}
                  </span>
                  {flag.significance && (
                    <Badge variant={significanceVariant(flag.significance)}>
                      {flag.significance}
                    </Badge>
                  )}
                </div>
                {flag.evidence && (
                  <p className="text-xs text-muted mt-1">{flag.evidence}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Red Flags */}
        {Array.isArray(data.red_flags) && data.red_flags.length > 0 && (
          <div>
            <h3 className="font-medium text-red mb-3">Red Flags</h3>
            {data.red_flags.map((flag: any, i: number) => (
              <div key={i} className="bg-red-50 rounded-[8px] p-3 mb-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm text-red">
                    {flag.flag || flag.name}
                  </span>
                  {flag.significance && (
                    <Badge variant={significanceVariant(flag.significance)}>
                      {flag.significance}
                    </Badge>
                  )}
                </div>
                {flag.evidence && (
                  <p className="text-xs text-muted mt-1">{flag.evidence}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

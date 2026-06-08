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

function scoreLabel(score: number): string {
  if (score >= 8) return 'Strong Buy signal';
  if (score >= 6) return 'Broadly positive';
  if (score >= 4) return 'Mixed signals';
  return 'Caution warranted';
}

export default function GreenRedFlags({ data }: Props) {
  const greenFlags: any[] = Array.isArray(data.green_flags) ? data.green_flags : [];
  const redFlags: any[] = Array.isArray(data.red_flags) ? data.red_flags : [];

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-1">🚩 Green &amp; Red Flags</h2>
      <p className="text-xs text-muted mb-4">Cross-signal synthesis: fundamentals · insiders · sentiment</p>

      {data.overall_score != null && (
        <div className="flex items-end gap-3 mb-3">
          <div>
            <span className={`text-5xl font-bold ${scoreColor(data.overall_score)}`}>
              {data.overall_score}
            </span>
            <span className="text-muted text-xl">/10</span>
          </div>
          <div className="pb-1">
            <div className={`text-sm font-medium ${scoreColor(data.overall_score)}`}>
              {scoreLabel(data.overall_score)}
            </div>
            <div className="text-xs text-muted">Overall conviction score</div>
          </div>
        </div>
      )}

      {data.overall_assessment && (
        <p className="text-muted leading-relaxed mb-2">{data.overall_assessment}</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
        {/* Green Flags */}
        {greenFlags.length > 0 && (
          <div>
            <h3 className="font-medium text-green mb-3 flex items-center gap-1.5">
              <span>✅</span> Green Flags ({greenFlags.length})
            </h3>
            {greenFlags.map((flag: any, i: number) => (
              <div key={i} className="bg-green/8 border border-green/15 rounded-[8px] p-3 mb-2">
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
        {redFlags.length > 0 && (
          <div>
            <h3 className="font-medium text-red mb-3 flex items-center gap-1.5">
              <span>🚩</span> Red Flags ({redFlags.length})
            </h3>
            {redFlags.map((flag: any, i: number) => (
              <div key={i} className="bg-red/8 border border-red/15 rounded-[8px] p-3 mb-2">
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

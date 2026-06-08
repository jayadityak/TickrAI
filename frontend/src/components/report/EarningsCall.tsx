import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface Props {
  data: any;
}

function toneVariant(tone: string): 'green' | 'red' | 'default' {
  const t = tone?.toLowerCase();
  if (t === 'bullish') return 'green';
  if (t === 'bearish') return 'red';
  return 'default';
}

export default function EarningsCall({ data }: Props) {
  return (
    <Card>
      <h2 className="font-semibold text-lg mb-1">🎙️ Earnings Call</h2>
      <p className="text-xs text-muted mb-4">Most recent quarterly earnings · management tone &amp; guidance</p>

      {data.summary && (
        <p className="text-muted leading-relaxed">{data.summary}</p>
      )}

      {data.management_tone && (
        <div className="mt-3">
          <Badge variant={toneVariant(data.management_tone)}>
            {data.management_tone}
          </Badge>
        </div>
      )}

      {Array.isArray(data.key_themes) && data.key_themes.length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2">Key Themes</h3>
          <ul className="list-disc list-inside text-muted text-sm space-y-1">
            {data.key_themes.map((theme: string, i: number) => (
              <li key={i}>{theme}</li>
            ))}
          </ul>
        </>
      )}

      {data.guidance && (
        <>
          <h3 className="font-medium mt-6 mb-2">Forward Guidance</h3>
          {typeof data.guidance === 'string' ? (
            <p className="text-muted text-sm leading-relaxed">
              {data.guidance}
            </p>
          ) : (
            <div className="text-muted text-sm leading-relaxed space-y-1">
              {data.guidance.revenue && (
                <p>
                  <span className="font-medium">Revenue:</span>{' '}
                  {data.guidance.revenue}
                </p>
              )}
              {data.guidance.earnings && (
                <p>
                  <span className="font-medium">Earnings:</span>{' '}
                  {data.guidance.earnings}
                </p>
              )}
              {data.guidance.outlook && (
                <p>
                  <span className="font-medium">Outlook:</span>{' '}
                  {data.guidance.outlook}
                </p>
              )}
            </div>
          )}
        </>
      )}

      {Array.isArray(data.analyst_concerns) &&
        data.analyst_concerns.length > 0 && (
          <>
            <h3 className="font-medium mt-6 mb-2">Analyst Concerns</h3>
            <ul className="list-disc list-inside text-amber text-sm space-y-1">
              {data.analyst_concerns.map((concern: string, i: number) => (
                <li key={i}>{concern}</li>
              ))}
            </ul>
          </>
        )}

      {data.forward_outlook && (
        <>
          <h3 className="font-medium mt-6 mb-2">Outlook</h3>
          <p className="text-muted leading-relaxed">{data.forward_outlook}</p>
        </>
      )}
    </Card>
  );
}

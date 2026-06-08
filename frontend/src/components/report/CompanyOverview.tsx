import Card from '../ui/Card';

interface Props {
  data: any;
}

export default function CompanyOverview({ data }: Props) {
  const segments: any[] = Array.isArray(data.revenue_segments) ? data.revenue_segments : [];
  const products: string[] = Array.isArray(data.key_products) ? data.key_products : [];

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-1">🏢 Company Overview</h2>
      <p className="text-xs text-muted mb-4">Business description &amp; competitive position</p>

      {data.business_description && (
        <p className="text-muted leading-relaxed">{data.business_description}</p>
      )}

      {data.competitive_position && (
        <>
          <h3 className="font-medium mt-5 mb-2 text-sm">Competitive Position</h3>
          <p className="text-sm text-muted leading-relaxed">{data.competitive_position}</p>
        </>
      )}

      {data.management_highlights && (
        <>
          <h3 className="font-medium mt-5 mb-2 text-sm">Management</h3>
          <p className="text-sm text-muted leading-relaxed">{data.management_highlights}</p>
        </>
      )}

      {products.length > 0 && (
        <>
          <h3 className="font-medium mt-5 mb-2 text-sm">Key Products &amp; Services</h3>
          <ul className="list-disc list-inside text-muted text-sm space-y-1">
            {products.map((product: string, i: number) => (
              <li key={i}>{product}</li>
            ))}
          </ul>
        </>
      )}

      {segments.length > 0 && (
        <>
          <h3 className="font-medium mt-5 mb-2 text-sm">Revenue Segments</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
            {segments.map(
              (segment: { name: string; description: string; revenue?: string }, i: number) => (
                <div key={i} className="bg-surface rounded-[8px] p-3">
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-sm">{segment.name}</div>
                    {segment.revenue && (
                      <div className="text-xs text-accent font-medium">{segment.revenue}</div>
                    )}
                  </div>
                  {segment.description && (
                    <div className="text-xs text-muted mt-1">{segment.description}</div>
                  )}
                </div>
              ),
            )}
          </div>
        </>
      )}

      <div className="flex flex-wrap gap-4 mt-5 pt-4 border-t border-border">
        {data.headquarters && (
          <p className="text-sm text-muted">
            <span className="font-medium text-fg">HQ:</span>{' '}
            {data.headquarters}
          </p>
        )}
        {data.employee_count && (
          <p className="text-sm text-muted">
            <span className="font-medium text-fg">Employees:</span>{' '}
            {typeof data.employee_count === 'number'
              ? data.employee_count.toLocaleString()
              : data.employee_count}
          </p>
        )}
        {data.founded && (
          <p className="text-sm text-muted">
            <span className="font-medium text-fg">Founded:</span> {data.founded}
          </p>
        )}
      </div>
    </Card>
  );
}

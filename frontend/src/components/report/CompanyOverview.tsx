import Card from '../ui/Card';

interface Props {
  data: any;
}

export default function CompanyOverview({ data }: Props) {
  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4">🏢 Company Overview</h2>

      {data.business_description && (
        <p className="text-muted leading-relaxed">{data.business_description}</p>
      )}

      {data.key_products && data.key_products.length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2">Key Products & Services</h3>
          <ul className="list-disc list-inside text-muted text-sm space-y-1">
            {data.key_products.map((product: string, i: number) => (
              <li key={i}>{product}</li>
            ))}
          </ul>
        </>
      )}

      {data.revenue_segments && data.revenue_segments.length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2">Revenue Segments</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
            {data.revenue_segments.map(
              (segment: { name: string; description: string }, i: number) => (
                <div key={i} className="bg-surface rounded-[8px] p-3">
                  <div className="font-medium text-sm">{segment.name}</div>
                  <div className="text-xs text-muted">{segment.description}</div>
                </div>
              ),
            )}
          </div>
        </>
      )}

      {data.headquarters && (
        <p className="text-sm text-muted mt-4">
          <span className="font-medium">Headquarters:</span> {data.headquarters}
        </p>
      )}

      {data.employee_count && (
        <p className="text-sm text-muted mt-1">
          <span className="font-medium">Employees:</span>{' '}
          {typeof data.employee_count === 'number'
            ? data.employee_count.toLocaleString()
            : data.employee_count}
        </p>
      )}
    </Card>
  );
}

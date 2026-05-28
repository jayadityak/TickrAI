import Card from '../ui/Card';

interface Props {
  data: any;
}

function displayValue(value: any): string {
  if (value == null) return 'N/A';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return value.toLocaleString();
  return String(value);
}

export default function FinancialAnalysis({ data }: Props) {
  const metricKeys = [
    { key: 'pe_ratio', label: 'P/E Ratio' },
    { key: 'market_cap', label: 'Market Cap' },
    { key: 'price_to_book', label: 'Price to Book' },
    { key: 'dividend_yield', label: 'Dividend Yield' },
  ];

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4">📊 Financial Analysis</h2>

      {data.summary && (
        <p className="text-muted leading-relaxed">{data.summary}</p>
      )}

      {data.key_metrics && (
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-3 sm:gap-4 mt-4">
          {metricKeys.map(({ key, label }) => {
            const value = data.key_metrics[key];
            if (value == null) return null;
            return (
              <div key={key} className="bg-surface rounded-[8px] px-3 sm:px-4 py-2 sm:py-3">
                <div className="text-xs text-muted uppercase">{label}</div>
                <div className="text-base sm:text-lg font-bold">{displayValue(value)}</div>
              </div>
            );
          })}
        </div>
      )}

      {Array.isArray(data.annual_trends) && data.annual_trends.length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2">Annual Trends</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 font-medium">Year</th>
                  <th className="text-right py-2 px-2 font-medium">Revenue</th>
                  <th className="text-right py-2 px-2 font-medium">Net Income</th>
                  <th className="text-right py-2 px-2 font-medium">EPS</th>
                  <th className="text-right py-2 px-2 font-medium">EBITDA Margin</th>
                  <th className="text-right py-2 px-2 font-medium">Net Margin</th>
                </tr>
              </thead>
              <tbody>
                {data.annual_trends.map((row: any, i: number) => (
                  <tr key={i} className="even:bg-surface border-b border-border">
                    <td className="py-2 px-2">{displayValue(row.year)}</td>
                    <td className="text-right py-2 px-2">{displayValue(row.revenue)}</td>
                    <td className="text-right py-2 px-2">{displayValue(row.net_income)}</td>
                    <td className="text-right py-2 px-2">{displayValue(row.eps)}</td>
                    <td className="text-right py-2 px-2">{displayValue(row.ebitda_margin)}</td>
                    <td className="text-right py-2 px-2">{displayValue(row.net_margin)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {data.analysis && (
        <>
          <h3 className="font-medium mt-6 mb-2">Analysis</h3>
          <p className="text-muted leading-relaxed">{data.analysis}</p>
        </>
      )}
    </Card>
  );
}

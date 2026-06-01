import Card from '../ui/Card';
import { TrendingUp, TrendingDown, Minus, Target } from 'lucide-react';

interface Props {
  data: any;
}

function displayValue(value: any): string {
  if (value == null) return 'N/A';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return value.toLocaleString();
  return String(value);
}

function BeatIcon({ pct }: { pct: number }) {
  if (pct > 2) return <TrendingUp size={12} className="text-green-500 inline ml-1" />;
  if (pct < -2) return <TrendingDown size={12} className="text-red-500 inline ml-1" />;
  return <Minus size={12} className="text-muted inline ml-1" />;
}

export default function FinancialAnalysis({ data }: Props) {
  const metricKeys = [
    { key: 'pe_ratio', label: 'P/E Ratio' },
    { key: 'market_cap', label: 'Market Cap' },
    { key: 'price_to_book', label: 'Price to Book' },
    { key: 'dividend_yield', label: 'Dividend Yield' },
  ];

  const qualityKeys = [
    { key: 'roe', label: 'Return on Equity' },
    { key: 'roic', label: 'ROIC' },
    { key: 'fcf_yield', label: 'FCF Yield' },
    { key: 'net_debt_ebitda', label: 'Net Debt / EBITDA' },
    { key: 'graham_number', label: 'Graham Number' },
    { key: 'graham_upside', label: 'vs Graham Value' },
  ];

  const pt = data.price_target;
  const surprises: any[] = data.earnings_surprises || [];
  const quality = data.quality_metrics || {};

  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4">📊 Financial Analysis</h2>

      {data.summary && (
        <p className="text-muted leading-relaxed">{data.summary}</p>
      )}

      {/* Core Key Metrics */}
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

      {/* Analyst Price Target */}
      {pt && pt.target_consensus != null && (
        <div className="mt-5 p-4 bg-surface rounded-[8px] border border-border">
          <div className="flex items-center gap-2 mb-3">
            <Target size={15} className="text-accent" />
            <span className="font-medium text-sm">Analyst Price Target Consensus</span>
            {pt.upside_pct != null && (
              <span className={`ml-auto text-sm font-bold ${pt.upside_pct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {pt.upside_pct >= 0 ? '+' : ''}{pt.upside_pct}% upside
              </span>
            )}
          </div>
          <div className="flex gap-4 text-sm flex-wrap">
            {pt.target_low != null && (
              <span><span className="text-muted">Bear: </span><span className="font-medium">${pt.target_low}</span></span>
            )}
            {pt.target_median != null && (
              <span><span className="text-muted">Median: </span><span className="font-bold">${pt.target_median}</span></span>
            )}
            {pt.target_consensus != null && (
              <span><span className="text-muted">Consensus: </span><span className="font-medium">${pt.target_consensus}</span></span>
            )}
            {pt.target_high != null && (
              <span><span className="text-muted">Bull: </span><span className="font-medium">${pt.target_high}</span></span>
            )}
          </div>
        </div>
      )}

      {/* Quality Metrics */}
      {Object.keys(quality).length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2 text-sm uppercase text-muted tracking-wide">Quality & Value Signals</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {qualityKeys.map(({ key, label }) => {
              const value = quality[key];
              if (value == null) return null;
              const isUpside = key === 'graham_upside';
              const isPositive = isUpside && value.startsWith('+');
              const isNegative = isUpside && value.startsWith('-');
              return (
                <div key={key} className="bg-surface rounded-[8px] px-3 py-2">
                  <div className="text-xs text-muted">{label}</div>
                  <div className={`text-sm font-bold mt-0.5 ${isPositive ? 'text-green-500' : isNegative ? 'text-red-500' : ''}`}>
                    {value}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Earnings Surprises */}
      {surprises.length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2 text-sm uppercase text-muted tracking-wide">Recent EPS Surprises</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 font-medium text-muted">Quarter</th>
                  <th className="text-right py-2 px-2 font-medium text-muted">Estimated</th>
                  <th className="text-right py-2 px-2 font-medium text-muted">Actual</th>
                  <th className="text-right py-2 px-2 font-medium text-muted">Surprise</th>
                </tr>
              </thead>
              <tbody>
                {surprises.map((row: any, i: number) => (
                  <tr key={i} className="even:bg-surface border-b border-border">
                    <td className="py-2 px-2 text-muted">{row.date}</td>
                    <td className="text-right py-2 px-2">${row.eps_estimated?.toFixed(2) ?? 'N/A'}</td>
                    <td className="text-right py-2 px-2 font-medium">${row.eps_actual?.toFixed(2) ?? 'N/A'}</td>
                    <td className={`text-right py-2 px-2 font-bold ${row.beat_pct > 2 ? 'text-green-500' : row.beat_pct < -2 ? 'text-red-500' : 'text-muted'}`}>
                      {row.beat_pct > 0 ? '+' : ''}{row.beat_pct}%
                      <BeatIcon pct={row.beat_pct} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Annual Trends */}
      {Array.isArray(data.annual_trends) && data.annual_trends.length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2 text-sm uppercase text-muted tracking-wide">Annual Trends</h3>
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

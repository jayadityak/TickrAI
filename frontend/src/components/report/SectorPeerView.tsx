import Card from '../ui/Card';

interface Props {
  data: any;
}

function display(value: any): string {
  if (value == null) return '—';
  return String(value);
}

export default function SectorPeerView({ data }: Props) {
  return (
    <Card>
      <h2 className="font-semibold text-lg mb-4">📈 Sector & Peers</h2>

      {data.sector_overview && (
        <p className="text-muted leading-relaxed">{data.sector_overview}</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
        {Array.isArray(data.tailwinds) && data.tailwinds.length > 0 && (
          <div className="border-l-4 border-green pl-3">
            <h3 className="font-medium mb-2">Tailwinds</h3>
            <ul className="space-y-1">
              {data.tailwinds.map((item: string, i: number) => (
                <li key={i} className="text-sm text-muted">{item}</li>
              ))}
            </ul>
          </div>
        )}

        {Array.isArray(data.headwinds) && data.headwinds.length > 0 && (
          <div className="border-l-4 border-red pl-3">
            <h3 className="font-medium mb-2">Headwinds</h3>
            <ul className="space-y-1">
              {data.headwinds.map((item: string, i: number) => (
                <li key={i} className="text-sm text-muted">{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {Array.isArray(data.peer_comparison) && data.peer_comparison.length > 0 && (
        <>
          <h3 className="font-medium mt-6 mb-2">Peer Comparison</h3>
          <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
            <table className="w-full text-sm min-w-[500px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 font-medium whitespace-nowrap">Company</th>
                  <th className="text-right py-2 px-2 font-medium whitespace-nowrap">Market Cap</th>
                  <th className="text-right py-2 px-2 font-medium whitespace-nowrap">P/E</th>
                  <th className="text-right py-2 px-2 font-medium whitespace-nowrap">Rev Growth</th>
                  <th className="text-right py-2 px-2 font-medium whitespace-nowrap">Margin</th>
                  <th className="text-left py-2 px-2 font-medium whitespace-nowrap">Assessment</th>
                </tr>
              </thead>
              <tbody>
                {data.peer_comparison.map((peer: any, i: number) => (
                  <tr key={i} className="even:bg-surface border-b border-border">
                    <td className="py-2 px-2 font-medium">
                      {peer.symbol || peer.company_name || peer.company || '—'}
                    </td>
                    <td className="text-right py-2 px-2">{display(peer.market_cap)}</td>
                    <td className="text-right py-2 px-2">{display(peer.pe_ratio || peer.pe)}</td>
                    <td className="text-right py-2 px-2">{display(peer.revenue_growth)}</td>
                    <td className="text-right py-2 px-2">{display(peer.margin)}</td>
                    <td className="text-left py-2 px-2 text-xs text-muted">{display(peer.assessment)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {data.relative_valuation && (
        <>
          <h3 className="font-medium mt-6 mb-2">Relative Valuation</h3>
          <p className="text-muted leading-relaxed">{data.relative_valuation}</p>
        </>
      )}
    </Card>
  );
}

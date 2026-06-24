import { useState, useEffect } from 'react';
import axios from 'axios';

interface MacroMarket {
  label: string;
  probability: number;
  url: string;
}

export default function MacroSignals() {
  const [markets, setMarkets] = useState<MacroMarket[]>([]);

  useEffect(() => {
    axios.get('/api/kalshi/macro')
      .then(res => setMarkets(res.data?.markets ?? []))
      .catch(() => {});
  }, []);

  if (markets.length === 0) return null;

  return (
    <section className="py-4 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted font-semibold uppercase tracking-wider shrink-0">
            Market Signals
          </span>
          {markets.map((m) => {
            const color =
              m.probability >= 60 ? 'text-green border-green/30 bg-green/5' :
              m.probability <= 40 ? 'text-red border-red/30 bg-red/5' :
              'text-amber border-amber/30 bg-amber/5';

            return (
              <a
                key={m.label}
                href={m.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-medium hover:opacity-80 transition-opacity ${color}`}
              >
                <span className="font-bold">{m.probability}%</span>
                <span className="opacity-70">{m.label}</span>
              </a>
            );
          })}
          <span className="text-xs text-muted opacity-50 ml-1">via Kalshi</span>
        </div>
      </div>
    </section>
  );
}

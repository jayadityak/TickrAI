import { useState, useEffect } from 'react';
import axios from 'axios';

interface KalshiMarket {
  probability: number;
  title: string;
  close_time?: string;
  volume?: number;
  url: string;
}

export default function KalshiEarningsBadge({ ticker }: { ticker: string }) {
  const [market, setMarket] = useState<KalshiMarket | null>(null);

  useEffect(() => {
    axios.get(`/api/kalshi/earnings/${ticker}`)
      .then(res => setMarket(res.data?.market ?? null))
      .catch(() => {});
  }, [ticker]);

  if (!market) return null;

  const { probability, title, url, volume } = market;

  const color =
    probability >= 60 ? 'text-green bg-green/10 border-green/20' :
    probability <= 40 ? 'text-red bg-red/10 border-red/20' :
    'text-amber bg-amber/10 border-amber/20';

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium transition-opacity hover:opacity-80 ${color}`}
      title={title}
    >
      <span className="font-bold">{probability}%</span>
      <span className="opacity-80">earnings beat</span>
      {volume != null && volume > 0 && (
        <span className="opacity-50">· {volume.toLocaleString()} contracts</span>
      )}
      <span className="opacity-50">Kalshi ↗</span>
    </a>
  );
}

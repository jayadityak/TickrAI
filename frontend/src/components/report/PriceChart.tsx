import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import axios from 'axios';
import Card from '../ui/Card';
import { useTheme } from '../../contexts/ThemeContext';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const RANGES = ['1D', '1W', '1M', '3M', '6M', '1Y', '5Y'];

function formatDate(date: string, range: string): string {
  const d = new Date(date);
  if (range === '1D' || range === '1W') {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  if (range === '5Y' || range === 'MAX') {
    return d.toLocaleDateString([], { month: 'short', year: '2-digit' });
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

function formatVolume(vol: number): string {
  if (vol >= 1e9) return `${(vol / 1e9).toFixed(1)}B`;
  if (vol >= 1e6) return `${(vol / 1e6).toFixed(1)}M`;
  if (vol >= 1e3) return `${(vol / 1e3).toFixed(0)}K`;
  return vol.toString();
}

export default function PriceChart({ ticker }: { ticker: string }) {
  const [range, setRange] = useState('1Y');
  const [data, setData] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const { isDark } = useTheme();
  const tickColor = isDark ? '#9a9591' : '#78716c';

  useEffect(() => {
    const fetchChart = async () => {
      setLoading(true);
      setUnavailable(false);
      try {
        const res = await axios.get(`/api/chart/${ticker}?range=${range}`);
        setData(res.data.data || []);
        if (res.data.unavailable) setUnavailable(true);
      } catch {
        setData([]);
      } finally {
        setLoading(false);
      }
    };
    fetchChart();
  }, [ticker, range]);

  const firstPrice = data.length > 0 ? data[0].close : 0;
  const lastPrice = data.length > 0 ? data[data.length - 1].close : 0;
  const priceChange = lastPrice - firstPrice;
  const pctChange = firstPrice ? (priceChange / firstPrice) * 100 : 0;
  const isPositive = priceChange >= 0;
  const chartColor = isPositive ? '#059669' : '#dc2626';

  return (
    <Card>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl sm:text-3xl font-bold">
              {lastPrice ? formatPrice(lastPrice) : '—'}
            </span>
            {data.length > 0 && (
              <span className={`flex items-center gap-1 text-sm font-medium ${isPositive ? 'text-green' : 'text-red'}`}>
                {isPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                {isPositive ? '+' : ''}{formatPrice(priceChange)} ({isPositive ? '+' : ''}{pctChange.toFixed(2)}%)
              </span>
            )}
          </div>
          <p className="text-xs text-muted mt-1">{ticker} · {range} range</p>
        </div>

        {/* Range selector */}
        <div className="flex gap-1 bg-surface rounded-[8px] p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-2.5 sm:px-3 py-1 text-xs sm:text-sm font-medium rounded-[6px] transition-colors cursor-pointer ${
                range === r
                  ? 'bg-accent text-white'
                  : 'text-muted hover:text-fg'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      {loading ? (
        <div className="h-[250px] sm:h-[300px] flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : data.length > 0 ? (
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
            <defs>
              <linearGradient id={`gradient-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chartColor} stopOpacity={0.2} />
                <stop offset="100%" stopColor={chartColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tickFormatter={(d) => formatDate(d, range)}
              tick={{ fontSize: 11, fill: tickColor }}
              axisLine={false}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              domain={['auto', 'auto']}
              tickFormatter={(v) => `$${v}`}
              tick={{ fontSize: 11, fill: tickColor }}
              axisLine={false}
              tickLine={false}
              width={55}
            />
            <Tooltip
              formatter={(value: number) => [formatPrice(value), 'Price']}
              labelFormatter={(label) => {
                const d = new Date(label);
                return d.toLocaleDateString([], {
                  weekday: 'short',
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                });
              }}
              contentStyle={{
                background: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                fontSize: '13px',
                color: 'var(--color-fg)',
              }}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={chartColor}
              strokeWidth={2}
              fill={`url(#gradient-${ticker})`}
              dot={false}
              activeDot={{ r: 4, fill: chartColor }}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-[250px] flex items-center justify-center text-muted text-sm">
          {unavailable
            ? `Price chart unavailable for ${ticker} — this ticker may not be listed on a major exchange`
            : 'No price data available for this range'}
        </div>
      )}

      {/* Volume bar */}
      {data.length > 0 && (
        <p className="text-xs text-muted mt-2">
          Latest volume: {formatVolume(data[data.length - 1].volume)}
        </p>
      )}
    </Card>
  );
}

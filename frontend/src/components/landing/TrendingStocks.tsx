import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, Flame } from 'lucide-react';
import axios from 'axios';

interface TrendingItem {
  ticker: string;
  count: number;
}

export default function TrendingStocks() {
  const [trending, setTrending] = useState<TrendingItem[]>([]);
  const [totalReports, setTotalReports] = useState(0);

  useEffect(() => {
    const fetchTrending = async () => {
      try {
        const res = await axios.get('/api/trending');
        setTrending(res.data.trending);
        setTotalReports(res.data.total_reports_generated);
      } catch {
        // Fail silently — trending is non-critical
      }
    };
    fetchTrending();
  }, []);

  if (trending.length === 0) return null;

  return (
    <section className="py-8 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-2 mb-4">
          <Flame size={20} className="text-accent" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Trending Today
          </h3>
          <span className="text-xs text-muted bg-surface px-2 py-0.5 rounded-full">
            {totalReports.toLocaleString()} reports generated
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {trending.map((item, i) => (
            <Link
              key={item.ticker}
              to={`/report/${item.ticker}`}
              className="group flex items-center gap-2 px-4 py-2 rounded-full border border-border hover:border-accent hover:bg-accent-light transition-all"
            >
              <span className={`text-xs font-bold ${i < 3 ? 'text-accent' : 'text-muted'}`}>
                #{i + 1}
              </span>
              <span className="font-semibold text-sm text-fg group-hover:text-accent transition-colors">
                {item.ticker}
              </span>
              <span className="flex items-center gap-0.5 text-xs text-muted">
                <TrendingUp size={12} />
                {item.count}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

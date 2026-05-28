import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Search, Star, TrendingUp, TrendingDown, X } from 'lucide-react';
import axios from 'axios';
import AuthGate from '../components/auth/AuthGate';
import { useAuth } from '../contexts/AuthContext';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';

interface WatchlistItem {
  ticker: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  positive: boolean;
}

function DashboardContent() {
  const { user } = useAuth();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWatchlist = async () => {
      const token = localStorage.getItem('valyu_token');
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await axios.get('/api/watchlist', {
          headers: { Authorization: `Bearer ${token}` },
        });
        setWatchlist(res.data.watchlist);
      } catch {
        // Fail silently
      } finally {
        setLoading(false);
      }
    };
    fetchWatchlist();
  }, []);

  const removeFromWatchlist = async (ticker: string) => {
    const token = localStorage.getItem('valyu_token');
    if (!token) return;
    try {
      await axios.delete(`/api/watchlist/${ticker}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setWatchlist((prev) => prev.filter((w) => w.ticker !== ticker));
    } catch {
      // Fail silently
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        {user?.picture ? (
          <img
            src={user.picture}
            alt={user.name}
            className="w-14 h-14 rounded-full"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="w-14 h-14 rounded-full bg-accent text-white flex items-center justify-center text-xl font-medium">
            {user?.name?.[0]?.toUpperCase() || 'U'}
          </div>
        )}
        <div>
          <h1 className="text-2xl font-bold">{user?.name}</h1>
          <p className="text-muted text-sm">{user?.email}</p>
        </div>
      </div>

      {/* Watchlist */}
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Star size={20} className="text-amber" />
        Watchlist
      </h2>

      {loading ? (
        <Card>
          <div className="animate-pulse space-y-3">
            <div className="h-10 bg-surface2 rounded" />
            <div className="h-10 bg-surface2 rounded" />
            <div className="h-10 bg-surface2 rounded" />
          </div>
        </Card>
      ) : watchlist.length > 0 ? (
        <Card className="mb-8">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-2 pr-3 text-muted font-medium">Ticker</th>
                  <th className="py-2 pr-3 text-muted font-medium text-right">Price</th>
                  <th className="py-2 pr-3 text-muted font-medium text-right">Change</th>
                  <th className="py-2 pr-3 text-muted font-medium text-right">% Change</th>
                  <th className="py-2 text-muted font-medium text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map((item) => (
                  <tr key={item.ticker} className="border-b border-border/50 hover:bg-surface transition-colors">
                    <td className="py-3 pr-3">
                      <Link
                        to={`/report/${item.ticker}`}
                        className="font-bold text-accent hover:underline"
                      >
                        {item.ticker}
                      </Link>
                    </td>
                    <td className="py-3 pr-3 text-right tabular-nums font-medium">
                      {item.price ? `$${item.price.toFixed(2)}` : '—'}
                    </td>
                    <td className={`py-3 pr-3 text-right tabular-nums ${item.positive ? 'text-green' : 'text-red'}`}>
                      <span className="flex items-center justify-end gap-1">
                        {item.positive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                        {item.change !== null ? `$${Math.abs(item.change).toFixed(2)}` : '—'}
                      </span>
                    </td>
                    <td className={`py-3 pr-3 text-right tabular-nums font-medium ${item.positive ? 'text-green' : 'text-red'}`}>
                      {item.change_pct !== null ? `${item.change_pct >= 0 ? '+' : ''}${item.change_pct.toFixed(2)}%` : '—'}
                    </td>
                    <td className="py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <Link to={`/report/${item.ticker}`}>
                          <Button variant="secondary" size="sm">
                            <FileText size={14} />
                          </Button>
                        </Link>
                        <button
                          onClick={() => removeFromWatchlist(item.ticker)}
                          className="p-1.5 rounded-[6px] text-muted hover:text-red hover:bg-red/10 transition-colors cursor-pointer"
                          title="Remove from watchlist"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card className="text-center py-8 mb-8">
          <Star size={32} className="text-muted mx-auto mb-3" />
          <h3 className="font-semibold mb-1">No watchlist items</h3>
          <p className="text-muted text-sm">
            Click the star icon on any report to add it to your watchlist.
          </p>
        </Card>
      )}

      {/* Recent Reports — placeholder */}
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FileText size={20} />
        Recent Reports
      </h2>

      <Card className="text-center py-12">
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 rounded-full bg-surface2 flex items-center justify-center">
            <Search size={32} className="text-muted" />
          </div>
        </div>
        <h3 className="text-lg font-semibold mb-2">No reports yet</h3>
        <p className="text-muted text-sm mb-6">
          Search for a company to generate your first AI research report.
        </p>
        <Link to="/">
          <Button>Start Researching</Button>
        </Link>
      </Card>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGate message="Sign in to view your dashboard and watchlist">
      <DashboardContent />
    </AuthGate>
  );
}

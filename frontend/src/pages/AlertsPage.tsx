import { useState, useEffect, useCallback } from 'react';
import { Bell, BellRing, Plus, Trash2, TrendingUp, TrendingDown, X } from 'lucide-react';
import axios from 'axios';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import AuthGate from '../components/auth/AuthGate';

interface Alert {
  id: string;
  ticker: string;
  target_price: number;
  direction: 'above' | 'below';
  created_at: number;
  triggered: boolean;
  triggered_at: number | null;
  current_price: number | null;
}

function formatPrice(p: number): string {
  return `$${p.toFixed(2)}`;
}

function timeAgo(ts: number): string {
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function AlertsContent() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [ticker, setTicker] = useState('');
  const [targetPrice, setTargetPrice] = useState('');
  const [direction, setDirection] = useState<'above' | 'below'>('above');
  const [creating, setCreating] = useState(false);

  const token = localStorage.getItem('valyu_token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await axios.get('/api/alerts', { headers });
      setAlerts(res.data.alerts);
    } catch {
      // fail silently
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
    // Poll every 60 seconds for price updates
    const interval = setInterval(fetchAlerts, 60000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const createAlert = async () => {
    if (!ticker.trim() || !targetPrice.trim()) return;
    setCreating(true);
    try {
      await axios.post(
        '/api/alerts',
        {
          ticker: ticker.trim().toUpperCase(),
          target_price: parseFloat(targetPrice),
          direction,
        },
        { headers },
      );
      setTicker('');
      setTargetPrice('');
      setShowForm(false);
      await fetchAlerts();
    } catch {
      // fail silently
    } finally {
      setCreating(false);
    }
  };

  const deleteAlert = async (id: string) => {
    try {
      await axios.delete(`/api/alerts/${id}`, { headers });
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // fail silently
    }
  };

  const active = alerts.filter((a) => !a.triggered);
  const triggered = alerts.filter((a) => a.triggered);

  return (
    <div className="max-w-3xl mx-auto px-3 sm:px-4 py-6 sm:py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bell size={24} className="text-accent" />
          Price Alerts
        </h1>
        <Button onClick={() => setShowForm(!showForm)} size="sm">
          <span className="flex items-center gap-1.5">
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'New Alert'}
          </span>
        </Button>
      </div>

      {/* Create Alert Form */}
      {showForm && (
        <Card className="mb-6">
          <h3 className="font-medium text-sm mb-3">Create Price Alert</h3>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="Ticker (e.g. AAPL)"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="flex-1 px-3 py-2 rounded-[8px] border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
            />
            <div className="flex gap-2">
              <button
                onClick={() => setDirection('above')}
                className={`px-3 py-2 rounded-[8px] text-sm font-medium transition-colors cursor-pointer ${
                  direction === 'above'
                    ? 'bg-green/15 text-green border border-green/30'
                    : 'bg-surface text-muted border border-border'
                }`}
              >
                <TrendingUp size={14} className="inline mr-1" />
                Above
              </button>
              <button
                onClick={() => setDirection('below')}
                className={`px-3 py-2 rounded-[8px] text-sm font-medium transition-colors cursor-pointer ${
                  direction === 'below'
                    ? 'bg-red/15 text-red border border-red/30'
                    : 'bg-surface text-muted border border-border'
                }`}
              >
                <TrendingDown size={14} className="inline mr-1" />
                Below
              </button>
            </div>
            <input
              type="number"
              step="0.01"
              placeholder="Target price"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              className="w-full sm:w-32 px-3 py-2 rounded-[8px] border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
            />
            <Button onClick={createAlert} disabled={creating} size="sm">
              {creating ? 'Creating...' : 'Set Alert'}
            </Button>
          </div>
          <p className="text-xs text-muted mt-2">
            You&apos;ll be alerted when {ticker || 'TICKER'} goes{' '}
            {direction} {targetPrice ? formatPrice(parseFloat(targetPrice)) : '$0.00'}
          </p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-surface2 rounded w-full" />
            <div className="h-4 bg-surface2 rounded w-3/4" />
            <div className="h-12 bg-surface2 rounded" />
          </div>
        </Card>
      ) : alerts.length === 0 ? (
        <Card>
          <div className="text-center py-8">
            <Bell size={40} className="mx-auto text-muted mb-3 opacity-50" />
            <h3 className="font-medium text-lg mb-1">No alerts yet</h3>
            <p className="text-sm text-muted">
              Set price alerts to track when stocks hit your target prices.
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Active Alerts */}
          {active.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-muted mb-2 flex items-center gap-1.5">
                <Bell size={14} />
                Active ({active.length})
              </h3>
              <div className="space-y-2">
                {active.map((alert) => {
                  const distance =
                    alert.current_price !== null
                      ? ((alert.target_price - alert.current_price) / alert.current_price) * 100
                      : null;

                  return (
                    <Card key={alert.id} className="!p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <span className="font-bold text-sm">{alert.ticker}</span>
                          <Badge variant={alert.direction === 'above' ? 'green' : 'red'}>
                            {alert.direction === 'above' ? '↑' : '↓'} {formatPrice(alert.target_price)}
                          </Badge>
                          {alert.current_price !== null && (
                            <span className="text-xs text-muted hidden sm:inline">
                              Now: {formatPrice(alert.current_price)}
                              {distance !== null && (
                                <span className={distance > 0 ? 'text-green ml-1' : 'text-red ml-1'}>
                                  ({distance > 0 ? '+' : ''}{distance.toFixed(1)}% away)
                                </span>
                              )}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-xs text-muted hidden sm:inline">
                            {timeAgo(alert.created_at)}
                          </span>
                          <button
                            onClick={() => deleteAlert(alert.id)}
                            className="text-muted hover:text-red transition-colors cursor-pointer"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Triggered Alerts */}
          {triggered.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-muted mb-2 flex items-center gap-1.5">
                <BellRing size={14} className="text-amber-500" />
                Triggered ({triggered.length})
              </h3>
              <div className="space-y-2">
                {triggered.map((alert) => (
                  <Card key={alert.id} className="!p-3 border-amber-200 bg-amber-50/50">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <span className="font-bold text-sm">{alert.ticker}</span>
                        <Badge variant="amber">
                          {alert.direction === 'above' ? '↑' : '↓'} {formatPrice(alert.target_price)} — Triggered!
                        </Badge>
                        {alert.current_price !== null && (
                          <span className="text-xs text-muted hidden sm:inline">
                            Now: {formatPrice(alert.current_price)}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {alert.triggered_at && (
                          <span className="text-xs text-muted hidden sm:inline">
                            {timeAgo(alert.triggered_at)}
                          </span>
                        )}
                        <button
                          onClick={() => deleteAlert(alert.id)}
                          className="text-muted hover:text-red transition-colors cursor-pointer"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-muted mt-6 text-center">
        Prices update every 60 seconds. Alerts are checked when you visit this page.
      </p>
    </div>
  );
}

export default function AlertsPage() {
  return (
    <AuthGate message="Sign in to set price alerts">
      <AlertsContent />
    </AuthGate>
  );
}

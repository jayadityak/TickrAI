import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { Compass, LogOut, Menu, Moon, Sun, User, BarChart3, Bell, X } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import axios from 'axios';

interface MarketIndex {
  name: string;
  value: string;
  change: string;
  positive: boolean;
}

const FALLBACK_DATA: MarketIndex[] = [
  { name: 'S&P 500', value: '—', change: '—', positive: true },
  { name: 'NASDAQ', value: '—', change: '—', positive: true },
  { name: 'DOW', value: '—', change: '—', positive: true },
];

export default function Navbar() {
  const { user, login, logout } = useAuth();
  const { isDark, toggle: toggleTheme } = useTheme();
  const [showDropdown, setShowDropdown] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [marketData, setMarketData] = useState<MarketIndex[]>(FALLBACK_DATA);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch live market data on mount and every 5 minutes
  useEffect(() => {
    const fetchMarket = async () => {
      try {
        const res = await axios.get('/api/market/indices');
        setMarketData(res.data);
      } catch {
        // Keep fallback data
      }
    };
    fetchMarket();
    const interval = setInterval(fetchMarket, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleGoogleSuccess = async (response: { credential?: string }) => {
    if (response.credential) {
      try {
        await login(response.credential);
      } catch (err) {
        console.error('Login failed:', err);
      }
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-card border-b border-border print:hidden">
      <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-16">
        {/* Left: Logo */}
        <Link to="/" className="flex items-center gap-3">
          <span className="font-serif italic text-2xl text-accent">TickrAI</span>
          <span className="text-xs tracking-widest text-muted uppercase">
            / EQUITY RESEARCH
          </span>
        </Link>

        {/* Center: Live ticker bar */}
        <div className="hidden md:flex items-center gap-6">
          {marketData.map((item) => (
            <div key={item.name} className="flex items-center gap-2 text-sm">
              <span className="text-muted font-medium">{item.name}</span>
              <span className="text-fg">{item.value}</span>
              <span className={item.positive ? 'text-green' : 'text-red'}>
                {item.change}
              </span>
            </div>
          ))}
        </div>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-4">
          <Link
            to="/discover"
            className="flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors"
          >
            <Compass size={16} />
            Discover
          </Link>
          <Link
            to="/compare"
            className="flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors"
          >
            <BarChart3 size={16} />
            Compare
          </Link>
          <Link
            to="/alerts"
            className="flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors"
          >
            <Bell size={16} />
            Alerts
          </Link>
        </div>

        {/* Dark / light mode toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-[8px] text-muted hover:text-accent hover:bg-surface transition-colors cursor-pointer"
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          title={isDark ? 'Light mode' : 'Dark mode'}
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Mobile hamburger — shown only when logged out (logged-in users have avatar dropdown) */}
        {!user && (
          <button
            onClick={() => setShowMobileMenu((prev) => !prev)}
            className="md:hidden p-2 rounded-[8px] text-muted hover:text-accent hover:bg-surface transition-colors cursor-pointer"
            aria-label="Toggle menu"
          >
            {showMobileMenu ? <X size={20} /> : <Menu size={20} />}
          </button>
        )}

        {/* Right: Auth */}
        {user ? (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center gap-2 rounded-full hover:bg-surface transition-colors p-1 pr-3 cursor-pointer"
            >
              {user.picture ? (
                <img
                  src={user.picture}
                  alt={user.name}
                  className="w-8 h-8 rounded-full"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center text-sm font-medium">
                  {user.name?.[0]?.toUpperCase() || 'U'}
                </div>
              )}
              <span className="text-sm font-medium text-fg hidden sm:inline">
                {user.name?.split(' ')[0]}
              </span>
            </button>

            {showDropdown && (
              <div className="absolute right-0 mt-2 w-56 bg-card border border-border rounded-[12px] shadow-lg overflow-hidden z-50">
                <div className="px-4 py-3 border-b border-border">
                  <p className="text-sm font-medium text-fg">{user.name}</p>
                  <p className="text-xs text-muted truncate">{user.email}</p>
                </div>
                <Link
                  to="/dashboard"
                  className="flex items-center gap-2 px-4 py-2.5 text-sm text-fg hover:bg-surface transition-colors"
                  onClick={() => setShowDropdown(false)}
                >
                  <User size={16} />
                  My Reports
                </Link>
                <Link
                  to="/discover"
                  className="flex items-center gap-2 px-4 py-2.5 text-sm text-fg hover:bg-surface transition-colors"
                  onClick={() => setShowDropdown(false)}
                >
                  <Compass size={16} />
                  Discover
                </Link>
                <Link
                  to="/compare"
                  className="flex md:hidden items-center gap-2 px-4 py-2.5 text-sm text-fg hover:bg-surface transition-colors"
                  onClick={() => setShowDropdown(false)}
                >
                  <BarChart3 size={16} />
                  Compare
                </Link>
                <Link
                  to="/alerts"
                  className="flex items-center gap-2 px-4 py-2.5 text-sm text-fg hover:bg-surface transition-colors"
                  onClick={() => setShowDropdown(false)}
                >
                  <Bell size={16} />
                  Price Alerts
                </Link>
                <button
                  onClick={() => {
                    logout();
                    setShowDropdown(false);
                  }}
                  className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-red hover:bg-surface transition-colors cursor-pointer"
                >
                  <LogOut size={16} />
                  Sign Out
                </button>
              </div>
            )}
          </div>
        ) : (
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={() => console.error('Google login error')}
            size="medium"
            theme="outline"
            shape="pill"
            text="signin_with"
          />
        )}
      </div>

      {/* Mobile menu drawer — shown for logged-out users on small screens */}
      {!user && showMobileMenu && (
        <div className="md:hidden border-t border-border bg-card print:hidden">
          <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-1">
            <Link
              to="/discover"
              className="flex items-center gap-2 px-3 py-2.5 rounded-[8px] text-sm text-fg hover:bg-surface transition-colors"
              onClick={() => setShowMobileMenu(false)}
            >
              <Compass size={16} className="text-muted" />
              Discover Stocks
            </Link>
            <Link
              to="/compare"
              className="flex items-center gap-2 px-3 py-2.5 rounded-[8px] text-sm text-fg hover:bg-surface transition-colors"
              onClick={() => setShowMobileMenu(false)}
            >
              <BarChart3 size={16} className="text-muted" />
              Compare Companies
            </Link>
            <Link
              to="/alerts"
              className="flex items-center gap-2 px-3 py-2.5 rounded-[8px] text-sm text-fg hover:bg-surface transition-colors"
              onClick={() => setShowMobileMenu(false)}
            >
              <Bell size={16} className="text-muted" />
              Price Alerts
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}

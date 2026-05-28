import { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';

interface SearchResult {
  symbol: string;
  company_name: string;
  exchange: string;
}

interface TickerSearchProps {
  /** If provided, calls this instead of navigating to /report/:ticker */
  onSelect?: (ticker: string) => void;
  placeholder?: string;
}

export default function TickerSearch({ onSelect, placeholder }: TickerSearchProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  const fetchResults = useCallback(async (q: string) => {
    if (q.length === 0) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchResults(query), 200);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, fetchResults]);

  function handleBlur() {
    timeoutRef.current = setTimeout(() => setIsOpen(false), 200);
  }

  function handleFocus() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (query.length > 0) setIsOpen(true);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value);
    setIsOpen(e.target.value.length > 0);
  }

  function handleSelect(symbol: string) {
    setQuery('');
    setIsOpen(false);
    if (onSelect) {
      onSelect(symbol);
    } else {
      navigate(`/report/${symbol}`);
    }
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
        <input
          type="text"
          value={query}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder={placeholder || "Search by company name or symbol, e.g. AAPL"}
          className="w-full pl-10 sm:pl-12 pr-4 sm:pr-5 py-3 sm:py-4 text-base sm:text-lg rounded-[12px] border-2 border-border focus:border-accent focus:outline-none transition-colors bg-card shadow-sm"
        />
      </div>

      {isOpen && query.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-card border border-border rounded-[12px] shadow-lg overflow-hidden z-20">
          {loading ? (
            <div className="text-muted text-center py-4">Searching...</div>
          ) : results.length > 0 ? (
            results.map((result) => (
              <button
                key={result.symbol}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(result.symbol)}
                className="block w-full text-left px-5 py-3 hover:bg-surface transition-colors cursor-pointer"
              >
                <span className="font-semibold">{result.symbol}</span>
                <span className="text-sm text-muted ml-2">{result.company_name}</span>
                <span className="text-xs text-muted ml-2">{result.exchange}</span>
              </button>
            ))
          ) : (
            <div className="text-muted text-center py-4">No results found</div>
          )}
        </div>
      )}
    </div>
  );
}

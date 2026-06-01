import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const [activeIndex, setActiveIndex] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const blurRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const fetchResults = useCallback(async (q: string) => {
    if (q.length === 0) {
      setResults([]);
      setActiveIndex(-1);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results || []);
      setActiveIndex(-1);
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

  // Scroll the active list item into view
  useEffect(() => {
    if (activeIndex < 0 || !listRef.current) return;
    const item = listRef.current.children[activeIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  function handleBlur() {
    blurRef.current = setTimeout(() => setIsOpen(false), 200);
  }

  function handleFocus() {
    if (blurRef.current) clearTimeout(blurRef.current);
    if (query.length > 0) setIsOpen(true);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value);
    setIsOpen(e.target.value.length > 0);
    setActiveIndex(-1);
  }

  function handleSelect(symbol: string) {
    setQuery('');
    setIsOpen(false);
    setActiveIndex(-1);
    if (onSelect) {
      onSelect(symbol);
    } else {
      navigate(`/report/${symbol}`);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!isOpen || results.length === 0) {
      // Enter with no dropdown → navigate directly if query looks like a ticker
      if (e.key === 'Enter' && query.trim()) {
        handleSelect(query.trim().toUpperCase());
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && results[activeIndex]) {
        handleSelect(results[activeIndex].symbol);
      } else if (results.length === 1) {
        handleSelect(results[0].symbol);
      } else if (query.trim()) {
        // Best guess: treat the raw query as a ticker
        handleSelect(query.trim().toUpperCase());
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setActiveIndex(-1);
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
          onKeyDown={handleKeyDown}
          placeholder={placeholder || 'Search by company name or symbol, e.g. AAPL'}
          className="w-full pl-10 sm:pl-12 pr-4 sm:pr-5 py-3 sm:py-4 text-base sm:text-lg rounded-[12px] border-2 border-border focus:border-accent focus:outline-none transition-colors bg-card shadow-sm"
          autoComplete="off"
          spellCheck={false}
        />
      </div>

      {isOpen && query.length > 0 && (
        <div
          ref={listRef}
          className="absolute top-full left-0 right-0 mt-1 bg-card border border-border rounded-[12px] shadow-lg overflow-y-auto z-20 max-h-72"
        >
          {loading ? (
            <div className="text-muted text-center py-4 text-sm">Searching…</div>
          ) : results.length > 0 ? (
            results.map((result, i) => (
              <button
                key={result.symbol}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(result.symbol)}
                onMouseEnter={() => setActiveIndex(i)}
                className={`block w-full text-left px-5 py-3 transition-colors cursor-pointer ${
                  i === activeIndex ? 'bg-accent-light' : 'hover:bg-surface'
                }`}
              >
                <span className="font-semibold">{result.symbol}</span>
                <span className="text-sm text-muted ml-2">{result.company_name}</span>
                <span className="text-xs text-muted ml-2">{result.exchange}</span>
              </button>
            ))
          ) : (
            <div className="text-muted text-center py-4 text-sm">No results found</div>
          )}
        </div>
      )}
    </div>
  );
}

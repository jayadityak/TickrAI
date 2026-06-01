import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Check, Download, Share2, Star, Zap } from 'lucide-react';
import axios from 'axios';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Skeleton from '../components/ui/Skeleton';
import AuthGate from '../components/auth/AuthGate';
import { useReport } from '../hooks/useReport';
import { addRecentReport } from '../hooks/useRecentReports';
import { useAuth } from '../contexts/AuthContext';
import { AGENT_NAMES, AGENT_ICONS } from '../utils/constants';

import CompanyOverview from '../components/report/CompanyOverview';
import FinancialAnalysis from '../components/report/FinancialAnalysis';
import RiskAnalysis from '../components/report/RiskAnalysis';
import AuditorFlags from '../components/report/AuditorFlags';
import EarningsCall from '../components/report/EarningsCall';
import SectorPeerView from '../components/report/SectorPeerView';
import GreenRedFlags from '../components/report/GreenRedFlags';
import ReportChat from '../components/report/ReportChat';
import InsiderTrading from '../components/report/InsiderTrading';
import CongressTrading from '../components/report/CongressTrading';
import NewsSentiment from '../components/report/NewsSentiment';
import InstitutionalOwnership from '../components/report/InstitutionalOwnership';
import AIExecutiveSummary from '../components/report/AIExecutiveSummary';
import AnalystConsensus from '../components/report/AnalystConsensus';
import PriceChart from '../components/report/PriceChart';

// Section IDs used for scroll targets — order matches tabs
const SECTIONS = [
  { tab: 'Summary', id: 'section-summary' },
  { tab: 'Analyst', id: 'section-analyst' },
  { tab: 'Overview', id: 'section-overview' },
  { tab: 'Financials', id: 'section-financials' },
  { tab: 'Risk', id: 'section-risk' },
  { tab: 'Auditor', id: 'section-auditor' },
  { tab: 'Earnings', id: 'section-earnings' },
  { tab: 'Sector', id: 'section-sector' },
  { tab: 'Flags', id: 'section-flags' },
  { tab: 'Insider', id: 'section-insider' },
  { tab: 'Congress', id: 'section-congress' },
  { tab: 'News', id: 'section-news' },
  { tab: 'Institutional', id: 'section-institutional' },
];

const agentComponentMap: Record<number, React.FC<{ data: any }>> = {
  1: CompanyOverview,
  2: FinancialAnalysis,
  3: RiskAnalysis,
  4: AuditorFlags,
  5: EarningsCall,
  6: SectorPeerView,
  7: GreenRedFlags,
};

function ReportContent({ ticker }: { ticker: string }) {
  const { agentResults, isLoading, isComplete, error } = useReport(ticker);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [copied, setCopied] = useState(false);
  const [analystCount, setAnalystCount] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<string>('section-summary');
  const [hiddenSections, setHiddenSections] = useState<Set<string>>(new Set());
  const tabBarRef = useRef<HTMLDivElement>(null);
  const isScrollingRef = useRef(false);

  // Reset hidden sections whenever ticker changes
  useEffect(() => {
    setHiddenSections(new Set());
    setActiveTab('section-summary');
    setAnalystCount(null);
  }, [ticker]);

  // Callback passed to independent data components — hides their tab when they have no data
  const hideSection = useCallback((id: string) => {
    setHiddenSections((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }, []);

  // Only show tabs for sections that have data
  const visibleSections = useMemo(
    () => SECTIONS.filter((s) => !hiddenSections.has(s.id)),
    [hiddenSections],
  );

  const completedCount = agentResults.filter(
    (r) => r.status === 'completed',
  ).length;

  // Build report data object for chat context
  const reportData: Record<string, any> = {};
  for (const r of agentResults) {
    if (r.status === 'completed' && r.data) {
      reportData[r.agent_name] = { data: r.data };
    }
  }

  // Extract exchange + company name from overview agent
  const overviewData = agentResults.find((r) => r.agent_index === 1 && r.status === 'completed')?.data;
  const exchange = overviewData?.exchange || '';
  const companyName = overviewData?.company_name || ticker.toUpperCase();

  // Persist to recent-reports list whenever we have the company name
  useEffect(() => {
    addRecentReport(ticker, companyName);
  }, [ticker, companyName]);

  // Scroll to a section when tab is clicked
  const scrollToSection = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    isScrollingRef.current = true;
    setActiveTab(id);
    // 128px offset = navbar(64) + tab bar(~48) + padding(16)
    const y = el.getBoundingClientRect().top + window.scrollY - 128;
    window.scrollTo({ top: y, behavior: 'smooth' });
    // Re-enable scroll detection after animation
    setTimeout(() => { isScrollingRef.current = false; }, 800);
  }, []);

  // Auto-scroll the tab bar to keep active tab visible
  useEffect(() => {
    if (!tabBarRef.current) return;
    const visIdx = visibleSections.findIndex((s) => s.id === activeTab);
    if (visIdx >= 0) {
      const activeBtn = tabBarRef.current.children[visIdx] as HTMLElement;
      if (activeBtn) {
        activeBtn.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      }
    }
  }, [activeTab, visibleSections]);

  // Track scroll position → highlight the active tab
  useEffect(() => {
    const handleScroll = () => {
      if (isScrollingRef.current) return;
      const offset = 160;
      let current = visibleSections[0]?.id ?? 'section-summary';
      for (let i = visibleSections.length - 1; i >= 0; i--) {
        const el = document.getElementById(visibleSections[i].id);
        if (el && el.getBoundingClientRect().top <= offset) {
          current = visibleSections[i].id;
          break;
        }
      }
      setActiveTab(current);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [visibleSections]);

  // Check watchlist status on mount
  useEffect(() => {
    const token = localStorage.getItem('tickrai_token');
    if (!token) return;
    axios
      .get(`/api/watchlist/${ticker}/status`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((res) => setInWatchlist(res.data.in_watchlist))
      .catch(() => {});
  }, [ticker]);

  const toggleWatchlist = async () => {
    const token = localStorage.getItem('tickrai_token');
    if (!token) return;
    try {
      if (inWatchlist) {
        await axios.delete(`/api/watchlist/${ticker}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setInWatchlist(false);
      } else {
        await axios.post(`/api/watchlist/${ticker}`, null, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setInWatchlist(true);
      }
    } catch {
      // Fail silently
    }
  };

  const handleShare = async () => {
    const url = window.location.href;
    const title = `${ticker.toUpperCase()}${companyName !== ticker.toUpperCase() ? ` — ${companyName}` : ''} · TickrAI Equity Research`;
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
      } else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      // User cancelled or clipboard unavailable — silent
    }
  };

  return (
    <div>
      {/* Print-only header — hidden on screen, shown when printing */}
      <div className="hidden print:block px-8 py-6 border-b border-border">
        <p className="text-xs text-muted uppercase tracking-widest mb-1">TickrAI · Equity Research</p>
        <h1 className="text-2xl font-bold">
          {ticker.toUpperCase()}
          {companyName !== ticker.toUpperCase() && ` — ${companyName}`}
          {exchange && ` (${exchange})`}
        </h1>
        <p className="text-sm text-muted mt-1">
          Report generated {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
        </p>
      </div>

      {/* Top bar — hidden when printing */}
      <div className="print:hidden flex items-center gap-2 sm:gap-4 px-3 sm:px-4 py-3 border-b border-border bg-card">
        <Link
          to="/"
          className="text-muted hover:text-accent transition-colors shrink-0"
        >
          <ArrowLeft size={20} />
        </Link>

        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="font-bold text-lg uppercase">{ticker}</span>
          {exchange && <Badge variant="accent">{exchange}</Badge>}
          <button
            onClick={toggleWatchlist}
            className="ml-1 cursor-pointer transition-colors shrink-0"
            title={inWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
          >
            <Star
              size={20}
              className={inWatchlist ? 'text-amber fill-amber' : 'text-muted hover:text-amber'}
            />
          </button>
        </div>

        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          <Button variant="secondary" size="sm" onClick={() => window.print()}>
            <span className="flex items-center gap-1.5">
              <Download size={16} />
              <span className="hidden sm:inline">Download PDF</span>
            </span>
          </Button>
          <Button variant="ghost" size="sm" onClick={handleShare}>
            <span className="flex items-center gap-1.5">
              {copied ? <Check size={16} className="text-green" /> : <Share2 size={16} />}
              <span className="hidden sm:inline">{copied ? 'Copied!' : 'Share'}</span>
            </span>
          </Button>
        </div>
      </div>

      {/* Undercovered stock banner */}
      {analystCount !== null && analystCount <= 3 && (
        <div className="print:hidden px-3 sm:px-4 py-2 bg-amber/10 border-b border-amber/20 flex items-center gap-2 text-xs text-amber">
          <Zap size={13} className="shrink-0" />
          <span>
            {analystCount === 0
              ? 'No Wall Street analysts cover this stock —'
              : `Only ${analystCount} Wall Street analyst${analystCount > 1 ? 's' : ''} cover${analystCount === 1 ? 's' : ''} this stock —`}{' '}
            this TickrAI report may be the most comprehensive research available.
          </span>
        </div>
      )}

      {/* Sticky section nav — hidden when printing */}
      <div className="print:hidden sticky top-16 z-10 bg-card border-b border-border">
        <div ref={tabBarRef} className="flex overflow-x-auto scrollbar-hide">
          {visibleSections.map((section) => (
            <button
              key={section.id}
              onClick={() => scrollToSection(section.id)}
              className={`px-3 sm:px-4 py-3 text-xs sm:text-sm font-medium transition-colors whitespace-nowrap cursor-pointer ${
                activeTab === section.id
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-muted hover:text-accent'
              }`}
            >
              {section.tab}
            </button>
          ))}
        </div>
      </div>

      {/* Price Chart — loads immediately */}
      <div className="max-w-5xl mx-auto px-3 sm:px-4 pt-4 sm:pt-8">
        <PriceChart ticker={ticker} />
      </div>

      {/* Main content */}
      <div className="max-w-5xl mx-auto px-3 sm:px-4 py-4 sm:py-8 space-y-6 sm:space-y-8">

        {/* AI Executive Summary — appears at top once all 7 agents complete */}
        <div id="section-summary">
          <AIExecutiveSummary
            ticker={ticker}
            reportData={reportData}
            isComplete={isComplete}
          />
        </div>

        {/* Analyst Consensus — Wall Street price targets, rating distribution, key stats */}
        <div id="section-analyst">
          {completedCount > 0 && (
            <AnalystConsensus
              ticker={ticker}
              onNoData={() => hideSection('section-analyst')}
              onCoverageData={(n) => setAnalystCount(n)}
            />
          )}
        </div>

        {/* Progress indicator — hidden on print */}
        {isLoading && (
          <div className="print:hidden bg-surface rounded-[12px] border border-border p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm text-muted">Generating report…</p>
              <span className="text-sm font-semibold text-accent tabular-nums">
                {completedCount} / 7
              </span>
            </div>

            {/* Per-agent progress rows */}
            <div className="space-y-2">
              {[1, 2, 3, 4, 5, 6, 7].map((i) => {
                const done = agentResults.some(
                  (r) => r.agent_index === i && r.status === 'completed',
                );
                return (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-base w-6 text-center shrink-0">{AGENT_ICONS[i - 1]}</span>
                    <div className="flex-1 h-1.5 bg-surface2 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${
                          done ? 'bg-accent w-full' : 'bg-accent/25 w-full animate-pulse'
                        }`}
                      />
                    </div>
                    <span className={`text-xs shrink-0 w-16 ${done ? 'text-accent font-medium' : 'text-muted'}`}>
                      {done ? 'Done ✓' : 'Running…'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <Card className="border-red/40">
            <div className="flex items-start gap-3 py-2">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="font-semibold text-red mb-1">Could not generate report</p>
                <p className="text-sm text-muted">{error}</p>
                <button
                  onClick={() => window.history.back()}
                  className="mt-3 text-xs text-accent hover:underline cursor-pointer"
                >
                  ← Go back
                </button>
              </div>
            </div>
          </Card>
        )}

        {/* Agent sections */}
        {[1, 2, 3, 4, 5, 6, 7].map((agentIndex) => {
          const result = agentResults.find(
            (r) => r.agent_index === agentIndex,
          );
          const Component = agentComponentMap[agentIndex];
          // agentIndex 1→section-overview (index 2), 2→section-financials (index 3), etc.
          // Offset by 2: SECTIONS[0]=summary, SECTIONS[1]=analyst, then agent sections start
          const sectionId = SECTIONS[agentIndex + 1]?.id;

          if (result && result.status === 'completed' && Component) {
            return (
              <div key={agentIndex} id={sectionId}>
                <Component data={result.data} />
              </div>
            );
          }

          // Skeleton placeholder
          return (
            <div key={agentIndex} id={sectionId}>
              <Card>
                <h2 className="font-semibold text-lg mb-4">
                  {AGENT_ICONS[agentIndex - 1]} {AGENT_NAMES[agentIndex - 1]}
                </h2>
                <Skeleton className="h-4 w-full mb-3" />
                <Skeleton className="h-4 w-3/4 mb-3" />
                <Skeleton className="h-4 w-5/6 mb-3" />
                <Skeleton className="h-32 w-full" />
              </Card>
            </div>
          );
        })}

        {/* Insider Trading section — loads independently */}
        <div id="section-insider">
          {completedCount > 0 && (
            <InsiderTrading ticker={ticker} onNoData={() => hideSection('section-insider')} />
          )}
        </div>

        {/* Congress Trading section — loads independently */}
        <div id="section-congress">
          {completedCount > 0 && (
            <CongressTrading ticker={ticker} onNoData={() => hideSection('section-congress')} />
          )}
        </div>

        {/* News Sentiment section — loads independently */}
        <div id="section-news">
          {completedCount > 0 && (
            <NewsSentiment ticker={ticker} onNoData={() => hideSection('section-news')} />
          )}
        </div>

        {/* Institutional Ownership section — loads independently */}
        <div id="section-institutional">
          {completedCount > 0 && (
            <InstitutionalOwnership ticker={ticker} onNoData={() => hideSection('section-institutional')} />
          )}
        </div>

      </div>

      {/* AI Chat — shows once we have at least 1 completed section; hidden on print */}
      {completedCount > 0 && (
        <div className="print:hidden">
          <ReportChat ticker={ticker} reportData={reportData} />
        </div>
      )}
    </div>
  );
}

export default function ReportPage() {
  const { ticker } = useParams();

  return (
    <AuthGate message={`Sign in to generate an AI research report for ${ticker?.toUpperCase()}`}>
      {ticker && <ReportContent ticker={ticker} />}
    </AuthGate>
  );
}

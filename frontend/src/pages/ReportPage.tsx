import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download, Share2, Star } from 'lucide-react';
import axios from 'axios';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Skeleton from '../components/ui/Skeleton';
import AuthGate from '../components/auth/AuthGate';
import { useReport } from '../hooks/useReport';
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
import PriceChart from '../components/report/PriceChart';

// Section IDs used for scroll targets — order matches tabs
const SECTIONS = [
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
  const [activeTab, setActiveTab] = useState(0);
  const tabBarRef = useRef<HTMLDivElement>(null);
  const isScrollingRef = useRef(false);

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

  // Scroll to a section when tab is clicked
  const scrollToSection = useCallback((index: number) => {
    const id = SECTIONS[index]?.id;
    const el = document.getElementById(id);
    if (!el) return;
    isScrollingRef.current = true;
    setActiveTab(index);
    // 128px offset = navbar(64) + tab bar(~48) + padding(16)
    const y = el.getBoundingClientRect().top + window.scrollY - 128;
    window.scrollTo({ top: y, behavior: 'smooth' });
    // Re-enable scroll detection after animation
    setTimeout(() => { isScrollingRef.current = false; }, 800);
  }, []);

  // Auto-scroll the tab bar to keep active tab visible
  useEffect(() => {
    if (!tabBarRef.current) return;
    const activeBtn = tabBarRef.current.children[activeTab] as HTMLElement;
    if (activeBtn) {
      activeBtn.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }
  }, [activeTab]);

  // Track scroll position → highlight the active tab
  useEffect(() => {
    const handleScroll = () => {
      if (isScrollingRef.current) return;
      const offset = 160;
      let current = 0;
      for (let i = SECTIONS.length - 1; i >= 0; i--) {
        const el = document.getElementById(SECTIONS[i].id);
        if (el) {
          const top = el.getBoundingClientRect().top;
          if (top <= offset) {
            current = i;
            break;
          }
        }
      }
      setActiveTab(current);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

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

  return (
    <div>
      {/* Top bar */}
      <div className="flex items-center gap-2 sm:gap-4 px-3 sm:px-4 py-3 border-b border-border bg-card">
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
          <Button variant="secondary" size="sm">
            <span className="flex items-center gap-1.5">
              <Download size={16} />
              <span className="hidden sm:inline">Download PDF</span>
            </span>
          </Button>
          <Button variant="ghost" size="sm">
            <span className="flex items-center gap-1.5">
              <Share2 size={16} />
              <span className="hidden sm:inline">Share</span>
            </span>
          </Button>
        </div>
      </div>

      {/* Sticky section nav */}
      <div className="sticky top-16 z-10 bg-card border-b border-border">
        <div ref={tabBarRef} className="flex overflow-x-auto scrollbar-hide">
          {SECTIONS.map((section, i) => (
            <button
              key={section.id}
              onClick={() => scrollToSection(i)}
              className={`px-3 sm:px-4 py-3 text-xs sm:text-sm font-medium transition-colors whitespace-nowrap cursor-pointer ${
                activeTab === i
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
        {/* Progress indicator */}
        {isLoading && (
          <div className="space-y-2">
            <p className="text-sm text-muted">
              Generating report... {completedCount} of 7 agents complete
            </p>
            <div className="w-full h-2 bg-surface2 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all duration-500"
                style={{ width: `${(completedCount / 7) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <Card className="border-red">
            <p className="text-red text-sm">{error}</p>
          </Card>
        )}

        {/* Agent sections */}
        {[1, 2, 3, 4, 5, 6, 7].map((agentIndex) => {
          const result = agentResults.find(
            (r) => r.agent_index === agentIndex,
          );
          const Component = agentComponentMap[agentIndex];
          // agentIndex 1→section-overview, 2→section-financials, etc.
          const sectionId = SECTIONS[agentIndex - 1]?.id;

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
          {completedCount > 0 && <InsiderTrading ticker={ticker} />}
        </div>

        {/* Congress Trading section — loads independently */}
        <div id="section-congress">
          {completedCount > 0 && <CongressTrading ticker={ticker} />}
        </div>

        {/* News Sentiment section — loads independently */}
        <div id="section-news">
          {completedCount > 0 && <NewsSentiment ticker={ticker} />}
        </div>
      </div>

      {/* AI Chat — shows once we have at least 1 completed section */}
      {completedCount > 0 && (
        <ReportChat ticker={ticker} reportData={reportData} />
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

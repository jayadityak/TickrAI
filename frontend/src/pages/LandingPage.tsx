import { Link } from 'react-router-dom';
import { Compass, FileText, Zap, ShieldCheck } from 'lucide-react';
import TickerSearch from '../components/search/TickerSearch';
import TrendingStocks from '../components/landing/TrendingStocks';
import Card from '../components/ui/Card';
import { POPULAR_TICKERS, AGENT_NAMES, AGENT_ICONS } from '../utils/constants';

const stats = [
  { value: '8,000+', label: 'US-Listed Companies' },
  { value: '7', label: 'AI Research Agents' },
  { value: '~60 sec', label: 'To Full Report' },
  { value: '15+', label: 'Data Sections' },
];

const howItWorks = [
  {
    step: 1,
    title: 'Search a Stock',
    description:
      'Type any US-listed company name or stock symbol to begin your research.',
  },
  {
    step: 2,
    title: 'AI Analyzes in Parallel',
    description:
      '7 specialized research agents run simultaneously, analyzing financials, filings, and earnings calls.',
  },
  {
    step: 3,
    title: 'Get Your Report',
    description:
      'Receive a comprehensive research report in under 2 minutes. Download as PDF or view online.',
  },
];

const moduleDescriptions = [
  'Business profile, revenue segments, competitive positioning, and recent developments sourced from SEC filings.',
  'Quarter-over-quarter and annual revenue, profit, and margin trends with AI-generated variance commentary.',
  'Debt-to-equity, interest coverage, contingent liabilities, and cash flow stress indicators.',
  'Scans annual reports for qualified opinions, going-concern notes, material weaknesses, and auditor changes.',
  'Earnings call transcript analysis for management tone, forward guidance, capex signals, and strategic shifts.',
  'Industry headwinds and tailwinds, regulatory changes, and peer benchmarking across key financial metrics.',
  'Synthesized bullish and bearish signals backed by specific data points from across all research modules.',
];

export default function LandingPage() {
  return (
    <>
      {/* A. Hero Section */}
      <section id="search-hero" className="text-center max-w-4xl mx-auto pt-16 sm:pt-24 pb-12 sm:pb-16 px-4">
        <span className="inline-block uppercase text-xs tracking-widest bg-accent-light text-accent px-4 py-1.5 rounded-full font-medium">
          AI-POWERED EQUITY RESEARCH
        </span>

        <h1 className="text-3xl sm:text-5xl md:text-6xl font-bold tracking-tight leading-tight mt-6 font-sans">
          Institutional-Grade Analysis
          <br />
          <span className="text-accent">for Every Investor</span>
        </h1>

        <p className="text-base sm:text-lg text-muted max-w-2xl mx-auto mt-4 sm:mt-6">
          Comprehensive research reports on 8,000+ US-listed companies, generated
          by 7 parallel AI research agents in under 2 minutes.
        </p>

        <div className="mt-10 max-w-2xl mx-auto">
          <TickerSearch />
        </div>

        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {POPULAR_TICKERS.map((ticker) => (
            <Link
              key={ticker.symbol}
              to={`/report/${ticker.symbol}`}
              className="px-3 py-1 text-sm rounded-full border border-border text-muted hover:border-accent hover:text-accent transition-colors"
            >
              {ticker.symbol}
            </Link>
          ))}
        </div>

        {/* Secondary CTA */}
        <div className="mt-6 flex items-center justify-center">
          <Link
            to="/discover"
            className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors"
          >
            <Compass size={15} />
            Discover undercovered stocks
          </Link>
        </div>

        {/* AI disclaimer */}
        <p className="mt-6 text-xs text-muted max-w-xl mx-auto">
          AI-generated research for informational purposes only.{' '}
          <strong className="font-semibold">Not financial advice.</strong>{' '}
          Always do your own due diligence before investing.
        </p>
      </section>

      {/* Trending Stocks */}
      <TrendingStocks />

      {/* B. Stats Bar */}
      <section className="bg-accent text-white py-8 mt-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-5xl mx-auto px-4">
          {stats.map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-3xl font-bold">{stat.value}</div>
              <div className="text-sm opacity-80 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* C. How It Works */}
      <section className="py-12 sm:py-20 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold text-center mb-8 sm:mb-12">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {howItWorks.map((item) => (
              <Card key={item.step}>
                <div className="w-10 h-10 rounded-full bg-accent text-white flex items-center justify-center font-bold text-lg mb-4">
                  {item.step}
                </div>
                <h3 className="text-lg font-semibold mb-2">{item.title}</h3>
                <p className="text-muted text-sm">{item.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* D. What's in a Report */}
      <section className="py-12 sm:py-20 px-4 bg-surface">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-4">
          What&apos;s in a Report
        </h2>
        <p className="text-muted text-center mb-8 sm:mb-12 max-w-2xl mx-auto text-sm sm:text-base">
          Each report is assembled by 7 specialized AI agents working in parallel, enriched with
          live market data — covering every angle of institutional-grade equity research.
        </p>

        {/* AI Agent modules */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto mb-8">
          {AGENT_NAMES.map((name, i) => (
            <div
              key={name}
              className="bg-card rounded-[12px] border border-border p-6"
            >
              <div className="text-2xl mb-3">{AGENT_ICONS[i]}</div>
              <h3 className="font-semibold mb-2">{name}</h3>
              <p className="text-sm text-muted">{moduleDescriptions[i]}</p>
            </div>
          ))}
        </div>

        {/* Live data sections */}
        <p className="text-center text-xs font-semibold text-muted uppercase tracking-wider mb-4">
          Plus live market data sections
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 max-w-5xl mx-auto">
          {[
            { icon: '📊', label: 'Analyst Consensus', desc: 'Wall Street ratings & price targets' },
            { icon: '👤', label: 'Insider Trading', desc: 'SEC Form 4 filings' },
            { icon: '🏛️', label: 'Congress Trades', desc: 'Congressional disclosures' },
            { icon: '📰', label: 'News Sentiment', desc: 'AI-scored recent headlines' },
            { icon: '🏢', label: 'Institutional Ownership', desc: '13F filings from hedge funds' },
          ].map(({ icon, label, desc }) => (
            <div key={label} className="bg-card rounded-[12px] border border-border p-4 text-center">
              <div className="text-2xl mb-2">{icon}</div>
              <p className="text-sm font-semibold mb-1">{label}</p>
              <p className="text-xs text-muted">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* E. What Makes TickrAI Different */}
      <section className="py-12 sm:py-20 px-4">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-3">
          Built differently
        </h2>
        <p className="text-muted text-center text-sm sm:text-base mb-10 sm:mb-14 max-w-xl mx-auto">
          Not a data dump. Not a chatbot. A structured research process — the same one analysts follow — run in parallel by AI.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
          {[
            {
              icon: <Zap size={22} className="text-accent" />,
              title: 'Discovery Score',
              description: 'Proprietary algorithm ranks 400+ small & mid-caps by analyst coverage gap, upside potential, momentum, and quality — surfacing opportunities before the crowd.',
            },
            {
              icon: <ShieldCheck size={22} className="text-accent" />,
              title: 'Cross-Signal Synthesis',
              description: 'Insider trades, congressional disclosures, news sentiment, and fundamentals are synthesized into a single verdict — not siloed tabs you have to connect yourself.',
            },
            {
              icon: <FileText size={22} className="text-accent" />,
              title: 'SEC Filing Grounded',
              description: '10-K business descriptions and risk factors pull directly from EDGAR — so the AI analysis is anchored to what management actually filed, not just headlines.',
            },
            {
              icon: <Compass size={22} className="text-accent" />,
              title: 'Speed with depth',
              description: '7 agents run in parallel across financials, risk, earnings, peers, flags, and more. What takes an analyst half a day to compile takes TickrAI about 60 seconds.',
            },
          ].map(({ icon, title, description }) => (
            <Card key={title}>
              <div className="mb-3">{icon}</div>
              <h3 className="font-semibold mb-2 text-sm">{title}</h3>
              <p className="text-xs text-muted leading-relaxed">{description}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* F. Bottom CTA */}
      <section className="py-12 sm:py-20 px-4 bg-navy text-white text-center">
        <h2 className="text-2xl sm:text-3xl font-bold mb-4">Ready to Research?</h2>
        <p className="text-white/60 mb-8 text-sm sm:text-base">
          Search any US-listed stock and get a full report in about 60 seconds. No setup, no spreadsheets.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <a
            href="#search-hero"
            onClick={(e) => {
              e.preventDefault();
              document.getElementById('search-hero')?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="inline-block bg-accent text-white px-8 py-3 rounded-[8px] font-medium hover:bg-accent-hover transition-colors text-base cursor-pointer"
          >
            Start Researching
          </a>
          <Link
            to="/discover"
            className="inline-flex items-center gap-1.5 text-white/70 hover:text-white transition-colors text-sm px-4 py-3"
          >
            <Compass size={15} />
            Or browse undercovered stocks
          </Link>
        </div>
      </section>
    </>
  );
}

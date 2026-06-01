import { Link } from 'react-router-dom';
import { Star } from 'lucide-react';
import TickerSearch from '../components/search/TickerSearch';
import TrendingStocks from '../components/landing/TrendingStocks';
import Card from '../components/ui/Card';
import { POPULAR_TICKERS, AGENT_NAMES, AGENT_ICONS } from '../utils/constants';

const stats = [
  { value: '8,000+', label: 'US-Listed Companies' },
  { value: '7', label: 'Research Modules' },
  { value: '<2 min', label: 'Report Generation' },
  { value: '15+', label: 'Report Sections' },
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

      {/* E. Testimonial Section */}
      <section className="py-12 sm:py-20 px-4">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-8 sm:mb-12">
          What Investors Say
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {[
            {
              quote: 'Clean reports with detailed financials, risk analysis, and sectoral context all in one place. Great for quick screening before deeper research.',
              name: 'Michael R.',
              title: 'Buy-Side Research Analyst',
            },
            {
              quote: 'The insider trading and institutional ownership sections are genuinely useful — I cross-reference them before every position. Saves me an hour of digging.',
              name: 'Sarah K.',
              title: 'Hedge Fund Associate',
            },
            {
              quote: 'I used to pay for Bloomberg just to get this data. TickrAI gives me analyst consensus, earnings trends, and news sentiment in one report. Game changer.',
              name: 'David L.',
              title: 'Independent Investor',
            },
          ].map(({ quote, name, title }) => (
            <Card key={name}>
              <div className="flex gap-1 mb-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star key={i} size={16} className="text-amber fill-amber" />
                ))}
              </div>
              <p className="text-muted italic text-sm leading-relaxed">
                &ldquo;{quote}&rdquo;
              </p>
              <div className="mt-4 pt-4 border-t border-border">
                <div className="font-semibold text-sm">{name}</div>
                <div className="text-xs text-muted">{title}</div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* F. Bottom CTA */}
      <section className="py-12 sm:py-20 px-4 bg-navy text-white text-center">
        <h2 className="text-2xl sm:text-3xl font-bold mb-4">Ready to Research?</h2>
        <p className="text-navy-border opacity-70 mb-8">
          Search any US-listed stock to get started.
        </p>
        <a
          href="#search-hero"
          onClick={(e) => {
            e.preventDefault();
            document.getElementById('search-hero')?.scrollIntoView({ behavior: 'smooth' });
          }}
          className="inline-block bg-accent text-white px-8 py-3 rounded-[8px] font-medium hover:bg-accent-hover transition-colors text-lg cursor-pointer"
        >
          Start Researching
        </a>
      </section>
    </>
  );
}

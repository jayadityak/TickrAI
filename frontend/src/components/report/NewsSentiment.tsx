import { useState, useEffect } from 'react';
import { Newspaper, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import axios from 'axios';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

interface Headline {
  title: string;
  summary: string;
  date: string;
  thumbnail: string | null;
  sentiment: 'bullish' | 'bearish' | 'neutral';
}

interface NewsData {
  ticker: string;
  headlines: Headline[];
  overall_score: number;
  overall_label: 'bullish' | 'bearish' | 'neutral';
}

function sentimentIcon(s: string) {
  if (s === 'bullish') return <TrendingUp size={14} className="text-green" />;
  if (s === 'bearish') return <TrendingDown size={14} className="text-red" />;
  return <Minus size={14} className="text-muted" />;
}

function sentimentColor(s: string): string {
  if (s === 'bullish') return 'text-green';
  if (s === 'bearish') return 'text-red';
  return 'text-muted';
}

function sentimentBg(s: string): string {
  if (s === 'bullish') return 'bg-green/10';
  if (s === 'bearish') return 'bg-red/10';
  return 'bg-surface';
}

function scoreColor(score: number): string {
  if (score >= 7) return 'text-green';
  if (score >= 5) return 'text-amber-600';
  return 'text-red';
}

function scoreBarColor(score: number): string {
  if (score >= 7) return 'bg-green';
  if (score >= 5) return 'bg-amber-500';
  return 'bg-red';
}

export default function NewsSentiment({ ticker, onNoData }: { ticker: string; onNoData?: () => void }) {
  const [data, setData] = useState<NewsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchNews = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`/api/news/${ticker}`);
        setData(res.data);
        if (!res.data?.headlines?.length) onNoData?.();
      } catch {
        setData(null);
        onNoData?.();
      } finally {
        setLoading(false);
      }
    };
    fetchNews();
  }, [ticker]);

  if (loading) {
    return (
      <Card>
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <Newspaper size={20} className="text-accent" />
          News Sentiment
        </h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-surface2 rounded w-full" />
          <div className="h-4 bg-surface2 rounded w-3/4" />
          <div className="h-20 bg-surface2 rounded" />
        </div>
      </Card>
    );
  }

  if (!data || data.headlines.length === 0) {
    return null;
  }

  const bullish = data.headlines.filter((h) => h.sentiment === 'bullish').length;
  const bearish = data.headlines.filter((h) => h.sentiment === 'bearish').length;
  const neutral = data.headlines.length - bullish - bearish;

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="font-semibold text-lg flex items-center gap-2">
            <Newspaper size={20} className="text-accent" />
            News Sentiment
          </h2>
          <p className="text-xs text-muted mt-0.5">Past 30 days · AI-scored headlines</p>
        </div>
        <Badge variant={data.overall_label === 'bullish' ? 'green' : data.overall_label === 'bearish' ? 'red' : 'default'}>
          {data.overall_label.charAt(0).toUpperCase() + data.overall_label.slice(1)}
        </Badge>
      </div>

      {/* Sentiment Score */}
      <div className="mb-4 p-3 rounded-[8px] bg-surface">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-muted">Sentiment Score</span>
          <span className={`text-2xl font-bold ${scoreColor(data.overall_score)}`}>
            {data.overall_score}/10
          </span>
        </div>
        <div className="w-full h-2 bg-surface2 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${scoreBarColor(data.overall_score)}`}
            style={{ width: `${data.overall_score * 10}%` }}
          />
        </div>
      </div>

      {/* Breakdown */}
      <div className="flex gap-3 mb-4">
        <div className="bg-green/10 rounded-[8px] px-3 py-2 text-center flex-1">
          <p className="text-xs text-muted">Bullish</p>
          <p className="text-lg font-bold text-green">{bullish}</p>
        </div>
        <div className="bg-surface rounded-[8px] px-3 py-2 text-center flex-1">
          <p className="text-xs text-muted">Neutral</p>
          <p className="text-lg font-bold text-muted">{neutral}</p>
        </div>
        <div className="bg-red/10 rounded-[8px] px-3 py-2 text-center flex-1">
          <p className="text-xs text-muted">Bearish</p>
          <p className="text-lg font-bold text-red">{bearish}</p>
        </div>
      </div>

      {/* Headlines */}
      <div className="space-y-2">
        {data.headlines.map((headline, i) => (
          <div
            key={i}
            className={`rounded-[8px] p-3 border border-border/50 ${sentimentBg(headline.sentiment)}`}
          >
            <div className="flex items-start gap-3">
              {headline.thumbnail && (
                <img
                  src={headline.thumbnail}
                  alt=""
                  className="w-12 h-12 rounded-[6px] object-cover shrink-0 hidden sm:block"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium leading-snug">{headline.title}</p>
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${sentimentBg(headline.sentiment)} ${sentimentColor(headline.sentiment)}`}
                  >
                    {sentimentIcon(headline.sentiment)}
                    {headline.sentiment}
                  </span>
                </div>
                {headline.summary && (
                  <p className="text-xs text-muted mt-1 line-clamp-2">{headline.summary}</p>
                )}
                {headline.date && (
                  <p className="text-xs text-muted/70 mt-1">{headline.date}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-muted mt-4">
        Sentiment scored by AI analysis of recent news headlines.
      </p>
    </Card>
  );
}

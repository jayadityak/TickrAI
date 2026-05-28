export const POPULAR_TICKERS = [
  { symbol: 'AAPL', name: 'Apple' },
  { symbol: 'MSFT', name: 'Microsoft' },
  { symbol: 'GOOGL', name: 'Alphabet' },
  { symbol: 'AMZN', name: 'Amazon' },
  { symbol: 'NVDA', name: 'NVIDIA' },
  { symbol: 'META', name: 'Meta Platforms' },
  { symbol: 'TSLA', name: 'Tesla' },
  { symbol: 'JPM', name: 'JPMorgan Chase' },
] as const;

export const AGENT_NAMES = [
  'Company Overview',
  'Financial Analysis',
  'Risk Analysis',
  'Auditor Flags',
  'Earnings Call',
  'Sector & Peers',
  'Green/Red Flags',
] as const;

export const AGENT_ICONS = [
  '\u{1F3E2}',
  '\u{1F4CA}',
  '⚠️',
  '\u{1F50D}',
  '\u{1F399}️',
  '\u{1F4C8}',
  '\u{1F6A9}',
] as const;

export const API_URL = '/api';

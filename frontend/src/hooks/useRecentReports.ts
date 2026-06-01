const STORAGE_KEY = 'tickrai_recent_reports';
const MAX_ITEMS = 10;

export interface RecentReport {
  ticker: string;
  companyName: string;
  timestamp: number;
}

/** Read the stored list (newest first). Never throws. */
export function getRecentReports(): RecentReport[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as RecentReport[];
  } catch {
    return [];
  }
}

/**
 * Upsert a ticker into the recent-reports list.
 * If the ticker is already there, it moves to the top with the latest timestamp.
 * Trims the list to MAX_ITEMS.
 */
export function addRecentReport(ticker: string, companyName = ''): void {
  const upper = ticker.toUpperCase();
  const existing = getRecentReports().filter((r) => r.ticker !== upper);
  const updated: RecentReport[] = [
    { ticker: upper, companyName, timestamp: Date.now() },
    ...existing,
  ].slice(0, MAX_ITEMS);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // storage quota exceeded — ignore
  }
}

/** Human-readable relative time label. */
export function relativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffDays = Math.floor(diffMs / 86_400_000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

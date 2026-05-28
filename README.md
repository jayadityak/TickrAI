# tickrAI

AI-powered equity research platform for US stocks. Generates comprehensive analysis reports covering 8,000+ NYSE and NASDAQ tickers using 7 parallel AI agents.

## Features

- **7-Agent Report Engine** — Company Overview, Financial Analysis, Risk Analysis, Auditor Flags, Earnings Call, Sector & Peers, Green/Red Flags
- **Real-Time SSE Streaming** — Report sections render progressively as each agent completes
- **Interactive Price Charts** — Powered by Recharts with multiple timeframes (1D to 5Y)
- **Insider & Congress Trading** — Track insider transactions and congressional stock trades
- **News Sentiment** — Aggregated news with per-headline sentiment scoring
- **AI Chat** — Ask follow-up questions about any generated report
- **Ticker Comparison** — Side-by-side comparison of multiple stocks
- **Price Alerts** — Set above/below price targets with auto-polling
- **Watchlist** — Save and track favorite tickers
- **Google OAuth** — Secure authentication with JWT sessions

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 |
| Backend | Python, FastAPI, asyncio |
| Data | yfinance (primary), Financial Modeling Prep (secondary), SEC EDGAR |
| Auth | Google OAuth 2.0, python-jose JWT |
| Charts | Recharts |
| Database | PostgreSQL (Neon) with asyncpg |

## Project Structure

```
tickrai/
├── frontend/                  # React SPA
│   └── src/
│       ├── pages/             # Landing, Report, Dashboard, Compare, Alerts
│       ├── components/
│       │   ├── report/        # 12 report section components
│       │   ├── ui/            # Reusable UI primitives
│       │   ├── layout/        # Navbar, Footer
│       │   └── auth/          # AuthGate, GoogleSignIn
│       ├── hooks/             # useReport (SSE), useAuth, etc.
│       └── contexts/          # AuthContext
├── backend/
│   └── app/
│       ├── agents/            # fmp_report_builder (7 parallel agents)
│       ├── data_sources/      # fmp.py, yahoo_finance.py, edgar.py
│       ├── routers/           # 13 API routers
│       └── config.py          # Pydantic settings
└── .env.example
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL database (or [Neon](https://neon.tech) free tier)

### Environment Variables

Create a `.env` file in `backend/`:

```env
DATABASE_URL=postgresql://...
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
JWT_SECRET=your-jwt-secret
OPENAI_API_KEY=your-openai-key          # optional — reports work without it
FMP_API_KEY=your-fmp-key                # optional — falls back to yfinance
SEC_EDGAR_USER_AGENT=YourName your@email.com
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5174` and proxies API calls to the backend on port 8000.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| POST | `/api/auth/google` | No | Google OAuth token exchange |
| GET | `/api/search?q=` | No | Ticker autocomplete (trigram search) |
| POST | `/api/reports/{ticker}` | Yes | Generate report |
| GET | `/api/reports/{ticker}/stream` | Yes | SSE stream of agent results |
| GET | `/api/chart/{ticker}` | No | Price history for charts |
| GET | `/api/insider/{ticker}` | No | Insider trading data |
| GET | `/api/congress/{ticker}` | No | Congressional trades |
| GET | `/api/news/{ticker}` | No | News with sentiment |
| POST | `/api/chat` | Yes | AI chat about reports |
| GET/POST/DELETE | `/api/watchlist` | Yes | Watchlist CRUD |
| GET/POST/DELETE | `/api/alerts` | Yes | Price alerts CRUD |
| GET | `/api/compare?tickers=` | No | Multi-ticker comparison |
| GET | `/api/trending` | No | Trending tickers |

## How Reports Work

1. User requests a report for a ticker (e.g., AAPL)
2. Backend fetches data from FMP + yfinance in parallel
3. 7 agents run concurrently via `asyncio.gather()`:
   - Agents 1-6 run in parallel (Overview, Financials, Risk, Auditor, Earnings, Sector)
   - Agent 7 (Green/Red Flags) runs after 1-6 complete, synthesizing their outputs
4. Each agent result streams to the frontend via Server-Sent Events
5. Frontend renders sections progressively as they arrive
6. Reports are cached for 24 hours

When FMP's free tier is exhausted, the system automatically falls back to yfinance for all data — reports still generate in under 1 second.

## License

Private repository.

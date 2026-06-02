from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, search, reports, market, chat, insider, trending, compare, watchlist, chart, congress, news, alerts, institutional, ai_summary, analyst, screener


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting TickrAI backend...")
    yield


app = FastAPI(
    title="TickrAI - AI Equity Research",
    version="0.1.0",
    lifespan=lifespan,
)


def _build_cors_origins() -> list[str]:
    """Merge frontend_url + cors_extra_origins + localhost dev into one list."""
    origins = {settings.frontend_url, "http://localhost:5173", "http://localhost:5174"}
    if settings.cors_extra_origins:
        for o in settings.cors_extra_origins.split(","):
            o = o.strip().rstrip("/")
            if o:
                origins.add(o)
    return [o for o in origins if o]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    # Match any Vercel preview deploy of this project (e.g. tickrai-git-feat-x.vercel.app).
    # Project-specific prefix should be set via CORS_EXTRA_ORIGINS or here once known.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(reports.router)
app.include_router(market.router)
app.include_router(chat.router)
app.include_router(insider.router)
app.include_router(trending.router)
app.include_router(compare.router)
app.include_router(watchlist.router)
app.include_router(chart.router)
app.include_router(congress.router)
app.include_router(news.router)
app.include_router(alerts.router)
app.include_router(institutional.router)
app.include_router(ai_summary.router)
app.include_router(analyst.router)
app.include_router(screener.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

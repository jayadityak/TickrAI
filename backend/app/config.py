from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    fmp_api_key: str = ""
    sec_edgar_user_agent: str = "TickrAI research@tickr.ai"
    frontend_url: str = "http://localhost:5173"
    # Comma-separated list of additional allowed CORS origins (production domains,
    # Vercel preview URLs, etc.).  Always merged with frontend_url + localhost dev.
    cors_extra_origins: str = ""
    backend_url: str = "http://localhost:8000"
    environment: str = "development"
    rate_limit_per_day: int = 10
    # Finnhub API key — premium plan required for congressional trading endpoint.
    # If set, enables the Congress trading tab. Leave blank to show a notice instead.
    finnhub_api_key: str = ""
    # Path for persisting price alerts across server restarts.
    # Override with ALERTS_STORE_PATH env var. Default: ./data/alerts.json
    alerts_store_path: str = "./data/alerts.json"
    # Kalshi prediction market API key — enables earnings beat probability and macro signals.
    # Leave blank to disable Kalshi features gracefully.
    kalshi_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()

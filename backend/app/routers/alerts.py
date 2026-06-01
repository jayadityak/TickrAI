"""Price alerts — set target prices, get notified when hit.

Alerts are persisted to a JSON file on disk so they survive server restarts.
The file path is configured via ALERTS_STORE_PATH env var (default: ./data/alerts.json).
"""

import json
import logging
import time
import uuid
from pathlib import Path

import yfinance as yf
from fastapi import APIRouter, Depends

from ..config import settings
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory alerts: user_email -> list of alerts
_alerts: dict[str, list[dict]] = {}

# Price cache: ticker -> (timestamp, price)
_price_cache: dict[str, tuple[float, float]] = {}
_PRICE_TTL = 60  # 1 minute


def _store_path() -> Path:
    return Path(settings.alerts_store_path)


def _load_alerts() -> None:
    """Load alerts from disk into _alerts on startup. Silent on missing file."""
    global _alerts
    path = _store_path()
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _alerts = data
            logger.info("Alerts: loaded %d user(s) from %s", len(_alerts), path)
    except Exception as e:
        logger.warning("Alerts: failed to load from %s: %s", path, e)


def _save_alerts() -> None:
    """Persist _alerts to disk. Silent on write failure."""
    path = _store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(_alerts, f, indent=2)
    except Exception as e:
        logger.warning("Alerts: failed to save to %s: %s", path, e)


# Load persisted alerts at import time
_load_alerts()


def _get_price(symbol: str) -> float | None:
    """Get current price with 1-minute cache."""
    now = time.time()
    if symbol in _price_cache:
        ts, price = _price_cache[symbol]
        if now - ts < _PRICE_TTL:
            return price

    try:
        t = yf.Ticker(symbol)
        info = t.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
        if price:
            _price_cache[symbol] = (now, float(price))
            return float(price)
    except Exception as e:
        logger.warning("Price fetch failed for %s: %s", symbol, e)

    # Return stale cache if available
    if symbol in _price_cache:
        return _price_cache[symbol][1]
    return None


@router.post("/api/alerts")
async def create_alert(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Create a new price alert."""
    email = user["email"]
    ticker = body.get("ticker", "").upper()
    target_price = body.get("target_price")
    direction = body.get("direction", "above")  # "above" or "below"

    if not ticker or target_price is None:
        return {"error": "ticker and target_price required"}

    try:
        target_price = float(target_price)
    except (ValueError, TypeError):
        return {"error": "target_price must be a number"}

    if direction not in ("above", "below"):
        return {"error": "direction must be 'above' or 'below'"}

    current_price = _get_price(ticker)

    alert = {
        "id": str(uuid.uuid4())[:8],
        "ticker": ticker,
        "target_price": target_price,
        "direction": direction,
        "created_at": time.time(),
        "triggered": False,
        "triggered_at": None,
        "current_price": current_price,
    }

    if email not in _alerts:
        _alerts[email] = []
    _alerts[email].append(alert)
    _save_alerts()

    return {"alert": alert}


@router.get("/api/alerts")
async def get_alerts(user: dict = Depends(get_current_user)):
    """Get all alerts for the current user, checking current prices."""
    email = user["email"]
    alerts = _alerts.get(email, [])

    # Check each alert against current price
    newly_triggered = False
    for alert in alerts:
        if alert["triggered"]:
            continue

        price = _get_price(alert["ticker"])
        alert["current_price"] = price

        if price is not None:
            if alert["direction"] == "above" and price >= alert["target_price"]:
                alert["triggered"] = True
                alert["triggered_at"] = time.time()
                newly_triggered = True
            elif alert["direction"] == "below" and price <= alert["target_price"]:
                alert["triggered"] = True
                alert["triggered_at"] = time.time()
                newly_triggered = True

    # Persist if any new triggers fired
    if newly_triggered:
        _save_alerts()

    # Sort: triggered first (newest), then active (newest)
    triggered = [a for a in alerts if a["triggered"]]
    active = [a for a in alerts if not a["triggered"]]
    triggered.sort(key=lambda x: x.get("triggered_at", 0), reverse=True)
    active.sort(key=lambda x: x.get("created_at", 0), reverse=True)

    return {"alerts": active + triggered}


@router.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """Delete a price alert."""
    email = user["email"]
    alerts = _alerts.get(email, [])
    _alerts[email] = [a for a in alerts if a["id"] != alert_id]
    _save_alerts()
    return {"deleted": True}

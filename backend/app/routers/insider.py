"""Insider trading data endpoint.

Uses yfinance to fetch recent insider transactions (Form 4 filings).
Cached for 1 hour to minimize API calls.
"""

import logging
import time
import math

import yfinance as yf
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache: symbol -> (timestamp, data)
_cache: dict[str, tuple[float, list]] = {}
_CACHE_TTL = 3600  # 1 hour


def _fetch_insider_transactions(symbol: str) -> list[dict]:
    """Fetch insider transactions via yfinance."""
    now = time.time()
    if symbol in _cache:
        ts, data = _cache[symbol]
        if now - ts < _CACHE_TTL:
            return data

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.insider_transactions
        if df is None or df.empty:
            return []

        transactions = []
        for _, row in df.head(15).iterrows():
            value = row.get("Value")
            # Handle NaN values
            if value is not None and isinstance(value, float) and math.isnan(value):
                value = None

            text = row.get("Text", "")
            transaction_type = row.get("Transaction", "")

            # Determine if buy or sell
            is_sale = "sale" in str(text).lower() or "sell" in str(transaction_type).lower()
            is_purchase = "purchase" in str(text).lower() or "buy" in str(transaction_type).lower()
            is_gift = "gift" in str(text).lower()

            if is_sale:
                tx_type = "Sale"
            elif is_purchase:
                tx_type = "Purchase"
            elif is_gift:
                tx_type = "Gift"
            else:
                tx_type = str(transaction_type) if transaction_type else "Other"

            date = row.get("Start Date")
            date_str = str(date)[:10] if date else "N/A"

            transactions.append({
                "date": date_str,
                "insider": row.get("Insider", "Unknown"),
                "position": row.get("Position", ""),
                "transaction_type": tx_type,
                "shares": int(row.get("Shares", 0)) if row.get("Shares") else 0,
                "value": float(value) if value else None,
                "text": str(text) if text else "",
            })

        _cache[symbol] = (now, transactions)
        return transactions

    except Exception as e:
        logger.warning("Failed to fetch insider data for %s: %s", symbol, e)
        return []


@router.get("/api/insider/{ticker}")
async def get_insider_trading(ticker: str):
    """Return recent insider transactions for a ticker."""
    transactions = _fetch_insider_transactions(ticker.upper())

    # Compute summary stats
    purchases = [t for t in transactions if t["transaction_type"] == "Purchase"]
    sales = [t for t in transactions if t["transaction_type"] == "Sale"]

    total_buy_value = sum(t["value"] or 0 for t in purchases)
    total_sell_value = sum(t["value"] or 0 for t in sales)
    net_value = total_buy_value - total_sell_value

    return {
        "transactions": transactions,
        "summary": {
            "total_transactions": len(transactions),
            "purchases": len(purchases),
            "sales": len(sales),
            "total_buy_value": total_buy_value,
            "total_sell_value": total_sell_value,
            "net_value": net_value,
            "signal": "Bullish" if net_value > 0 else "Bearish" if net_value < 0 else "Neutral",
        },
    }

TICKERS: list[dict] = [
    {"symbol": "AAPL", "company_name": "Apple Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "MSFT", "company_name": "Microsoft Corporation", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "GOOGL", "company_name": "Alphabet Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "AMZN", "company_name": "Amazon.com Inc.", "exchange": "NASDAQ", "sector": "Consumer Cyclical"},
    {"symbol": "NVDA", "company_name": "NVIDIA Corporation", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "META", "company_name": "Meta Platforms Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "TSLA", "company_name": "Tesla Inc.", "exchange": "NASDAQ", "sector": "Consumer Cyclical"},
    {"symbol": "JPM", "company_name": "JPMorgan Chase & Co.", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "V", "company_name": "Visa Inc.", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "JNJ", "company_name": "Johnson & Johnson", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "WMT", "company_name": "Walmart Inc.", "exchange": "NYSE", "sector": "Consumer Defensive"},
    {"symbol": "PG", "company_name": "Procter & Gamble Co.", "exchange": "NYSE", "sector": "Consumer Defensive"},
    {"symbol": "MA", "company_name": "Mastercard Incorporated", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "UNH", "company_name": "UnitedHealth Group Incorporated", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "HD", "company_name": "The Home Depot Inc.", "exchange": "NYSE", "sector": "Consumer Cyclical"},
    {"symbol": "DIS", "company_name": "The Walt Disney Company", "exchange": "NYSE", "sector": "Communication Services"},
    {"symbol": "BAC", "company_name": "Bank of America Corporation", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "NFLX", "company_name": "Netflix Inc.", "exchange": "NASDAQ", "sector": "Communication Services"},
    {"symbol": "ADBE", "company_name": "Adobe Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "CRM", "company_name": "Salesforce Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "PYPL", "company_name": "PayPal Holdings Inc.", "exchange": "NASDAQ", "sector": "Financial Services"},
    {"symbol": "INTC", "company_name": "Intel Corporation", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "CSCO", "company_name": "Cisco Systems Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "AMD", "company_name": "Advanced Micro Devices Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "PEP", "company_name": "PepsiCo Inc.", "exchange": "NASDAQ", "sector": "Consumer Defensive"},
    {"symbol": "KO", "company_name": "The Coca-Cola Company", "exchange": "NYSE", "sector": "Consumer Defensive"},
    {"symbol": "ABT", "company_name": "Abbott Laboratories", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "TMO", "company_name": "Thermo Fisher Scientific Inc.", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "MRK", "company_name": "Merck & Co. Inc.", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "ABBV", "company_name": "AbbVie Inc.", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "AVGO", "company_name": "Broadcom Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "COST", "company_name": "Costco Wholesale Corporation", "exchange": "NASDAQ", "sector": "Consumer Defensive"},
    {"symbol": "NKE", "company_name": "NIKE Inc.", "exchange": "NYSE", "sector": "Consumer Cyclical"},
    {"symbol": "LLY", "company_name": "Eli Lilly and Company", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "ORCL", "company_name": "Oracle Corporation", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "QCOM", "company_name": "QUALCOMM Incorporated", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "TXN", "company_name": "Texas Instruments Incorporated", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "UPS", "company_name": "United Parcel Service Inc.", "exchange": "NYSE", "sector": "Industrials"},
    {"symbol": "BMY", "company_name": "Bristol-Myers Squibb Company", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "GS", "company_name": "The Goldman Sachs Group Inc.", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "MS", "company_name": "Morgan Stanley", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "BLK", "company_name": "BlackRock Inc.", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "SCHW", "company_name": "The Charles Schwab Corporation", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "C", "company_name": "Citigroup Inc.", "exchange": "NYSE", "sector": "Financial Services"},
    {"symbol": "AMGN", "company_name": "Amgen Inc.", "exchange": "NASDAQ", "sector": "Healthcare"},
    {"symbol": "GILD", "company_name": "Gilead Sciences Inc.", "exchange": "NASDAQ", "sector": "Healthcare"},
    {"symbol": "MDLZ", "company_name": "Mondelez International Inc.", "exchange": "NASDAQ", "sector": "Consumer Defensive"},
    {"symbol": "SYK", "company_name": "Stryker Corporation", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "ZTS", "company_name": "Zoetis Inc.", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "ISRG", "company_name": "Intuitive Surgical Inc.", "exchange": "NASDAQ", "sector": "Healthcare"},
]


def search_tickers(query: str, limit: int = 10) -> list[dict]:
    """Search tickers by symbol or company name using case-insensitive
    prefix and substring matching. Prefix matches on symbol are ranked first."""
    if not query:
        return []

    q = query.upper()
    q_lower = query.lower()

    prefix_matches: list[dict] = []
    substring_matches: list[dict] = []

    for ticker in TICKERS:
        symbol_upper = ticker["symbol"].upper()
        name_lower = ticker["company_name"].lower()

        if symbol_upper.startswith(q):
            prefix_matches.append(ticker)
        elif q_lower in name_lower or q in symbol_upper:
            substring_matches.append(ticker)

    results = prefix_matches + substring_matches
    return results[:limit]


def get_ticker(symbol: str) -> dict | None:
    """Return ticker info for the given symbol, or None if not found."""
    symbol_upper = symbol.upper()
    for ticker in TICKERS:
        if ticker["symbol"].upper() == symbol_upper:
            return ticker
    return None

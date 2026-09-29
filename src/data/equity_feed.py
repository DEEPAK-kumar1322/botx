"""
Equity / Traditional assets market data provider using Yahoo Finance.
"""

from typing import List
from datetime import datetime, timezone
import yfinance as yf
from loguru import logger

from .base import MarketDataFeed, TickerData, OrderBookData, CandleData


class EquityDataFeed(MarketDataFeed):
    """Market data feed for traditional equities and indices (e.g. SPY, AAPL, QQQ)."""

    def __init__(self):
        logger.info("Initialized EquityDataFeed (Yahoo Finance)")

    def fetch_ticker(self, symbol: str) -> TickerData:
        """Fetch fast real-time summary for equity symbol."""
        logger.debug(f"Fetching equity info for {symbol}")
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info

        last_price = float(getattr(info, "last_price", 0.0) or 0.0)
        prev_close = float(getattr(info, "previous_close", 0.0) or last_price)
        pct_change = ((last_price - prev_close) / prev_close * 100.0) if prev_close else 0.0

        return TickerData(
            symbol=symbol,
            source="yahoo_finance",
            timestamp=datetime.now(timezone.utc),
            last_price=last_price,
            bid=None,
            ask=None,
            high_24h=float(getattr(info, "day_high", 0.0) or 0.0),
            low_24h=float(getattr(info, "day_low", 0.0) or 0.0),
            volume_24h=float(getattr(info, "last_volume", 0.0) or 0.0),
            percentage_change_24h=round(pct_change, 2),
        )

    def fetch_order_book(self, symbol: str, limit: int = 5) -> OrderBookData:
        """Order book depth is typically not accessible via free Yahoo Finance APIs."""
        return OrderBookData(
            symbol=symbol,
            source="yahoo_finance",
            timestamp=datetime.now(timezone.utc),
            bids=[],
            asks=[],
        )

    def fetch_recent_candles(self, symbol: str, timeframe: str = "1m", limit: int = 10) -> List[CandleData]:
        """Fetch recent intraday candles."""
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m")
        if df.empty:
            df = ticker.history(period="5d", interval="1m")

        candles: List[CandleData] = []
        for index, row in df.tail(limit).iterrows():
            candles.append(CandleData(
                timestamp=index.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            ))
        return candles

"""
Base abstractions and standard data models for market data feeds.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field


class TickerData(BaseModel):
    """Standardized real-time ticker data."""
    symbol: str
    source: str
    timestamp: datetime
    last_price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    percentage_change_24h: Optional[float] = None


class OrderBookData(BaseModel):
    """Standardized top of order book snapshot."""
    symbol: str
    source: str
    timestamp: datetime
    bids: List[Tuple[float, float]] = Field(description="List of (price, size) bids")
    asks: List[Tuple[float, float]] = Field(description="List of (price, size) asks")


class CandleData(BaseModel):
    """Standardized OHLCV candle item."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataFeed(ABC):
    """Abstract Base Class for modular market data feeds."""

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> TickerData:
        """Fetch current real-time ticker for a given symbol."""
        pass

    @abstractmethod
    def fetch_order_book(self, symbol: str, limit: int = 5) -> OrderBookData:
        """Fetch real-time order book depth for a symbol."""
        pass

    @abstractmethod
    def fetch_recent_candles(self, symbol: str, timeframe: str = "1m", limit: int = 10) -> List[CandleData]:
        """Fetch recent OHLCV candlestick data."""
        pass

"""
Crypto market data provider using CCXT for standardized real-time market data access.
"""

from typing import List, Optional
from datetime import datetime, timezone
import ccxt
from loguru import logger

from .base import MarketDataFeed, TickerData, OrderBookData, CandleData


class CryptoDataFeed(MarketDataFeed):
    """Real-time crypto market data feed powered by CCXT."""

    def __init__(self, exchange_id: str = "binance", api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.exchange_id = exchange_id.lower()
        exchange_class = getattr(ccxt, self.exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{self.exchange_id}' is not supported by CCXT.")

        config = {
            "enableRateLimit": True,
            "timeout": 15000,
        }
        if api_key:
            config["apiKey"] = api_key
        if api_secret:
            config["secret"] = api_secret

        self.client: ccxt.Exchange = exchange_class(config)
        logger.info(f"Initialized CryptoDataFeed for exchange: {self.client.id}")

    def fetch_ticker(self, symbol: str) -> TickerData:
        """Fetch latest ticker from exchange."""
        logger.debug(f"Fetching ticker for {symbol} on {self.client.id}")
        raw = self.client.fetch_ticker(symbol)
        
        ts = raw.get("timestamp")
        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc) if ts else datetime.now(timezone.utc)

        return TickerData(
            symbol=symbol,
            source=self.client.id,
            timestamp=dt,
            last_price=float(raw.get("last") or raw.get("close") or 0.0),
            bid=float(raw.get("bid")) if raw.get("bid") is not None else None,
            ask=float(raw.get("ask")) if raw.get("ask") is not None else None,
            high_24h=float(raw.get("high")) if raw.get("high") is not None else None,
            low_24h=float(raw.get("low")) if raw.get("low") is not None else None,
            volume_24h=float(raw.get("baseVolume")) if raw.get("baseVolume") is not None else None,
            percentage_change_24h=float(raw.get("percentage")) if raw.get("percentage") is not None else None,
        )

    def fetch_order_book(self, symbol: str, limit: int = 5) -> OrderBookData:
        """Fetch top order book bids and asks."""
        logger.debug(f"Fetching order book for {symbol} on {self.client.id} (limit={limit})")
        raw = self.client.fetch_order_book(symbol, limit=limit)
        
        ts = raw.get("timestamp")
        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc) if ts else datetime.now(timezone.utc)

        bids = [(float(b[0]), float(b[1])) for b in raw.get("bids", [])[:limit]]
        asks = [(float(a[0]), float(a[1])) for a in raw.get("asks", [])[:limit]]

        return OrderBookData(
            symbol=symbol,
            source=self.client.id,
            timestamp=dt,
            bids=bids,
            asks=asks,
        )

    def fetch_recent_candles(self, symbol: str, timeframe: str = "1m", limit: int = 10) -> List[CandleData]:
        """Fetch recent OHLCV candlesticks."""
        logger.debug(f"Fetching candles for {symbol} ({timeframe}, limit={limit})")
        raw_candles = self.client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        
        candles: List[CandleData] = []
        for c in raw_candles:
            ts, o, h, l, cl, v = c[:6]
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            candles.append(CandleData(
                timestamp=dt,
                open=float(o),
                high=float(h),
                low=float(l),
                close=float(cl),
                volume=float(v)
            ))
        return candles

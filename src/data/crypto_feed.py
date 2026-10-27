"""
Crypto market data provider using CCXT for standardized real-time market data access.
"""

from typing import List, Optional
from datetime import datetime, timezone
import time
import requests
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
            "timeout": 2500,
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

    def _fetch_delta_candles(self, symbol: str, timeframe: str = "15m", limit: int = 30) -> List[CandleData]:
        """Fetch candles directly from Delta Exchange India chart history (zero ISP blocking)."""
        try:
            delta_sym = symbol.replace("/", "").replace("USDT", "USD")
            res_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "1D"}
            res = res_map.get(timeframe, "15")
            sec_per_candle = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}.get(timeframe, 900)

            now = int(time.time())
            start = now - (sec_per_candle * (limit + 15))

            url = "https://api.india.delta.exchange/v2/chart/history"
            r = requests.get(url, params={"symbol": delta_sym, "resolution": res, "from": start, "to": now}, timeout=5)
            data = r.json()
            if not data.get("success"):
                return []
            res_data = data.get("result", {})
            closes = res_data.get("c", [])
            highs = res_data.get("h", [])
            lows = res_data.get("l", [])
            opens = res_data.get("o", [])
            volumes = res_data.get("v", [])
            times = res_data.get("t", [])

            candles: List[CandleData] = []
            for i in range(len(closes)):
                candles.append(CandleData(
                    timestamp=datetime.fromtimestamp(times[i], tz=timezone.utc),
                    open=float(opens[i]),
                    high=float(highs[i]),
                    low=float(lows[i]),
                    close=float(closes[i]),
                    volume=float(volumes[i]) if volumes else 0.0,
                ))
            return candles[-limit:]
        except Exception as e:
            logger.warning(f"Delta native candle fetch failed for {symbol}: {e}")
            return []

    def fetch_recent_candles(self, symbol: str, timeframe: str = "1m", limit: int = 10) -> List[CandleData]:
        """Fetch recent OHLCV candlesticks (Delta Exchange native primary, CCXT fallback)."""
        logger.debug(f"Fetching candles for {symbol} ({timeframe}, limit={limit})")
        # 1. Try fast, reliable Delta Exchange native feed first (zero ISP blocking in India)
        delta_candles = self._fetch_delta_candles(symbol, timeframe=timeframe, limit=limit)
        if delta_candles and len(delta_candles) >= 5:
            return delta_candles

        # 2. Fallback to CCXT exchange feed if Delta doesn't have symbol
        try:
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
            if candles:
                return candles
        except Exception as e:
            logger.debug(f"CCXT candle fetch fallback failed for {symbol}: {e}")

        return delta_candles

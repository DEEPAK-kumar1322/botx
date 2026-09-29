"""
Unified Multi-Asset Market Data Feed for BotX Trading Engine.

Routes symbol requests to the optimal data source:
- Crypto (BTC/USDT, ETH/USDT): Binance / Kraken (CCXT)
- Metals (XAUUSD, XAGUSD, XAUJPY): Yahoo Finance (GC=F, SI=F, USDJPY=X)
- Indices (US100): Yahoo Finance (NQ=F / ^NDX)
- Forex: Yahoo Finance
"""

from typing import List, Optional
from datetime import datetime, timezone
import yfinance as yf
from loguru import logger

from .base import MarketDataFeed, TickerData, OrderBookData, CandleData
from .crypto_feed import CryptoDataFeed


class UnifiedMarketFeed(MarketDataFeed):
    """Router that handles multi-asset market data from Crypto, Forex, Metals & Indices."""

    # Symbol routing mapping
    YFINANCE_MAP = {
        "XAUUSD": "GC=F",       # Gold Futures / Spot proxy
        "GOLD": "GC=F",
        "XAGUSD": "SI=F",       # Silver Futures / Spot proxy
        "SILVER": "SI=F",
        "US100": "NQ=F",        # Nasdaq 100 Futures / CFD proxy
        "NAS100": "NQ=F",
        "NDX": "^NDX",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
    }

    def __init__(self, crypto_exchange: str = "binance"):
        self.crypto_feed = CryptoDataFeed(exchange_id=crypto_exchange)
        logger.info("Initialized UnifiedMarketFeed with multi-asset routing (Binance + Yahoo Finance)")

    def _classify_asset(self, symbol: str) -> str:
        """Classify asset into crypto, metal, index, or forex."""
        sym_clean = symbol.upper().replace("/", "").replace(" ", "").replace("-", "")
        if "XAUJPY" in sym_clean:
            return "xaujpy"
        if sym_clean in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BTCUSD", "ETHUSD"]:
            return "crypto"
        if sym_clean in self.YFINANCE_MAP or symbol.upper() in self.YFINANCE_MAP:
            return "yfinance"
        if "/" in symbol:
            return "crypto"
        return "yfinance"

    def fetch_ticker(self, symbol: str) -> TickerData:
        """Fetch current ticker from the appropriate source."""
        asset_type = self._classify_asset(symbol)

        if asset_type == "crypto":
            # Normalize to standard pair format (e.g. BTC/USDT)
            norm_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/{symbol[-4:]}"
            return self.crypto_feed.fetch_ticker(norm_symbol)

        elif asset_type == "xaujpy":
            # Calculate Gold in JPY from Gold (USD) * USD/JPY
            gold_t = yf.Ticker("GC=F").fast_info
            jpy_t = yf.Ticker("USDJPY=X").fast_info
            gold_price = float(getattr(gold_t, "last_price", 0.0) or 0.0)
            jpy_rate = float(getattr(jpy_t, "last_price", 0.0) or 0.0)
            xaujpy_price = gold_price * jpy_rate

            return TickerData(
                symbol="XAUJPY",
                source="yahoo_finance (synthetic GC=F * USDJPY=X)",
                timestamp=datetime.now(timezone.utc),
                last_price=round(xaujpy_price, 2),
                bid=None,
                ask=None,
                high_24h=round(float(getattr(gold_t, "day_high", 0.0) or gold_price) * jpy_rate, 2),
                low_24h=round(float(getattr(gold_t, "day_low", 0.0) or gold_price) * jpy_rate, 2),
                volume_24h=float(getattr(gold_t, "last_volume", 0.0) or 0.0),
                percentage_change_24h=0.45,
            )

        else:
            # Traditional equities, commodities, and indices via Yahoo Finance
            sym_clean = symbol.upper().replace("/", "").replace(" ", "").replace("-", "")
            yf_ticker = self.YFINANCE_MAP.get(sym_clean, self.YFINANCE_MAP.get(symbol.upper(), symbol))
            
            logger.debug(f"Routing {symbol} -> Yahoo Finance ({yf_ticker})")
            t = yf.Ticker(yf_ticker)
            info = t.fast_info

            last_price = float(getattr(info, "last_price", 0.0) or 0.0)
            prev_close = float(getattr(info, "previous_close", 0.0) or last_price)
            pct_change = ((last_price - prev_close) / prev_close * 100.0) if prev_close else 0.0

            return TickerData(
                symbol=symbol,
                source=f"yahoo_finance ({yf_ticker})",
                timestamp=datetime.now(timezone.utc),
                last_price=round(last_price, 2),
                bid=None,
                ask=None,
                high_24h=round(float(getattr(info, "day_high", 0.0) or 0.0), 2),
                low_24h=round(float(getattr(info, "day_low", 0.0) or 0.0), 2),
                volume_24h=float(getattr(info, "last_volume", 0.0) or 0.0),
                percentage_change_24h=round(pct_change, 2),
            )

    def fetch_order_book(self, symbol: str, limit: int = 5) -> OrderBookData:
        """Fetch order book for crypto, or mock empty for traditional assets."""
        asset_type = self._classify_asset(symbol)
        if asset_type == "crypto":
            norm_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/{symbol[-4:]}"
            return self.crypto_feed.fetch_order_book(norm_symbol, limit=limit)

        return OrderBookData(
            symbol=symbol,
            source="traditional_market",
            timestamp=datetime.now(timezone.utc),
            bids=[],
            asks=[],
        )

    def fetch_recent_candles(self, symbol: str, timeframe: str = "15m", limit: int = 60) -> List[CandleData]:
        """Fetch recent OHLCV candlesticks for any asset type."""
        asset_type = self._classify_asset(symbol)

        if asset_type == "crypto":
            norm_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/{symbol[-4:]}"
            return self.crypto_feed.fetch_recent_candles(norm_symbol, timeframe=timeframe, limit=limit)

        elif asset_type == "xaujpy":
            # Combine GC=F and USDJPY=X candles
            is_4h = timeframe in ["4h", "240"]
            yf_interval = "1h" if is_4h else ("15m" if timeframe in ["15m", "15"] else ("1h" if timeframe in ["1h", "60"] else "1d"))
            period = "30d" if is_4h else ("5d" if yf_interval in ["1m", "5m", "15m"] else "1mo")
            df_gold = yf.Ticker("GC=F").history(period=period, interval=yf_interval)
            df_jpy = yf.Ticker("USDJPY=X").history(period=period, interval=yf_interval)

            if df_gold.empty or df_jpy.empty:
                return []

            # Merge and multiply prices
            df_merged = df_gold.join(df_jpy[["Close"]].rename(columns={"Close": "Rate_jpy"}), how="inner").dropna()
            if is_4h:
                df_merged = df_merged.resample('4h').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum',
                    'Rate_jpy': 'last'
                }).dropna()

            candles: List[CandleData] = []
            for idx, row in df_merged.tail(limit).iterrows():
                rate = float(row["Rate_jpy"])
                candles.append(CandleData(
                    timestamp=idx.to_pydatetime(),
                    open=round(float(row["Open"]) * rate, 2),
                    high=round(float(row["High"]) * rate, 2),
                    low=round(float(row["Low"]) * rate, 2),
                    close=round(float(row["Close"]) * rate, 2),
                    volume=float(row.get("Volume", 0.0) or 0.0),
                ))
            return candles

        else:
            sym_clean = symbol.upper().replace("/", "").replace(" ", "").replace("-", "")
            yf_ticker = self.YFINANCE_MAP.get(sym_clean, self.YFINANCE_MAP.get(symbol.upper(), symbol))
            is_4h = timeframe in ["4h", "240"]
            yf_interval = "1h" if is_4h else ("15m" if timeframe in ["15m", "15"] else ("1h" if timeframe in ["1h", "60"] else "1d"))
            period = "30d" if is_4h else ("5d" if yf_interval in ["1m", "5m", "15m"] else "1mo")

            logger.debug(f"Fetching candles for {symbol} ({yf_ticker}) with interval={yf_interval} (is_4h={is_4h})")
            df = yf.Ticker(yf_ticker).history(period=period, interval=yf_interval)
            if df.empty:
                df = yf.Ticker(yf_ticker).history(period="1mo", interval=yf_interval)

            if is_4h and not df.empty:
                df = df.resample('4h').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()

            candles: List[CandleData] = []
            for idx, row in df.tail(limit).iterrows():
                candles.append(CandleData(
                    timestamp=idx.to_pydatetime(),
                    open=round(float(row["Open"]), 2),
                    high=round(float(row["High"]), 2),
                    low=round(float(row["Low"]), 2),
                    close=round(float(row["Close"]), 2),
                    volume=float(row.get("Volume", 0.0) or 0.0),
                ))
            return candles

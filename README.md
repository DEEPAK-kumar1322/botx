# Botx - Modular AI Trading Engine

A modular Python framework for real-time market data ingestion, algorithmic strategies, and AI-driven trading execution.

---

## 📁 Project Architecture

```
Botx/
├── .venv/                      # Isolated Python 3.13 virtual environment
├── src/                        # Core modular engine packages
│   ├── __init__.py
│   ├── config.py               # Pydantic configuration & environment settings
│   └── data/                   # Modular Market Data Feeds
│       ├── __init__.py
│       ├── base.py             # MarketDataFeed ABC & standardized Pydantic models
│       ├── crypto_feed.py      # CCXT-powered real-time crypto feed (Binance, Kraken, etc.)
│       └── equity_feed.py      # Yahoo Finance feed for equities, ETFs, & indices
├── scripts/
│   └── verify_market_data.py   # Live feed connectivity & verification script
├── verify_market_data.py       # Quick root runner for feed verification
├── requirements.txt            # Managed dependencies
├── .env.example                # Template for exchange and model API keys
├── .gitignore                  # Git ignore rules for Python / virtualenv
└── README.md                   # Project documentation
```

---

## ⚡ Quickstart

### 1. Activate Environment
In PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Configure Environment Variables (Optional)
Copy `.env.example` to `.env` if you wish to configure specific exchange keys or trading settings:
```powershell
cp .env.example .env
```

### 3. Verify Real-Time Market Data
Run the verification pipeline to verify live ticker, order book depth, and OHLCV candle feeds:
```powershell
.\.venv\Scripts\python.exe verify_market_data.py
```

#### Custom Verification Parameters:
```powershell
# Test a custom crypto pair & exchange:
.\.venv\Scripts\python.exe verify_market_data.py --crypto-symbol ETH/USDT --exchange kraken

# Test with a specific equity symbol:
.\.venv\Scripts\python.exe verify_market_data.py --equity-symbol AAPL
```

---

## 📦 Installed Core Dependencies

- **`ccxt`**: Standardized unified connectivity to 100+ crypto exchanges (order book, tickers, OHLCV, trades).
- **`pandas` & `numpy`**: Fast numerical analysis and time-series data structures.
- **`yfinance`**: Real-time & historical equity and index data.
- **`pydantic` & `python-dotenv`**: Type-safe settings and market event validation.
- **`rich` & `loguru`**: Structured logging and terminal UI reporting.
- **`aiohttp` & `websockets`**: High-performance async communication for real-time feeds.

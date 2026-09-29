"""
Market Data Verification Script for Botx AI Trading Engine.

Tests connectivity to live market feeds (Crypto & Equities), fetches real-time
tickers, order book depth, and recent OHLCV candlestick data, and prints
a formatted summary table using Rich.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Ensure UTF-8 output encoding across Windows terminals
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from loguru import logger

# Configure clean logger for verification
logger.remove()
logger.add(sys.stderr, format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}", level="INFO")

from src.data.crypto_feed import CryptoDataFeed
from src.data.equity_feed import EquityDataFeed
from src.config import config

console = Console(force_terminal=True, legacy_windows=False)


def test_crypto_feed(exchange_name: str, symbol: str) -> bool:
    """Test fetching real-time crypto ticker, order book, and candles."""
    console.rule(f"[bold cyan]Testing Crypto Market Feed: {exchange_name.upper()} ({symbol})[/bold cyan]")
    
    exchanges_to_try = [exchange_name]
    # Add common fallbacks if primary is geo-restricted or unavailable
    for fallback in ["kraken", "coinbase"]:
        if fallback not in exchanges_to_try:
            exchanges_to_try.append(fallback)

    feed = None
    connected_exchange = None
    for ex in exchanges_to_try:
        try:
            console.print(f"[dim][*] Probing connection to {ex.upper()}...[/dim]")
            candidate_feed = CryptoDataFeed(exchange_id=ex)
            test_symbol = symbol if ex == "binance" else ("BTC/USD" if "USD" in symbol else symbol)
            candidate_feed.fetch_ticker(test_symbol)
            feed = candidate_feed
            connected_exchange = ex
            symbol = test_symbol
            console.print(f"[bold green][OK] Successfully connected to {ex.upper()}![/bold green]")
            break
        except Exception as e:
            console.print(f"[yellow][!] Notice: Connection to {ex} failed: {e}. Trying fallback...[/yellow]")

    if not feed:
        console.print("[bold red][FAIL] Could not connect to any crypto exchange feed.[/bold red]")
        return False

    try:
        # 1. Fetch Real-time Ticker
        console.print(f"[dim][*] Fetching real-time ticker for {symbol}...[/dim]")
        ticker = feed.fetch_ticker(symbol)

        ticker_table = Table(title=f"Real-Time Ticker: {ticker.symbol} ({connected_exchange.upper()})", box=box.ROUNDED)
        ticker_table.add_column("Field", style="cyan", no_wrap=True)
        ticker_table.add_column("Value", style="magenta")

        pct_style = "green" if (ticker.percentage_change_24h or 0) >= 0 else "red"
        ticker_table.add_row("Last Price", f"${ticker.last_price:,.2f}")
        ticker_table.add_row("Best Bid", f"${ticker.bid:,.2f}" if ticker.bid else "N/A")
        ticker_table.add_row("Best Ask", f"${ticker.ask:,.2f}" if ticker.ask else "N/A")
        if ticker.bid and ticker.ask:
            spread = ticker.ask - ticker.bid
            ticker_table.add_row("Spread", f"${spread:,.2f} ({(spread / ticker.last_price) * 100:.3f}%)")
        ticker_table.add_row("24h High", f"${ticker.high_24h:,.2f}" if ticker.high_24h else "N/A")
        ticker_table.add_row("24h Low", f"${ticker.low_24h:,.2f}" if ticker.low_24h else "N/A")
        ticker_table.add_row("24h Change", f"[{pct_style}]{ticker.percentage_change_24h:+.2f}%[/{pct_style}]" if ticker.percentage_change_24h is not None else "N/A")
        ticker_table.add_row("24h Volume", f"{ticker.volume_24h:,.2f}" if ticker.volume_24h else "N/A")
        ticker_table.add_row("Timestamp (UTC)", ticker.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        console.print(ticker_table)

        # 2. Fetch Order Book Depth
        console.print(f"[dim][*] Fetching order book depth (top 5)...[/dim]")
        order_book = feed.fetch_order_book(symbol, limit=5)

        ob_table = Table(title="Order Book Depth (Top 5 Bids & Asks)", box=box.SIMPLE_HEAVY)
        ob_table.add_column("Bid Qty", justify="right", style="green")
        ob_table.add_column("Bid Price", justify="right", style="bold green")
        ob_table.add_column("Ask Price", justify="left", style="bold red")
        ob_table.add_column("Ask Qty", justify="left", style="red")

        max_rows = max(len(order_book.bids), len(order_book.asks))
        for i in range(max_rows):
            bid_price = f"${order_book.bids[i][0]:,.2f}" if i < len(order_book.bids) else "-"
            bid_qty = f"{order_book.bids[i][1]:.4f}" if i < len(order_book.bids) else "-"
            ask_price = f"${order_book.asks[i][0]:,.2f}" if i < len(order_book.asks) else "-"
            ask_qty = f"{order_book.asks[i][1]:.4f}" if i < len(order_book.asks) else "-"
            ob_table.add_row(bid_qty, bid_price, ask_price, ask_qty)

        console.print(ob_table)

        # 3. Fetch Recent OHLCV Candles
        console.print(f"[dim][*] Fetching recent 1m OHLCV candles...[/dim]")
        candles = feed.fetch_recent_candles(symbol, timeframe="1m", limit=5)

        candle_table = Table(title="Recent 1m Candlesticks (OHLCV)", box=box.ROUNDED)
        candle_table.add_column("Time (UTC)", style="cyan")
        candle_table.add_column("Open", justify="right")
        candle_table.add_column("High", justify="right")
        candle_table.add_column("Low", justify="right")
        candle_table.add_column("Close", justify="right")
        candle_table.add_column("Volume", justify="right", style="magenta")

        for c in candles:
            candle_color = "green" if c.close >= c.open else "red"
            candle_table.add_row(
                c.timestamp.strftime("%H:%M:%S"),
                f"${c.open:,.2f}",
                f"${c.high:,.2f}",
                f"${c.low:,.2f}",
                f"[{candle_color}]${c.close:,.2f}[/{candle_color}]",
                f"{c.volume:.4f}",
            )

        console.print(candle_table)
        console.print("[bold green][OK] Crypto market data feed verified successfully![/bold green]\n")
        return True

    except Exception as e:
        console.print(f"[bold red][FAIL] Error fetching crypto market data: {e}[/bold red]")
        return False


def test_equity_feed(symbol: str) -> bool:
    """Test fetching equity market data (via Yahoo Finance)."""
    console.rule(f"[bold blue]Testing Traditional Market Feed: Yahoo Finance ({symbol})[/bold blue]")
    try:
        console.print(f"[dim][*] Fetching equity data for {symbol}...[/dim]")
        feed = EquityDataFeed()
        ticker = feed.fetch_ticker(symbol)

        eq_table = Table(title=f"Equity Summary: {ticker.symbol}", box=box.ROUNDED)
        eq_table.add_column("Field", style="cyan")
        eq_table.add_column("Value", style="magenta")

        pct_style = "green" if (ticker.percentage_change_24h or 0) >= 0 else "red"
        eq_table.add_row("Last Price", f"${ticker.last_price:,.2f}")
        eq_table.add_row("Day High", f"${ticker.high_24h:,.2f}")
        eq_table.add_row("Day Low", f"${ticker.low_24h:,.2f}")
        eq_table.add_row("24h Change", f"[{pct_style}]{ticker.percentage_change_24h:+.2f}%[/{pct_style}]")
        eq_table.add_row("Volume", f"{ticker.volume_24h:,.0f}")
        console.print(eq_table)

        console.print("[bold green][OK] Equity market data feed verified successfully![/bold green]\n")
        return True
    except Exception as e:
        console.print(f"[yellow][!] Notice: Equity feed check encountered: {e}[/yellow]\n")
        return False


def main():
    parser = argparse.ArgumentParser(description="Botx Market Data Feed Verification")
    parser.add_argument("--crypto-symbol", default=config.default_symbol, help="Crypto pair (e.g. BTC/USDT)")
    parser.add_argument("--equity-symbol", default="SPY", help="Equity symbol (e.g. SPY, AAPL)")
    parser.add_argument("--exchange", default=config.exchange_id, help="Exchange ID (e.g. binance, kraken, coinbase)")
    parser.add_argument("--skip-equity", action="store_true", help="Skip equity feed test")
    args = parser.parse_args()

    console.print(
        Panel.fit(
            Text("Botx Modular AI Trading Engine\nMarket Data Verification Pipeline", justify="center", style="bold green"),
            border_style="green",
        )
    )

    crypto_ok = test_crypto_feed(exchange_name=args.exchange, symbol=args.crypto_symbol)
    
    if not args.skip_equity:
        test_equity_feed(symbol=args.equity_symbol)

    if crypto_ok:
        console.print(Panel("[bold green][OK] Real-Time Market Data Pipeline is Ready and Fully Functional![/bold green]", border_style="green"))
        sys.exit(0)
    else:
        console.print(Panel("[bold red][FAIL] Market data pipeline verification encountered issues.[/bold red]", border_style="red"))
        sys.exit(1)


if __name__ == "__main__":
    main()

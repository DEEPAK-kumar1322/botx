"""
Standalone Runner to Detect 15m & 1h SMC Setups and Send Telegram Alerts.

Takes detected Fair Value Gaps (FVG) and Order Blocks (OB) from the multi-timeframe
engine (BTC/USDT 15m & 1h) and dispatches formatted alert messages containing:
- Coin Name
- Timeframe
- Setup Type (FVG / Order Block with Bias)
- Exact Price Levels (Zone Top, Zone Bottom, Current Market Price, Gap Size)
"""

import os
import sys
import argparse
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}", level="INFO")

from src.data.crypto_feed import CryptoDataFeed
from scripts.test_mtf_smc import analyze_timeframe
from src.notifications.telegram_alerts import TelegramAlertSender

console = Console(force_terminal=True, legacy_windows=False)


def run_and_notify(symbol: str = "BTC/USDT", exchange: str = "binance", limit: int = 60, max_alerts_per_tf: int = 2):
    console.print(
        Panel.fit(
            Text(
                f"Botx Telegram SMC Alert Dispatcher\nPair: {symbol} | Timeframes: 15m & 1h | Target: Telegram Bot API",
                justify="center",
                style="bold magenta",
            ),
            border_style="magenta",
        )
    )

    # 1. Connect to Market Feed
    console.print(f"[dim][*] Connecting to {exchange.upper()} market feed...[/dim]")
    feed = None
    for ex in [exchange, "kraken", "coinbase"]:
        try:
            cand_feed = CryptoDataFeed(exchange_id=ex)
            target_symbol = symbol if ex == "binance" else ("BTC/USD" if "USD" in symbol else symbol)
            cand_feed.fetch_ticker(target_symbol)
            feed = cand_feed
            symbol = target_symbol
            console.print(f"[bold green][OK] Connected to {ex.upper()}![/bold green]\n")
            break
        except Exception as e:
            console.print(f"[yellow][!] Connection to {ex} failed: {e}. Retrying...[/yellow]")

    if not feed:
        console.print("[bold red][FAIL] Unable to connect to exchange feed.[/bold red]")
        sys.exit(1)

    # 2. Run Multi-Timeframe Analysis
    res_15m = analyze_timeframe(feed, symbol, timeframe="15m", limit=limit)
    res_1h = analyze_timeframe(feed, symbol, timeframe="1h", limit=limit)

    if not res_15m or not res_1h:
        console.print("[bold red][FAIL] Failed to retrieve candle data for analysis.[/bold red]")
        sys.exit(1)

    current_price = res_15m["candles"][-1].close
    sender = TelegramAlertSender()

    console.rule("[bold cyan]Dispatching Alerts to Telegram[/bold cyan]")
    if not sender.is_ready:
        console.print("[yellow][!] Telegram bot credentials not fully set. Alerts will be simulated in logs.[/yellow]")
    else:
        console.print(f"[bold green][*] Telegram credentials verified. Preparing live alert messages...[/bold green]")

    sent_count = 0

    # 3. Dispatch Active 15M Setups
    # Prioritize active/untested FVGs
    active_fvgs_15m = [f for f in res_15m["fvgs"] if not f.mitigated and not f.fully_filled]
    if active_fvgs_15m:
        fvg = active_fvgs_15m[-1]
        console.print(f"[dim][*] Sending 15m Active FVG alert ({fvg.bias.value})...[/dim]")
        if sender.send_fvg_alert(symbol, "15m", fvg, current_price):
            sent_count += 1

    # Prioritize active/untested Order Blocks
    active_obs_15m = [o for o in res_15m["obs"] if not o.broken and not o.mitigated]
    if active_obs_15m:
        ob = active_obs_15m[-1]
        console.print(f"[dim][*] Sending 15m Active Order Block alert ({ob.bias.value})...[/dim]")
        if sender.send_order_block_alert(symbol, "15m", ob, current_price):
            sent_count += 1

    # 4. Dispatch Active 1H Setups
    active_fvgs_1h = [f for f in res_1h["fvgs"] if not f.mitigated and not f.fully_filled]
    if active_fvgs_1h:
        fvg = active_fvgs_1h[-1]
        console.print(f"[dim][*] Sending 1h Active FVG alert ({fvg.bias.value})...[/dim]")
        if sender.send_fvg_alert(symbol, "1h", fvg, current_price):
            sent_count += 1

    active_obs_1h = [o for o in res_1h["obs"] if not o.broken]
    if active_obs_1h:
        ob = active_obs_1h[-1]
        console.print(f"[dim][*] Sending 1h Order Block alert ({ob.bias.value})...[/dim]")
        if sender.send_order_block_alert(symbol, "1h", ob, current_price):
            sent_count += 1

    # 5. Dispatch Executive MTF Summary
    console.print(f"[dim][*] Sending Multi-Timeframe Executive Summary...[/dim]")
    if sender.send_mtf_summary_alert(symbol, res_15m, res_1h, current_price):
        sent_count += 1

    console.print(
        Panel(
            f"[bold green][OK] Successfully processed and dispatched {sent_count} alert messages to Telegram![/bold green]",
            title="Dispatch Complete",
            border_style="green",
        )
    )


def main():
    parser = argparse.ArgumentParser(description="Send 15m & 1h SMC Setups to Telegram")
    parser.add_argument("--symbol", default="BTC/USDT", help="Crypto pair (default: BTC/USDT)")
    parser.add_argument("--exchange", default="binance", help="Exchange ID (default: binance)")
    parser.add_argument("--limit", type=int, default=60, help="Candles to fetch per timeframe")
    args = parser.parse_args()

    run_and_notify(symbol=args.symbol, exchange=args.exchange, limit=args.limit)


if __name__ == "__main__":
    main()

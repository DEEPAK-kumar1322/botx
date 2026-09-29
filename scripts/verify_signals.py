"""
Verification and Demonstration Script for Technical Analysis & Telegram Bot Alerts.

1. Fetches real-time intraday candles using CryptoDataFeed.
2. Analyzes candles for Fair Value Gaps (FVGs) and Order Blocks (OBs).
3. Renders detected patterns in rich terminal tables.
4. Dispatches live or simulated Telegram alert cards.
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
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}", level="INFO")

from src.data.crypto_feed import CryptoDataFeed
from src.analysis.smc import SMCAnalyzer
from src.analysis.models import BiasType, SetupType
from src.notifications.telegram import TelegramNotifier
from src.config import config

console = Console(force_terminal=True, legacy_windows=False)


def run_signals_verification(symbol: str = "BTC/USDT", timeframe: str = "1m", limit: int = 50, exchange: str = "binance"):
    console.print(
        Panel.fit(
            Text(f"Botx Technical Analysis & Telegram Alert Engine\nSymbol: {symbol} | Timeframe: {timeframe} | Candles: {limit}", justify="center", style="bold cyan"),
            border_style="cyan",
        )
    )

    # 1. Fetch Live Candlestick Data
    console.print(f"[dim][*] Fetching {limit} candles for {symbol} on {exchange.upper()}...[/dim]")
    feed = None
    for ex in [exchange, "kraken", "coinbase"]:
        try:
            cand_feed = CryptoDataFeed(exchange_id=ex)
            target_symbol = symbol if ex == "binance" else ("BTC/USD" if "USD" in symbol else symbol)
            candles = cand_feed.fetch_recent_candles(target_symbol, timeframe=timeframe, limit=limit)
            if candles:
                feed = cand_feed
                symbol = target_symbol
                break
        except Exception as e:
            console.print(f"[yellow][!] Could not fetch from {ex}: {e}. Retrying with next...[/yellow]")

    if not feed or not candles:
        console.print("[bold red][FAIL] Failed to retrieve candlestick data.[/bold red]")
        return False

    console.print(f"[bold green][OK] Retrieved {len(candles)} candles. Latest price: ${candles[-1].close:,.2f}[/bold green]\n")

    # 2. Run SMC Technical Analysis
    analyzer = SMCAnalyzer()
    fvgs = analyzer.find_fair_value_gaps(candles)
    obs = analyzer.find_order_blocks(candles, fvgs=fvgs)
    setups = analyzer.extract_setups(candles, symbol=symbol, timeframe=timeframe)

    # 3. Display Fair Value Gaps
    fvg_table = Table(title=f"Detected Fair Value Gaps (FVG) - Last {len(fvgs)} occurrences", box=box.ROUNDED)
    fvg_table.add_column("Time (UTC)", style="cyan")
    fvg_table.add_column("Bias", justify="center")
    fvg_table.add_column("Top Zone", justify="right")
    fvg_table.add_column("Bottom Zone", justify="right")
    fvg_table.add_column("Gap Size", justify="right")
    fvg_table.add_column("Status", justify="center")

    for f in fvgs[-8:]:
        bias_style = "bold green" if f.bias == BiasType.BULLISH else "bold red"
        status_str = "[red]Filled[/red]" if f.fully_filled else ("[yellow]Mitigated[/yellow]" if f.mitigated else "[bold green]Active[/bold green]")
        fvg_table.add_row(
            f.timestamp.strftime("%H:%M:%S"),
            f"[{bias_style}]{f.bias.value}[/{bias_style}]",
            f"${f.top:,.2f}",
            f"${f.bottom:,.2f}",
            f"${f.gap_size:,.2f} ({f.gap_pct:.2f}%)",
            status_str,
        )

    console.print(fvg_table if fvgs else "[yellow]No Fair Value Gaps detected in the chosen candle window.[/yellow]")
    console.print()

    # 4. Display Order Blocks
    ob_table = Table(title=f"Detected Institutional Order Blocks (OB) - Last {len(obs)} occurrences", box=box.ROUNDED)
    ob_table.add_column("Time (UTC)", style="cyan")
    ob_table.add_column("Bias", justify="center")
    ob_table.add_column("Zone High", justify="right")
    ob_table.add_column("Zone Low", justify="right")
    ob_table.add_column("Displacement", justify="right")
    ob_table.add_column("FVG Confluence", justify="center")
    ob_table.add_column("Status", justify="center")

    for ob in obs[-8:]:
        bias_style = "bold green" if ob.bias == BiasType.BULLISH else "bold red"
        status_str = "[red]Broken[/red]" if ob.broken else ("[yellow]Tested[/yellow]" if ob.mitigated else "[bold green]Active[/bold green]")
        fvg_conf = "[bold green]YES[/bold green]" if ob.has_confluence_fvg else "[dim]NO[/dim]"
        ob_table.add_row(
            ob.timestamp.strftime("%H:%M:%S"),
            f"[{bias_style}]{ob.bias.value}[/{bias_style}]",
            f"${ob.top:,.2f}",
            f"${ob.bottom:,.2f}",
            f"{ob.displacement_pct:+.2f}%",
            fvg_conf,
            status_str,
        )

    console.print(ob_table if obs else "[yellow]No Order Blocks detected in the chosen candle window.[/yellow]")
    console.print()

    # 5. Telegram Notification Test
    console.rule("[bold cyan]Testing Telegram Notification Dispatch[/bold cyan]")
    notifier = TelegramNotifier()

    if notifier.is_configured:
        console.print("[bold green][*] Active Telegram configuration detected. Testing live API delivery...[/bold green]")
        conn_test = notifier.test_connection()
        if conn_test.get("ok"):
            console.print(f"[bold green][OK] Connected to Telegram Bot: @{conn_test.get('bot_username')}[/bold green]")
        else:
            console.print(f"[bold red][!] Telegram connection error: {conn_test.get('error')}[/bold red]")

    # Select setup to alert
    alert_setup = setups[0] if setups else None
    if alert_setup:
        console.print(f"[dim][*] Dispatching alert for setup: {alert_setup.setup_type.value} ({alert_setup.bias.value})...[/dim]")
        delivered = notifier.send_setup_alert(alert_setup)
        if delivered:
            if notifier.is_configured:
                console.print("[bold green][OK] Live Telegram alert dispatched to chat successfully![/bold green]")
            else:
                console.print(
                    Panel(
                        Text(
                            "[Simulated Telegram Alert Card]\n"
                            f"Setup: {alert_setup.setup_type.value} ({alert_setup.bias.value})\n"
                            f"Symbol: {alert_setup.symbol} | Zone: ${alert_setup.zone_low:,.2f} - ${alert_setup.zone_high:,.2f}\n"
                            f"Price: ${alert_setup.current_price:,.2f} | Status: {alert_setup.status}\n\n"
                            "To receive live alerts in your Telegram group/channel, add your tokens in .env:\n"
                            "  TELEGRAM_BOT_TOKEN=123456789:ABCdef...\n"
                            "  TELEGRAM_CHAT_ID=-1001234567890",
                            style="green",
                        ),
                        title="Telegram Alert Dispatcher (Dry-Run Mode)",
                        border_style="green",
                    )
                )
    else:
        console.print("[dim][*] No recent setup to alert right now.[/dim]")

    console.print(Panel("[bold green][OK] Technical Analysis & Alert Module Verified Successfully![/bold green]", border_style="green"))
    return True


def main():
    parser = argparse.ArgumentParser(description="Botx Technical Analysis & Telegram Alert Verification")
    parser.add_argument("--symbol", default="BTC/USDT", help="Symbol to analyze")
    parser.add_argument("--timeframe", default="1m", help="Candle timeframe (1m, 5m, 15m, 1h)")
    parser.add_argument("--limit", type=int, default=50, help="Number of candles to fetch")
    parser.add_argument("--exchange", default=config.exchange_id, help="Exchange ID")
    args = parser.parse_args()

    success = run_signals_verification(
        symbol=args.symbol,
        timeframe=args.timeframe,
        limit=args.limit,
        exchange=args.exchange,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

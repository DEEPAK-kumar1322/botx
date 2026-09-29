"""
Multi-Timeframe SMC Test Script for Botx AI Trading Engine.

Fetches the latest 15-minute (15m) and 1-hour (1h) candles for BTC/USDT,
applies Fair Value Gap (FVG) and Institutional Order Block (OB) detection logic,
and prints detailed analysis and setups directly to the terminal.
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

from src.data.base import MarketDataFeed
from src.data.unified_feed import UnifiedMarketFeed
from src.analysis.smc import SMCAnalyzer
from src.analysis.models import BiasType

console = Console(force_terminal=True, legacy_windows=False)


def analyze_timeframe(feed: MarketDataFeed, symbol: str, timeframe: str, limit: int = 60):
    """Fetch candles and analyze FVGs & Order Blocks for a given timeframe."""
    console.rule(f"[bold cyan]Timeframe Analysis: {timeframe.upper()} ({symbol})[/bold cyan]")
    
    # 1. Fetch candles
    console.print(f"[dim][*] Fetching {limit} candles ({timeframe})...[/dim]")
    try:
        candles = feed.fetch_recent_candles(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        console.print(f"[bold red][FAIL] Error fetching {timeframe} candles: {e}[/bold red]")
        return None

    if not candles:
        console.print(f"[bold red][FAIL] No {timeframe} candles returned.[/bold red]")
        return None

    latest = candles[-1]
    console.print(
        f"[bold green][OK] Loaded {len(candles)} candles | "
        f"Latest Close: ${latest.close:,.2f} | Time: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}[/bold green]\n"
    )

    # 2. Run SMC Detection
    # On higher timeframes (15m, 1h), filter gaps slightly higher than 1m noise
    min_gap = 0.02 if timeframe == "15m" else 0.05
    analyzer = SMCAnalyzer(min_gap_pct=min_gap, displacement_factor=1.2)
    
    fvgs = analyzer.find_fair_value_gaps(candles)
    obs = analyzer.find_order_blocks(candles, fvgs=fvgs)

    # 3. Print Fair Value Gaps Table
    fvg_table = Table(
        title=f"Fair Value Gaps (FVG) - {timeframe.upper()} (Found: {len(fvgs)})",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    fvg_table.add_column("Displacement Time (UTC)", style="cyan")
    fvg_table.add_column("Bias", justify="center")
    fvg_table.add_column("Zone Top", justify="right")
    fvg_table.add_column("Zone Bottom", justify="right")
    fvg_table.add_column("Gap Size", justify="right")
    fvg_table.add_column("Status", justify="center")

    recent_fvgs = fvgs[-6:] if len(fvgs) >= 6 else fvgs
    if recent_fvgs:
        for f in recent_fvgs:
            bias_style = "bold green" if f.bias == BiasType.BULLISH else "bold red"
            status_str = (
                "[red]Filled[/red]"
                if f.fully_filled
                else ("[yellow]Mitigated[/yellow]" if f.mitigated else "[bold green]Active (Untested)[/bold green]")
            )
            fvg_table.add_row(
                f.timestamp.strftime("%Y-%m-%d %H:%M"),
                f"[{bias_style}]{f.bias.value}[/{bias_style}]",
                f"${f.top:,.2f}",
                f"${f.bottom:,.2f}",
                f"${f.gap_size:,.2f} ({f.gap_pct:.2f}%)",
                status_str,
            )
        console.print(fvg_table)
    else:
        console.print(f"[yellow]No Fair Value Gaps detected on {timeframe} above {min_gap}% threshold.[/yellow]")

    console.print()

    # 4. Print Order Blocks Table
    ob_table = Table(
        title=f"Institutional Order Blocks (OB) - {timeframe.upper()} (Found: {len(obs)})",
        box=box.ROUNDED,
        header_style="bold blue",
    )
    ob_table.add_column("Candle Time (UTC)", style="cyan")
    ob_table.add_column("Bias", justify="center")
    ob_table.add_column("Zone High", justify="right")
    ob_table.add_column("Zone Low", justify="right")
    ob_table.add_column("Displacement", justify="right")
    ob_table.add_column("FVG Confluence", justify="center")
    ob_table.add_column("Status", justify="center")

    recent_obs = obs[-6:] if len(obs) >= 6 else obs
    if recent_obs:
        for ob in recent_obs:
            bias_style = "bold green" if ob.bias == BiasType.BULLISH else "bold red"
            status_str = (
                "[red]Broken (Invalid)[/red]"
                if ob.broken
                else ("[yellow]Tested Zone[/yellow]" if ob.mitigated else "[bold green]Active (Untested)[/bold green]")
            )
            fvg_conf = "[bold green]YES[/bold green]" if ob.has_confluence_fvg else "[dim]NO[/dim]"
            ob_table.add_row(
                ob.timestamp.strftime("%Y-%m-%d %H:%M"),
                f"[{bias_style}]{ob.bias.value}[/{bias_style}]",
                f"${ob.top:,.2f}",
                f"${ob.bottom:,.2f}",
                f"{ob.displacement_pct:+.2f}%",
                fvg_conf,
                status_str,
            )
        console.print(ob_table)
    else:
        console.print(f"[yellow]No Order Blocks detected on {timeframe}.[/yellow]")

    console.print()
    return {"candles": candles, "fvgs": fvgs, "obs": obs}


def main():
    parser = argparse.ArgumentParser(description="Multi-Timeframe SMC Detection Test Script (15m & 1h)")
    parser.add_argument("--symbol", default="BTC/USDT", help="Crypto pair to analyze (default: BTC/USDT)")
    parser.add_argument("--limit", type=int, default=60, help="Candles to fetch per timeframe (default: 60)")
    parser.add_argument("--exchange", default="binance", help="Exchange ID (default: binance)")
    args = parser.parse_args()

    console.print(
        Panel.fit(
            Text(
                f"Botx Multi-Timeframe SMC Analyzer\nPair: {args.symbol} | Timeframes: 15m & 1h | Exchange: {args.exchange.upper()}",
                justify="center",
                style="bold green",
            ),
            border_style="green",
        )
    )

    # Initialize multi-asset unified data feed
    try:
        feed = UnifiedMarketFeed(crypto_exchange=args.exchange)
        ticker = feed.fetch_ticker(args.symbol)
        console.print(f"[bold green][OK] Connected to feed for {args.symbol}! Current Price: ${ticker.last_price:,.2f} (Source: {ticker.source})[/bold green]\n")
    except Exception as e:
        console.print(f"[bold red][FAIL] Unable to connect to market data feed for {args.symbol}: {e}[/bold red]")
        sys.exit(1)

    # Run Analysis on 15m and 1h
    res_15m = analyze_timeframe(feed, args.symbol, timeframe="15m", limit=args.limit)
    res_1h = analyze_timeframe(feed, args.symbol, timeframe="1h", limit=args.limit)

    # Summary Panel
    if res_15m and res_1h:
        active_fvg_15m = len([f for f in res_15m["fvgs"] if not f.mitigated and not f.fully_filled])
        active_ob_15m = len([o for o in res_15m["obs"] if not o.broken])
        active_fvg_1h = len([f for f in res_1h["fvgs"] if not f.mitigated and not f.fully_filled])
        active_ob_1h = len([o for o in res_1h["obs"] if not o.broken])

        summary_text = (
            f"• [bold cyan]15-Minute (15m)[/bold cyan]: {len(res_15m['fvgs'])} FVGs ({active_fvg_15m} Active) | "
            f"{len(res_15m['obs'])} Order Blocks ({active_ob_15m} Valid)\n"
            f"• [bold cyan]1-Hour (1h)[/bold cyan]:    {len(res_1h['fvgs'])} FVGs ({active_fvg_1h} Active) | "
            f"{len(res_1h['obs'])} Order Blocks ({active_ob_1h} Valid)\n\n"
            "[bold green][OK] Multi-Timeframe SMC Analysis Completed Successfully![/bold green]"
        )
        console.print(Panel(summary_text, title="Multi-Timeframe SMC Summary", border_style="cyan"))

    sys.exit(0)


if __name__ == "__main__":
    main()

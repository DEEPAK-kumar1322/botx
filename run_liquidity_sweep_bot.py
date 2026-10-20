"""
BotX 24/7 Algorithmic Trading Scanner & Auto-Execution Engine.

Supported Strategies:
1. Liquidity Sweep Strategy (Default):
   - 15M LTF + 1H HTF Filter
   - Support & Resistance Liquidity Sweeps (Pin Bar wick >= 45% or Pause Breakout)
   - 1:3 RR + CTC Trailing Stop
2. Price Action Retest Scalper (Funded Trader Video Strategy):
   - 5M Entry + 1H Trend Direction
   - 5M Break of Structure (BOS) + Retest / Pullback
   - Rejection Wick (>= 40%) OR Engulfing Candle confirmation
   - 1:2 RR Target
3. Shared Dynamic Strategy Switcher:
   - Switches dynamically via active_strategy.json (or via WhatsApp command / Web Dashboard).
   - Defaults to Liquidity Sweep unless explicitly switched to Retest Scalper.
"""

import os
import sys
import time
import argparse
from pathlib import Path
from typing import List, Optional

# Ensure UTF-8 output encoding on Windows terminals
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}", level="INFO")

from src.config import config
from src.data.unified_feed import UnifiedMarketFeed
from src.strategies.liquidity_sweep import LiquiditySweepAnalyzer
from src.strategies.price_action_retest import PriceActionRetestAnalyzer
from src.strategies.state_manager import get_active_strategy, VALID_STRATEGIES
from src.notifications.whatsapp_alerts import WhatsAppAlertSender
from src.notifications.telegram_alerts import TelegramAlertSender
from src.execution.binance_client import BinanceFuturesClient
from src.execution.order_manager import OrderManager
from src.execution.position_monitor import PositionMonitor

console = Console(force_terminal=True, legacy_windows=False)


def scan_symbols_once(
    feed: UnifiedMarketFeed,
    sweep_analyzer: LiquiditySweepAnalyzer,
    retest_analyzer: PriceActionRetestAnalyzer,
    whatsapp: WhatsAppAlertSender,
    telegram: TelegramAlertSender,
    symbols: List[str],
    timeframe: str = "15m",
    order_manager: Optional[OrderManager] = None,
    position_monitor: Optional[PositionMonitor] = None,
    max_positions: int = 2,
) -> List[dict]:
    """Scan all target symbols once using the currently active strategy."""
    # 1. Update active positions & check for Cost-To-Cost (CTC) breakeven triggers
    if position_monitor:
        try:
            position_monitor.check_and_update_positions()
        except Exception as e:
            logger.error(f"Error checking position monitor: {e}")

    # Fetch currently active positions to prevent duplicates and respect limits
    open_syms = set()
    if order_manager:
        try:
            cur_pos = order_manager.client.get_open_positions()
            open_syms = {p['symbol'] for p in cur_pos if abs(float(p.get('positionAmt', 0))) > 0}
        except Exception as e:
            logger.warning(f"Failed to fetch active positions: {e}")

    # Check active strategy dynamically from state manager
    active_strat = get_active_strategy()
    strat_display_name = VALID_STRATEGIES.get(active_strat, active_strat)

    table = Table(
        title=f"24/7 Scanner [Strategy: {strat_display_name}] (Auto-Trade: {'ACTIVE ($150 @ 14x)' if order_manager else 'OFF'})",
        header_style="bold cyan",
        show_header=True,
    )
    table.add_column("Pair", style="bold white", width=11)
    table.add_column("Price", justify="right", width=12)
    table.add_column("1H Bias", justify="center", width=13)
    table.add_column("Key Level / BOS", justify="right", width=14)
    table.add_column("Strategy Details", justify="center", width=16)
    table.add_column("Status / Signal", style="bold", width=22)

    signals_found = []

    for symbol in symbols:
        try:
            if active_strat == "funded_retest_scalper":
                # Video Strategy: 5M Entry + 1H Trend
                candles_5m = feed.fetch_recent_candles(symbol, timeframe="5m", limit=50)
                candles_1h = feed.fetch_recent_candles(symbol, timeframe="1h", limit=50)
                eval_res = retest_analyzer.evaluate(candles_5m, candles_1h, symbol=symbol, timeframe="5m")

                p_fmt = ".2f" if eval_res.current_price > 10 else (".4f" if eval_res.current_price > 0.01 else ".6f")
                broken_str = f"${eval_res.broken_level:{p_fmt}}" if eval_res.broken_level else "-"
                bias_color = "green" if eval_res.htf_bias == "BULLISH" else ("red" if eval_res.htf_bias == "BEARISH" else "yellow")

                if eval_res.has_valid_setup and eval_res.signal:
                    sig = eval_res.signal
                    signals_found.append(sig)
                    action_color = "bold green" if sig.action == "BUY" else "bold red"
                    status_cell = (
                        f"[{action_color}]{sig.action} (5M Retest)[/{action_color}]\n"
                        f"Entry: ${sig.entry_price:{p_fmt}} | SL: ${sig.stop_loss:{p_fmt}}\n"
                        f"TP (1:2 RR): ${sig.tp_1_2rr:{p_fmt}}"
                    )
                    table.add_row(
                        symbol,
                        f"${eval_res.current_price:{p_fmt}}",
                        f"[{bias_color}]{eval_res.htf_bias} ({eval_res.htf_confidence}%)[/{bias_color}]",
                        broken_str,
                        sig.confirmation_type,
                        status_cell,
                    )

                    # Auto-Execute on Binance Futures Testnet
                    target_exec_coins = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ZECUSDT", "XRPUSDT", "AVAXUSDT"]
                    raw_sym = symbol.replace("/", "").upper()
                    if order_manager and raw_sym in target_exec_coins:
                        if raw_sym in open_syms:
                            logger.info(f"Skipping {raw_sym}: Active position already exists on Binance.")
                        elif len(open_syms) >= max_positions:
                            logger.info(f"Skipping {raw_sym}: Max open positions ({max_positions}) reached.")
                        else:
                            trade_res = order_manager.execute_trade(
                                symbol=sig.symbol,
                                side=sig.action,
                                entry_price=sig.entry_price,
                                stop_loss=sig.stop_loss,
                                take_profit=sig.tp_1_2rr,
                                margin_usdt=150.0,
                                leverage=14,
                                reason=f"A++ 5M Retest ({sig.confirmation_type})",
                            )
                            if trade_res.get("status") == "SUCCESS":
                                open_syms.add(raw_sym)
                                if position_monitor:
                                    position_monitor.register_trade(
                                        symbol=sig.symbol,
                                        side=sig.action,
                                        entry_price=trade_res["fill_price"],
                                        initial_sl=sig.stop_loss,
                                        tp_price=sig.tp_1_2rr,
                                        qty=trade_res["quantity"],
                                        sl_order_id=trade_res.get("sl_order_id"),
                                        tp_order_id=trade_res.get("tp_order_id"),
                                    )
                else:
                    wait_msg = eval_res.wait_reasons[0] if eval_res.wait_reasons else "Waiting for 5M BOS Retest"
                    table.add_row(
                        symbol,
                        f"${eval_res.current_price:{p_fmt}}",
                        f"[{bias_color}]{eval_res.htf_bias} ({eval_res.htf_confidence}%)[/{bias_color}]",
                        broken_str,
                        "5M Structure",
                        f"[dim]WAITING: {wait_msg[:24]}[/dim]",
                    )

            else:
                # Default Strategy: Liquidity Sweep (15M + 1H, 1:3 RR)
                candles_ltf = feed.fetch_recent_candles(symbol, timeframe=timeframe, limit=60)
                candles_htf = feed.fetch_recent_candles(symbol, timeframe="1h", limit=60)
                eval_res = sweep_analyzer.evaluate(candles_ltf, candles_htf, symbol=symbol, timeframe=timeframe)

                p_fmt = ".2f" if eval_res.current_price > 10 else (".4f" if eval_res.current_price > 0.01 else ".6f")
                sup_str = f"${eval_res.nearest_support:{p_fmt}}" if eval_res.nearest_support else "-"
                res_str = f"${eval_res.nearest_resistance:{p_fmt}}" if eval_res.nearest_resistance else "-"
                bias_color = "green" if eval_res.htf_bias == "BULLISH" else ("red" if eval_res.htf_bias == "BEARISH" else "yellow")

                if eval_res.has_valid_setup and eval_res.signal:
                    sig = eval_res.signal
                    signals_found.append(sig)
                    action_color = "bold green" if sig.action == "BUY" else "bold red"
                    status_cell = (
                        f"[{action_color}]{sig.action} ({sig.sweep_type[:11]})[/{action_color}]\n"
                        f"Entry: ${sig.entry_price:{p_fmt}} | SL: ${sig.stop_loss:{p_fmt}}\n"
                        f"TP1 (1:2): ${sig.tp_1_2rr:{p_fmt}} | TP2 (1:3): ${sig.tp_1_3rr:{p_fmt}}"
                    )
                    table.add_row(
                        symbol,
                        f"${eval_res.current_price:{p_fmt}}",
                        f"[{bias_color}]{eval_res.htf_bias} ({eval_res.htf_confidence}%)[/{bias_color}]",
                        f"S:{sup_str} R:{res_str}",
                        sig.confirmation_type[:14],
                        status_cell,
                    )

                    # Log signal internally (WhatsApp will only alert if order is filled)
                    logger.info(f"A+ Liquidity Sweep signal detected for {symbol}: {sig.action} Entry: {sig.entry_price}")

                    # Auto-Execute on Binance Futures Testnet
                    target_exec_coins = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ZECUSDT", "XRPUSDT", "AVAXUSDT"]
                    raw_sym = symbol.replace("/", "").upper()
                    if order_manager and raw_sym in target_exec_coins:
                        if raw_sym in open_syms:
                            logger.info(f"Skipping {raw_sym}: Active position already exists on Binance.")
                        elif len(open_syms) >= max_positions:
                            logger.info(f"Skipping {raw_sym}: Max open positions ({max_positions}) reached.")
                        else:
                            trade_res = order_manager.execute_trade(
                                symbol=sig.symbol,
                                side=sig.action,
                                entry_price=sig.entry_price,
                                stop_loss=sig.stop_loss,
                                take_profit=sig.tp_1_3rr,
                                margin_usdt=150.0,
                                leverage=14,
                                reason=f"{sig.sweep_type} ({sig.confirmation_type})",
                            )
                            if trade_res.get("status") == "SUCCESS":
                                open_syms.add(raw_sym)
                                if position_monitor:
                                    position_monitor.register_trade(
                                        symbol=sig.symbol,
                                        side=sig.action,
                                        entry_price=trade_res["fill_price"],
                                        initial_sl=sig.stop_loss,
                                        tp_price=sig.tp_1_3rr,
                                        qty=trade_res["quantity"],
                                        sl_order_id=trade_res.get("sl_order_id"),
                                        tp_order_id=trade_res.get("tp_order_id"),
                                    )
                else:
                    wait_msg = eval_res.wait_reasons[0] if eval_res.wait_reasons else "Waiting for sweep setup"
                    table.add_row(
                        symbol,
                        f"${eval_res.current_price:{p_fmt}}",
                        f"[{bias_color}]{eval_res.htf_bias} ({eval_res.htf_confidence}%)[/{bias_color}]",
                        f"S:{sup_str} R:{res_str}",
                        "Liquidity Sweep",
                        f"[dim]WAITING: {wait_msg[:24]}[/dim]",
                    )

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            table.add_row(symbol, "ERR", "-", "-", "-", f"[red]{e}[/red]")

    console.print(table)
    return signals_found


def main():
    parser = argparse.ArgumentParser(description="BotX 24/7 Algorithmic Trading Scanner & Auto-Execution Bot")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ZEC/USDT", "XRP/USDT", "AVAX/USDT"],
        help="Pairs to monitor 24/7 (BTC ETH BNB SOL ZEC XRP AVAX)",
    )
    parser.add_argument("--timeframe", default="15m", help="Execution timeframe (default: 15m)")
    parser.add_argument("--interval", type=int, default=60, help="Scan interval in seconds (default: 60s)")
    parser.add_argument("--auto-trade", action="store_true", default=True, help="Enable auto-execution on Binance Futures")
    parser.add_argument("--max-positions", type=int, default=2, help="Max open positions allowed simultaneously (default: 2)")
    args = parser.parse_args()

    feed = UnifiedMarketFeed()
    sweep_analyzer = LiquiditySweepAnalyzer(swing_window=5, lookback_sweep_bars=3)
    retest_analyzer = PriceActionRetestAnalyzer(swing_window_5m=3, swing_window_1h=3)
    whatsapp = WhatsAppAlertSender(cooldown_seconds=14400)
    telegram = TelegramAlertSender(cooldown_seconds=14400)

    # Initialize Binance Execution Client & Position Monitor
    api_key = config.api_key or ""
    api_secret = config.api_secret or ""
    is_sandbox = config.exchange_sandbox

    order_manager = None
    position_monitor = None

    if api_key and api_secret:
        client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret, testnet=is_sandbox)
        order_manager = OrderManager(
            client=client,
            default_leverage=14,
            default_position_margin_usdt=150.0,
            whatsapp_sender=whatsapp,
            telegram_sender=telegram,
        )
        position_monitor = PositionMonitor(
            client=client,
            whatsapp_sender=whatsapp,
            ctc_threshold_pct=0.4,
        )
        logger.info("Binance Auto-Execution Engine ACTIVE ($150 Margin @ 14x Leverage | CTC Trailing Active)")

    console.print(
        Panel.fit(
            Text(
                f"BotX 24/7 Multi-Strategy Scanner & Auto-Execution Engine\n"
                f"Pairs: {', '.join(args.symbols)} | Target Margin: $150 @ 14x Leverage\n"
                f"Default Strategy: Liquidity Sweep (1:3 RR) | Dynamic Switcher: ACTIVE\n"
                f"Auto-Trade: {'ACTIVE' if order_manager else 'OFF'} | Trailing CTC: {'ACTIVE' if position_monitor else 'OFF'}",
                justify="center",
                style="bold cyan",
            ),
            border_style="cyan",
        )
    )

    console.print(f"[bold green][*] Starting 24/7 continuous monitoring & position management (every {args.interval}s)...[/bold green]\n")
    cycle = 1
    try:
        while True:
            console.rule(f"[bold blue]Scan Cycle #{cycle} — {time.strftime('%Y-%m-%d %H:%M:%S')}[/bold blue]")
            scan_symbols_once(
                feed,
                sweep_analyzer,
                retest_analyzer,
                whatsapp,
                telegram,
                args.symbols,
                timeframe=args.timeframe,
                order_manager=order_manager,
                position_monitor=position_monitor,
                max_positions=args.max_positions,
            )
            cycle += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        console.print("\n[yellow][!] Bot stopped by user.[/yellow]")


if __name__ == "__main__":
    main()

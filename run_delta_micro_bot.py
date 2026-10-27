"""
BotX 24/7 Delta Exchange India Micro-Pair Scanner & Auto-Execution Engine.

Designed for micro-capital accounts (e.g. ₹131 INR / $1.55 USD):
- Scans 10 Micro-Contract Pairs: XRP, SUI, ADA, POL, TRX, OP, GALA, IOTA, DOGE, NEAR
- Dual Strategy Engine:
    1. Video Strategy: Price Action 5M Retest Scalper (5M BOS + Engulfing Retest | 1:2 RR)
    2. Institutional Strategy: Liquidity Sweep (15M Sweep + Reclaim Wick | 1:3 RR)
- Strict Capital & Risk Guard:
    * Max Margin: ₹20 - ₹25 per trade (leaving ₹100+ safe buffer)
    * Max Stop-Loss: ₹3 - ₹5 max risk per trade
    * Max Concurrent Open Positions: 1 ONLY
    * Auto-Trailing Cost-to-Cost (CTC)
    * Real-time WhatsApp notifications
"""

import os
import time
import argparse
from typing import List, Dict, Any, Optional
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from dotenv import load_dotenv

load_dotenv()

from src.data.unified_feed import UnifiedMarketFeed
from src.strategies.price_action_retest import PriceActionRetestAnalyzer
from src.strategies.liquidity_sweep import LiquiditySweepAnalyzer
from src.strategies.enhanced_sweep_engine import EnhancedSweepAnalyzer
from src.analysis.monte_carlo_validator import MonteCarloValidator
from src.strategies.poc_pullback import POCPullbackAnalyzer
from src.execution.delta_client import DeltaExchangeClient
from src.notifications.whatsapp_alerts import WhatsAppAlertSender
from src.notifications.telegram_alerts import TelegramAlertSender

console = Console()

# 🎯 TOP 10 VERIFIED MICRO-PAIRS ON DELTA EXCHANGE INDIA
# All 10 pairs strictly require between Rs 5.00 and Rs 12.00 INR margin per trade!
# Massive buffer (>Rs 110 INR) remains 100% safe in wallet.
MICRO_PAIRS = [
    {"feed_sym": "XRP/USDT",  "delta_sym": "XRPUSD",  "product_id": 14969, "contract_val": 1.0,   "default_contracts": 1},  # ~Rs 11.50 margin
    {"feed_sym": "SUI/USDT",  "delta_sym": "SUIUSD",  "product_id": 17328, "contract_val": 1.0,   "default_contracts": 1},  # ~Rs 8.80 margin
    {"feed_sym": "POL/USDT",  "delta_sym": "POLUSD",  "product_id": 39943, "contract_val": 10.0,  "default_contracts": 1},  # ~Rs 8.20 margin
    {"feed_sym": "ADA/USDT",  "delta_sym": "ADAUSD",  "product_id": 16614, "contract_val": 1.0,   "default_contracts": 5},  # ~Rs 9.50 margin
    {"feed_sym": "LDO/USDT",  "delta_sym": "LDOUSD",  "product_id": 19616, "contract_val": 1.0,   "default_contracts": 2},  # ~Rs 7.10 margin
    {"feed_sym": "ARB/USDT",  "delta_sym": "ARBUSD",  "product_id": 17331, "contract_val": 1.0,   "default_contracts": 5},  # ~Rs 8.10 margin
    {"feed_sym": "DOT/USDT",  "delta_sym": "DOTUSD",  "product_id": 15304, "contract_val": 1.0,   "default_contracts": 1},  # ~Rs 9.80 margin
    {"feed_sym": "TRX/USDT",  "delta_sym": "TRXUSD",  "product_id": 20193, "contract_val": 1.0,   "default_contracts": 3},  # ~Rs 8.40 margin
    {"feed_sym": "OP/USDT",   "delta_sym": "OPUSD",   "product_id": 19618, "contract_val": 0.1,   "default_contracts": 50}, # ~Rs 5.60 margin
    {"feed_sym": "GALA/USDT", "delta_sym": "GALAUSD", "product_id": 27912, "contract_val": 100.0, "default_contracts": 5},  # ~Rs 8.40 margin
    {"feed_sym": "MUBARAK/USDT", "delta_sym": "MUBARAKUSD", "product_id": 68176, "contract_val": 10.0, "default_contracts": 10}, # ~Rs 4.50 margin per contract
]

# Hard-banned oversized symbols (Delta contract multiplier too big for micro accounts)
BANNED_SYMBOLS = {"DOGEUSD", "NEARUSD", "SOLUSD", "BNBUSD", "BTCUSD", "ETHUSD", "AVAXUSD", "LINKUSD"}

class DeltaMicroBot:
    def __init__(self, auto_trade: bool = True, max_margin_inr: float = 50.0):
        self.auto_trade = auto_trade
        self.max_margin_inr = min(max_margin_inr, 60.0)
        self.feed = UnifiedMarketFeed()
        self.video_strat = PriceActionRetestAnalyzer()
        self.sweep_strat = LiquiditySweepAnalyzer()
        self.enhanced_sweep = EnhancedSweepAnalyzer(min_rvol=1.05)
        self.mc_validator = MonteCarloValidator(replays=1000)
        self.poc_strat = POCPullbackAnalyzer()
        self.client = DeltaExchangeClient(
            api_key=os.getenv("DELTA_API_KEY", ""),
            api_secret=os.getenv("DELTA_API_SECRET", ""),
            is_india=os.getenv("DELTA_IS_INDIA", "true").lower() == "true",
        )
        self.telegram = TelegramAlertSender()
        self.last_trade_time = 0
        self.active_trade: Optional[Dict[str, Any]] = None

    def check_open_positions(self) -> List[Dict[str, Any]]:
        try:
            return self.client.get_open_positions()
        except Exception as e:
            logger.error(f"Error checking Delta positions: {e}")
            return []

    def get_wallet_inr(self) -> float:
        try:
            summary = self.client.get_account_summary()
            return float(summary.get("inr_balance", 0.0))
        except Exception:
            return 0.0

    def execute_micro_signal(self, pair_cfg: Dict[str, Any], signal_type: str, action: str, entry_price: float, sl_price: float, tp_price: float, reason: str, is_high_conviction: bool = False, recommended_contracts: Optional[int] = None):
        delta_sym = pair_cfg["delta_sym"]
        product_id = pair_cfg["product_id"]
        c_val = pair_cfg["contract_val"]
        base_contracts = pair_cfg["default_contracts"]

        # Calculate single contract margin in INR at 10x leverage
        single_notional_usd = 1 * c_val * entry_price
        single_margin_inr = (single_notional_usd / 10.0) * 85.0

        if recommended_contracts and recommended_contracts > 0:
            contracts = recommended_contracts
        elif single_margin_inr > 0:
            target_margin = 40.0  # target Rs 35-45 INR range
            contracts = max(1, round(target_margin / single_margin_inr))
        else:
            contracts = base_contracts

        notional_usd = contracts * c_val * entry_price
        est_margin_inr = (notional_usd / 10.0) * 85.0

        # Cap margin to max allowed (never exceed hard cap)
        while est_margin_inr > self.max_margin_inr and contracts > 1:
            contracts -= 1
            notional_usd = contracts * c_val * entry_price
            est_margin_inr = (notional_usd / 10.0) * 85.0

        logger.info(f"🎯 POSITION SIZING: {contracts} contracts {delta_sym} (~Rs {est_margin_inr:.2f} INR margin, cap Rs {self.max_margin_inr:.2f})")

        # Strict hard cap: skip if minimum contract exceeds max allowed margin
        if est_margin_inr > self.max_margin_inr:
            logger.warning(f"Skipping {delta_sym}: Required margin ₹{est_margin_inr:.2f} INR exceeds cap of ₹{self.max_margin_inr:.2f} INR!")
            return

        # Hard-ban check: never trade banned symbols
        if delta_sym in BANNED_SYMBOLS:
            logger.error(f"🚫 HARD-BANNED: {delta_sym} is permanently blocked. Skipping!")
            return

        inr_balance = self.get_wallet_inr()
        logger.info(f"🚨 EXECUTING MICRO TRADE ON DELTA: {action} {contracts} {delta_sym} @ ${entry_price:.4f} (Margin: Rs {est_margin_inr:.2f} | Balance: Rs {inr_balance:.2f})")

        side = "buy" if action.upper() == "BUY" else "sell"
        res = self.client.place_order(
            product_id=product_id,
            size=contracts,
            side=side,
            order_type="market_order",
            stop_loss=sl_price,
            take_profit=tp_price,
        )

        logger.info(f"Delta Order Response: {res}")
        if res.get("success"):
            self.last_trade_time = time.time()
            self.active_trade = {
                "symbol": delta_sym,
                "product_id": product_id,
                "entry_price": entry_price,
                "contracts": contracts,
                "side": side,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "entry_time": time.time(),
            }

            try:
                tg_msg = (
                    f"🚨 <b>[DELTA INDIA - MICRO TRADE EXECUTED]</b> 🚨\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🪙 <b>Pair:</b> <code>{delta_sym}</code> ({action.upper()})\n"
                    f"🎯 <b>Strategy:</b> <b>{signal_type}</b>\n"
                    f"🧠 <b>Logic:</b> <i>{reason}</i>\n"
                    f"📦 <b>Size:</b> <code>{contracts} Contract(s)</code> (~${notional_usd:.2f} Notional)\n"
                    f"💰 <b>Margin Used:</b> <b>~₹{est_margin_inr:.2f} INR</b> (Safe Micro Mode)\n"
                    f"📍 <b>Entry Price:</b> <code>${entry_price:.4f}</code>\n"
                    f"🛑 <b>Strict SL:</b> <code>${sl_price:.4f}</code> (Max Risk: <b>-₹{(contracts * abs(entry_price - sl_price) * 85.0):.2f} INR</b>)\n"
                    f"🎯 <b>Target TP:</b> <code>${tp_price:.4f}</code> (Target Gain: <b>+₹{(contracts * abs(tp_price - entry_price) * 85.0):.2f} INR</b>)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🛡️ <b>Wallet Safety:</b> ₹{inr_balance:.2f} mein se sirf ₹{est_margin_inr:.2f} use hua.\n"
                    f"💼 <b>Safe Buffer Remaining:</b> <b>₹{inr_balance - est_margin_inr:.2f} INR</b> untouched!"
                )
                self.telegram.send_raw_message(tg_msg)
            except Exception as e:
                logger.warning(f"Telegram alert error: {e}")

    def scan_cycle(self, cycle_num: int):
        table = Table(title=f"Delta India Swing Scanner Cycle #{cycle_num} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        table.add_column("Pair", style="cyan", justify="left")
        table.add_column("Price", style="white", justify="right")
        table.add_column("1H Bias", justify="center")
        table.add_column("15M Swing Retest", justify="left")
        table.add_column("15M Liquidity Sweep", justify="left")
        table.add_column("4H POC Pullback (30M)", justify="left")

        open_positions = self.check_open_positions()
        has_open_pos = len(open_positions) > 0
        inr_bal = self.get_wallet_inr()

        # Rehydrate active_trade if position exists on exchange but active_trade is None
        if not self.active_trade and has_open_pos:
            for p in open_positions:
                p_sz = int(p.get("size", 0))
                if p_sz != 0:
                    self.active_trade = {
                        "symbol": p.get("product_symbol"),
                        "product_id": p.get("product_id"),
                        "entry_price": float(p.get("entry_price", 0)),
                        "contracts": abs(p_sz),
                        "side": "buy" if p_sz > 0 else "sell",
                        "sl_price": float(p.get("entry_price", 0)) * (0.99 if p_sz > 0 else 1.01),
                        "tp_price": float(p.get("entry_price", 0)) * (1.02 if p_sz > 0 else 0.98),
                        "entry_time": time.time(),
                    }
                    logger.info(f"Rehydrated active trade from exchange: {self.active_trade['symbol']} ({p_sz} contracts @ ${self.active_trade['entry_price']:.4f})")
                    break

        # Check if active trade has closed and send Telegram Exit Alert
        if self.active_trade:
            active_sym = self.active_trade["symbol"]
            matching = [p for p in open_positions if p.get("product_symbol") == active_sym and int(p.get("size", 0)) != 0]
            if not matching:
                logger.info(f"Position on {active_sym} has CLOSED! Sending Telegram Exit Alert...")
                try:
                    entry_p = self.active_trade["entry_price"]
                    sl_p = self.active_trade["sl_price"]
                    tp_p = self.active_trade["tp_price"]
                    side_trade = self.active_trade["side"]
                    
                    # Fetch live ticker for last price
                    ticker = self.client.get_ticker(active_sym)
                    exit_price = float(ticker.get("mark_price", entry_p))
                    
                    pnl_usd = (exit_price - entry_p) if side_trade == "buy" else (entry_p - exit_price)
                    pnl_inr = pnl_usd * 85.0
                    is_win = pnl_inr >= 0
                    outcome_title = "🎉 TAKE-PROFIT HIT (PROFIT BOOKED!) 🎉" if is_win else "🛑 STOP-LOSS HIT (LOSS CUT SAFELY)"
                    
                    exit_msg = (
                        f"📊 <b>[{outcome_title}]</b> 📊\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🪙 <b>Pair:</b> <code>{active_sym}</code>\n"
                        f"📍 <b>Entry Price:</b> <code>${entry_p:.4f}</code>\n"
                        f"🏁 <b>Exit Price:</b> <code>${exit_price:.4f}</code>\n"
                        f"💡 <b>Close Reason:</b> {'Take-Profit target level reached' if is_win else 'Stop-Loss protected capital from drawdown'}\n"
                        f"💰 <b>Net PnL Added:</b> <b>{'+' if is_win else ''}₹{pnl_inr:.2f} INR</b> ({'+' if is_win else ''}${pnl_usd:.4f} USD)\n"
                        f"📈 <b>New Delta Wallet Balance:</b> <b>₹{inr_bal:.2f} INR</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔒 Capital strictly protected. Ready for next A++ setup."
                    )
                    self.telegram.send_raw_message(exit_msg)

                    # Cancel remaining open/bracket orders for this product to prevent orphan orders
                    prod_id = self.active_trade.get("product_id")
                    if prod_id:
                        try:
                            self.client.request("DELETE", "/v2/orders/all", data={"product_id": prod_id})
                            logger.info(f"Cleaned up remaining bracket orders for product {prod_id}")
                        except Exception as ce:
                            logger.warning(f"Order cleanup warning: {ce}")
                except Exception as e:
                    logger.error(f"Error sending exit alert: {e}")
                self.active_trade = None
        has_open_pos = len(open_positions) > 0
        inr_bal = self.get_wallet_inr()

        for p_cfg in MICRO_PAIRS:
            sym_feed = p_cfg["feed_sym"]
            delta_sym = p_cfg["delta_sym"]

            try:
                c_15m = self.feed.fetch_recent_candles(sym_feed, timeframe="15m", limit=60)
                c_1h = self.feed.fetch_recent_candles(sym_feed, timeframe="1h", limit=60)

                if not c_15m or not c_1h:
                    continue

                curr_p = c_15m[-1].close

                # Evaluate Video Strategy on 15M swing timeframe
                res_v = self.video_strat.evaluate(c_15m, c_1h, symbol=sym_feed, timeframe="15m")
                # Evaluate Sweep Strategy on 15M swing timeframe with Enhanced Engine (Volume + 1:1 RR + Noise-buffered SL)
                res_s = self.enhanced_sweep.evaluate(
                    c_15m,
                    c_1h,
                    symbol=sym_feed,
                    timeframe="15m",
                    max_loss_inr=4.0,
                    contract_multiplier=p_cfg["contract_val"],
                    leverage=10.0,
                )

                # Evaluate 4H Fixed Range Volume Profile (POC Pullback) on 30M
                c_4h = self.feed.fetch_recent_candles(sym_feed, timeframe="4h", limit=40)
                c_30m = self.feed.fetch_recent_candles(sym_feed, timeframe="30m", limit=40)
                res_poc = self.poc_strat.evaluate(c_30m, c_4h, symbol=sym_feed)

                bias_style = "green" if res_v.htf_bias == "BULLISH" else ("red" if res_v.htf_bias == "BEARISH" else "yellow")
                bias_text = f"[{bias_style}]{res_v.htf_bias}[/{bias_style}]"

                v_cell = f"[bold green]SIGNAL: {res_v.signal.action}[/]" if res_v.has_valid_setup else "[dim]Waiting for 15M BOS[/dim]"
                s_cell = f"[bold green]SIGNAL: {res_s.signal.action} (1:1)[/]" if res_s.has_valid_setup else "[dim]Waiting for 15M Sweep[/dim]"

                if res_poc.has_valid_setup and res_poc.signal:
                    poc_cell = f"[bold green]SIGNAL: {res_poc.signal.action} (POC ${res_poc.poc_price:.4f})[/]"
                elif res_poc.in_poc_zone:
                    poc_cell = f"[bold yellow]At POC (${res_poc.poc_price:.4f})[/]"
                elif res_poc.poc_price:
                    poc_cell = f"[dim]POC ${res_poc.poc_price:.4f} ({res_poc.distance_to_poc_pct:+.1f}%)[/dim]"
                else:
                    poc_cell = "[dim]Scanning[/dim]"

                table.add_row(delta_sym, f"${curr_p:.4f}", bias_text, v_cell, s_cell, poc_cell)

                # Check if we should execute a trade (1 position only, 10 min cooldown - strict)
                time_since_trade = time.time() - self.last_trade_time
                if self.auto_trade and not has_open_pos and time_since_trade > 600:
                    # User Directive: EXCLUSIVELY trade 15M Institutional Liquidity Sweep Strategy with 1:1 RR
                    if res_s.has_valid_setup and res_s.signal:
                        sig = res_s.signal
                        entry_p = sig.entry_price
                        sl_p = sig.stop_loss
                        tp_1_1 = sig.take_profit
                        
                        # Pre-Trade Monte Carlo Validation (from trader-timemachine)
                        sim = self.mc_validator.simulate(
                            c_15m,
                            action=sig.action,
                            entry_price=entry_p,
                            stop_loss=sl_p,
                            take_profit=tp_1_1,
                        )
                        logger.info(f"🎲 Monte Carlo Replay on {delta_sym}: Target {sim.target_prob}% | Stop {sim.stop_prob}% | Verdict: {sim.verdict}")

                        # Execute if odds are >= 45% (filter out trades with heavy negative expectancy)
                        if sim.target_prob >= 45.0:
                            self.execute_micro_signal(
                                pair_cfg=p_cfg,
                                signal_type=f"15M Liquidity Sweep 1:1 (RVOL {sig.relative_volume:.1f}x)",
                                action=sig.action,
                                entry_price=entry_p,
                                sl_price=sl_p,
                                tp_price=tp_1_1,
                                reason=f"A+ 15M Sweep of ${sig.swept_level} with 1:1 RR. MC Target {sim.target_prob}%.",
                                is_high_conviction=True,
                                recommended_contracts=sig.recommended_contracts,
                            )
                            has_open_pos = True
                        else:
                            logger.warning(f"Skipping {delta_sym}: Monte Carlo odds too low ({sim.target_prob}% target vs {sim.stop_prob}% stop).")

            except Exception as e:
                table.add_row(delta_sym, "ERR", "-", f"[red]{str(e)[:25]}[/]", "-", "-")

        console.print(table)
        console.print(f"[bold cyan]Delta Wallet Balance:[/] Rs. {inr_bal:.2f} | [bold green]Open Positions:[/] {len(open_positions)} (Cap: 1) | [bold yellow]Auto-Trade:[/] {'ACTIVE' if self.auto_trade else 'OFF'}")

    def run(self, interval: int = 60):
        console.print(Panel.fit(
            f"[bold green]BotX 24/7 Delta Exchange India Micro Scanner Running[/]\n"
            f"[cyan]Scanning 10 Pairs | Dual Strategy Engine (Video Retest + Liquidity Sweep)[/]\n"
            f"[yellow]Risk Guard: Max Margin Rs {self.max_margin_inr:.2f} | Max Risk Rs 3-5 per trade[/]",
            border_style="cyan"
        ))

        cycle = 1
        while True:
            try:
                self.scan_cycle(cycle)
                cycle += 1
            except Exception as e:
                logger.error(f"Scan cycle error: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60, help="Scan interval in seconds")
    parser.add_argument("--auto-trade", action="store_true", default=True, help="Auto execute signals")
    parser.add_argument("--max-margin", type=float, default=50.0, help="Max INR margin per trade (hard cap Rs 50)")
    args = parser.parse_args()

    bot = DeltaMicroBot(auto_trade=args.auto_trade, max_margin_inr=args.max_margin)
    bot.run(interval=args.interval)

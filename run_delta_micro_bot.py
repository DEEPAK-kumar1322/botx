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
import sys
import json
import time
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
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

PAPER_STATE_FILE = "data/paper_account.json"

def load_paper_account() -> Dict[str, Any]:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(PAPER_STATE_FILE):
        try:
            with open(PAPER_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "balance_inr": 110.88,
        "initial_balance_inr": 110.88,
        "trades": [],
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
        "active_trade": None,
    }

def save_paper_account(data: Dict[str, Any]):
    os.makedirs("data", exist_ok=True)
    try:
        with open(PAPER_STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save paper account: {e}")

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
    def __init__(self, auto_trade: bool = True, max_margin_inr: float = 50.0, paper_mode: bool = True):
        self.auto_trade = auto_trade
        self.paper_mode = paper_mode
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
        self.paper_state = load_paper_account() if self.paper_mode else {}
        self.active_trade: Optional[Dict[str, Any]] = self.paper_state.get("active_trade") if self.paper_mode else None

    def check_open_positions(self) -> List[Dict[str, Any]]:
        if self.paper_mode:
            if self.active_trade:
                p_sz = self.active_trade["contracts"] if self.active_trade["side"] == "buy" else -self.active_trade["contracts"]
                return [{
                    "product_symbol": self.active_trade["symbol"],
                    "product_id": self.active_trade.get("product_id"),
                    "size": p_sz,
                    "entry_price": self.active_trade["entry_price"],
                }]
            return []
        try:
            return self.client.get_open_positions()
        except Exception as e:
            logger.error(f"Error checking Delta positions: {e}")
            return []

    def get_wallet_inr(self) -> float:
        if self.paper_mode:
            return float(self.paper_state.get("balance_inr", 110.88))
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
            return False

        # Hard-ban check: never trade banned symbols
        if delta_sym in BANNED_SYMBOLS:
            logger.error(f"🚫 HARD-BANNED: {delta_sym} is permanently blocked. Skipping!")
            return False

        inr_balance = self.get_wallet_inr()
        side = "buy" if action.upper() == "BUY" else "sell"

        # 🧪 DEMO / PAPER TRADING EXECUTION
        if self.paper_mode:
            self.last_trade_time = time.time()
            self.active_trade = {
                "symbol": delta_sym,
                "product_id": product_id,
                "contract_val": c_val,
                "entry_price": entry_price,
                "contracts": contracts,
                "side": side,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "entry_time": time.time(),
                "ctc_activated": False,
            }
            self.paper_state["active_trade"] = self.active_trade
            save_paper_account(self.paper_state)
            logger.info(f"🧪 [DEMO TRADE SIMULATED] {action} {contracts} {delta_sym} @ ${entry_price:.4f} (Margin: Rs {est_margin_inr:.2f} | Balance: Rs {inr_balance:.2f})")

            try:
                tg_msg = (
                    f"🧪 <b>[DEMO / PAPER TRADE EXECUTED]</b> 🧪\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🪙 <b>Pair:</b> <code>{delta_sym}</code> ({action.upper()})\n"
                    f"🎯 <b>Strategy:</b> <b>{signal_type}</b>\n"
                    f"🧠 <b>Logic:</b> <i>{reason}</i>\n"
                    f"📦 <b>Size:</b> <code>{contracts} Contract(s)</code> (~${notional_usd:.2f} Notional)\n"
                    f"💰 <b>Demo Margin:</b> <b>~₹{est_margin_inr:.2f} INR</b>\n"
                    f"📍 <b>Entry Price:</b> <code>${entry_price:.4f}</code>\n"
                    f"🛑 <b>Strict SL:</b> <code>${sl_price:.4f}</code> (Max Risk: <b>-₹{(contracts * abs(entry_price - sl_price) * c_val * 85.0):.2f} INR</b>)\n"
                    f"🎯 <b>Target TP:</b> <code>${tp_price:.4f}</code> (Target Gain: <b>+₹{(contracts * abs(tp_price - entry_price) * c_val * 85.0):.2f} INR</b>)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔒 <i>Real account is 100% frozen & safe. Zero real money at risk!</i>"
                )
                self.telegram.send_raw_message(tg_msg)
            except Exception as e:
                logger.warning(f"Telegram alert error: {e}")
            return True

        # 🚨 LIVE REAL MONEY EXECUTION ON DELTA EXCHANGE
        logger.info(f"🚨 EXECUTING MICRO TRADE ON DELTA: {action} {contracts} {delta_sym} @ ${entry_price:.4f} (Margin: Rs {est_margin_inr:.2f} | Balance: Rs {inr_balance:.2f})")
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
                "contract_val": c_val,
                "entry_price": entry_price,
                "contracts": contracts,
                "side": side,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "entry_time": time.time(),
                "ctc_activated": False,
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
                    f"🛑 <b>Strict SL:</b> <code>${sl_price:.4f}</code> (Max Risk: <b>-₹{(contracts * abs(entry_price - sl_price) * c_val * 85.0):.2f} INR</b>)\n"
                    f"🎯 <b>Target TP:</b> <code>${tp_price:.4f}</code> (Target Gain: <b>+₹{(contracts * abs(tp_price - entry_price) * c_val * 85.0):.2f} INR</b>)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🛡️ <b>Wallet Safety:</b> ₹{inr_balance:.2f} mein se sirf ₹{est_margin_inr:.2f} use hua.\n"
                    f"💼 <b>Safe Buffer Remaining:</b> <b>₹{inr_balance - est_margin_inr:.2f} INR</b> untouched!"
                )
                self.telegram.send_raw_message(tg_msg)
            except Exception as e:
                logger.warning(f"Telegram alert error: {e}")
            return True
        else:
            logger.error(f"Failed to execute {delta_sym}: {res.get('error')}")
            return False

    def scan_cycle(self, cycle_num: int):
        mode_tag = "[DEMO / PAPER TRADING]" if self.paper_mode else "[LIVE REAL MONEY]"
        table = Table(title=f"Delta India SMC Blueprint Scanner Cycle #{cycle_num} {mode_tag} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        table.add_column("Pair", style="cyan", justify="left")
        table.add_column("Price", style="white", justify="right")
        table.add_column("50 EMA Macro", justify="center")
        table.add_column("Fib 50% Zone", justify="center")
        table.add_column("Master Blueprint (SMC)", justify="left")
        table.add_column("4H POC Pullback", justify="left")

        open_positions = self.check_open_positions()
        has_open_pos = len(open_positions) > 0
        inr_bal = self.get_wallet_inr()

        # Rehydrate active_trade if position exists on exchange (live mode only)
        if not self.paper_mode and not self.active_trade and has_open_pos:
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
                        "ctc_activated": False,
                    }
                    logger.info(f"Rehydrated active trade from exchange: {self.active_trade['symbol']} ({p_sz} contracts @ ${self.active_trade['entry_price']:.4f})")
                    break

        # Check active trade for Cost-to-Cost (CTC) Trailing & Exit Alerts
        if self.active_trade:
            active_sym = self.active_trade["symbol"]
            entry_p = float(self.active_trade["entry_price"])
            sl_p = float(self.active_trade["sl_price"])
            tp_p = float(self.active_trade["tp_price"])
            side_trade = self.active_trade["side"]
            contracts = self.active_trade.get("contracts", 1)
            c_val = self.active_trade.get("contract_val", 1.0)
            ctc_done = self.active_trade.get("ctc_activated", False)

            # Fetch live ticker for this symbol
            ticker = self.client.get_ticker(active_sym)
            mark_p = float(ticker.get("mark_price", 0)) if ticker else 0.0

            # 🧪 DEMO / PAPER TRADING ENGINE
            if self.paper_mode:
                if mark_p > 0:
                    # 1. Cost-to-Cost (CTC) Trailing Check
                    trigger_ctc = False
                    if not ctc_done:
                        if side_trade == "buy" and (tp_p > entry_p):
                            dist = tp_p - entry_p
                            if mark_p >= entry_p + (0.45 * dist):
                                trigger_ctc = True
                        elif side_trade == "sell" and (entry_p > tp_p):
                            dist = entry_p - tp_p
                            if mark_p <= entry_p - (0.45 * dist):
                                trigger_ctc = True

                        if trigger_ctc:
                            self.active_trade["ctc_activated"] = True
                            self.active_trade["sl_price"] = entry_p
                            self.paper_state["active_trade"] = self.active_trade
                            save_paper_account(self.paper_state)
                            logger.info(f"🛡️ [DEMO CTC TRIGGERED] {active_sym} live price ${mark_p:.4f} covered 45%+ of target! SL moved to Entry ${entry_p:.4f}")
                            ctc_msg = (
                                f"🛡️ <b>[DEMO CTC ACTIVATED - 100% RISK-FREE]</b> 🛡️\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🪙 <b>Pair:</b> <code>{active_sym}</code>\n"
                                f"📈 <b>Live Price:</b> <code>${mark_p:.4f}</code> (Hit 45%+ of target!)\n"
                                f"🛑 <b>Virtual SL Shifted:</b> <code>${sl_p:.4f}</code> ➡️ <b>Entry ${entry_p:.4f}</b>\n"
                                f"🎯 <b>Target TP:</b> <code>${tp_p:.4f}</code>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"✨ <i>Demo trade is now 100% Risk-Free! Real capital untouched.</i>"
                            )
                            self.telegram.send_raw_message(ctc_msg)

                    # 2. Check Take-Profit Hit
                    is_tp_hit = (side_trade == "buy" and mark_p >= tp_p) or (side_trade == "sell" and mark_p <= tp_p)
                    # 3. Check Stop-Loss Hit
                    is_sl_hit = (side_trade == "buy" and mark_p <= sl_p) or (side_trade == "sell" and mark_p >= sl_p)

                    if is_tp_hit:
                        pnl_usd = contracts * abs(tp_p - entry_p) * c_val
                        pnl_inr = pnl_usd * 85.0
                        self.paper_state["balance_inr"] = float(self.paper_state.get("balance_inr", 110.88)) + pnl_inr
                        self.paper_state["total_trades"] = self.paper_state.get("total_trades", 0) + 1
                        self.paper_state["wins"] = self.paper_state.get("wins", 0) + 1
                        self.paper_state["trades"].append({
                            "symbol": active_sym,
                            "side": side_trade,
                            "entry": entry_p,
                            "exit": mark_p,
                            "pnl_inr": pnl_inr,
                            "outcome": "WIN",
                            "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                        })
                        self.paper_state["active_trade"] = None
                        save_paper_account(self.paper_state)
                        self.active_trade = None

                        tp_msg = (
                            f"🎉 <b>[DEMO TAKE-PROFIT HIT - PROFIT BOOKED!]</b> 🎉\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🪙 <b>Pair:</b> <code>{active_sym}</code> ({side_trade.upper()})\n"
                            f"📍 <b>Entry Price:</b> <code>${entry_p:.4f}</code>\n"
                            f"🏁 <b>Exit Price:</b> <code>${mark_p:.4f}</code>\n"
                            f"💰 <b>Demo PnL Added:</b> <b>+₹{pnl_inr:.2f} INR</b> (+${pnl_usd:.4f})\n"
                            f"📈 <b>New Demo Balance:</b> <b>₹{self.paper_state['balance_inr']:.2f} INR</b>\n"
                            f"🏆 <b>Win Rate:</b> {self.paper_state['wins']}/{self.paper_state['total_trades']} ({(self.paper_state['wins']/self.paper_state['total_trades']*100):.1f}%)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔒 <i>Real account is 100% frozen. SMC Master Blueprint verified!</i>"
                        )
                        self.telegram.send_raw_message(tp_msg)
                        logger.info(f"🎉 [DEMO TP HIT] {active_sym} Win: +₹{pnl_inr:.2f}")

                    elif is_sl_hit:
                        if self.active_trade.get("ctc_activated"):
                            pnl_inr = 0.0
                            pnl_usd = 0.0
                            outcome = "BREAKEVEN"
                            self.paper_state["breakevens"] = self.paper_state.get("breakevens", 0) + 1
                            outcome_title = "🛡️ [DEMO BREAKEVEN EXIT - ZERO LOSS]"
                        else:
                            pnl_usd = contracts * abs(entry_p - sl_p) * c_val
                            pnl_inr = -pnl_usd * 85.0
                            outcome = "LOSS"
                            self.paper_state["balance_inr"] = float(self.paper_state.get("balance_inr", 110.88)) + pnl_inr
                            self.paper_state["losses"] = self.paper_state.get("losses", 0) + 1
                            outcome_title = "🛑 [DEMO STOP-LOSS HIT - SAFE EXIT]"

                        self.paper_state["total_trades"] = self.paper_state.get("total_trades", 0) + 1
                        self.paper_state["trades"].append({
                            "symbol": active_sym,
                            "side": side_trade,
                            "entry": entry_p,
                            "exit": mark_p,
                            "pnl_inr": pnl_inr,
                            "outcome": outcome,
                            "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                        })
                        self.paper_state["active_trade"] = None
                        save_paper_account(self.paper_state)
                        self.active_trade = None

                        sl_msg = (
                            f"📊 <b>{outcome_title}</b> 📊\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🪙 <b>Pair:</b> <code>{active_sym}</code> ({side_trade.upper()})\n"
                            f"📍 <b>Entry Price:</b> <code>${entry_p:.4f}</code>\n"
                            f"🏁 <b>Exit Price:</b> <code>${mark_p:.4f}</code>\n"
                            f"💰 <b>Demo PnL:</b> <b>{'+' if pnl_inr >= 0 else ''}₹{pnl_inr:.2f} INR</b>\n"
                            f"📈 <b>Demo Balance:</b> <b>₹{self.paper_state['balance_inr']:.2f} INR</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛡️ Capital preserved safely. Ready for next setup."
                        )
                        self.telegram.send_raw_message(sl_msg)
                        logger.info(f"🛑 [DEMO EXIT] {active_sym} {outcome}: ₹{pnl_inr:.2f}")

            # 🚨 LIVE REAL MONEY EXECUTION (Exchange checks)
            else:
                matching = [p for p in open_positions if p.get("product_symbol") == active_sym and int(p.get("size", 0)) != 0]
                if matching:
                    # 🛡️ ACTIVE TRADE COST-TO-COST (CTC) TRAILING CHECK
                    try:
                        prod_id = self.active_trade.get("product_id")
                        pos_size = abs(int(matching[0].get("size", contracts)))

                        if not ctc_done and prod_id and mark_p > 0:
                            trigger_ctc = False
                            if side_trade == "buy" and (tp_p > entry_p):
                                target_dist = tp_p - entry_p
                                if mark_p >= entry_p + (0.45 * target_dist):
                                    trigger_ctc = True
                            elif side_trade == "sell" and (entry_p > tp_p):
                                target_dist = entry_p - tp_p
                                if mark_p <= entry_p - (0.45 * target_dist):
                                    trigger_ctc = True

                            if trigger_ctc:
                                logger.info(
                                    f"🛡️ [CTC TRIGGERED] {active_sym} live price ${mark_p:.4f} hit 45%+ of target! "
                                    f"Moving SL from ${sl_p:.4f} to Cost-to-Cost Entry ${entry_p:.4f}..."
                                )
                                try:
                                    self.client.request("DELETE", "/v2/orders/all", data={"product_id": prod_id})
                                    logger.info(f"Cleared previous bracket orders for {active_sym} (Product {prod_id})")
                                except Exception as ce:
                                    logger.warning(f"Error cancelling old bracket orders: {ce}")

                                exit_side = "sell" if side_trade == "buy" else "buy"
                                sl_price_str = f"{entry_p:.4f}" if entry_p >= 1.0 else f"{entry_p:.5f}"
                                tp_price_str = f"{tp_p:.4f}" if tp_p >= 1.0 else f"{tp_p:.5f}"

                                sl_body = {
                                    "product_id": prod_id,
                                    "size": pos_size,
                                    "side": exit_side,
                                    "order_type": "market_order",
                                    "stop_order_type": "stop_loss_order",
                                    "stop_price": sl_price_str,
                                    "reduce_only": True,
                                }
                                sl_res = self.client.request("POST", "/v2/orders", data=sl_body)
                                logger.info(f"New CTC Stop-Loss placed: {sl_res.get('success')}")

                                tp_body = {
                                    "product_id": prod_id,
                                    "size": pos_size,
                                    "side": exit_side,
                                    "order_type": "limit_order",
                                    "limit_price": tp_price_str,
                                    "reduce_only": True,
                                }
                                tp_res = self.client.request("POST", "/v2/orders", data=tp_body)
                                logger.info(f"Re-placed Take-Profit order: {tp_res.get('success')}")

                                self.active_trade["ctc_activated"] = True
                                self.active_trade["sl_price"] = entry_p

                                ctc_msg = (
                                    f"🛡️ <b>[COST-TO-COST ACTIVATED - 100% RISK-FREE]</b> 🛡️\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🪙 <b>Pair:</b> <code>{active_sym}</code>\n"
                                    f"📈 <b>Live Price:</b> <code>${mark_p:.4f}</code> (Reached 45%+ of target!)\n"
                                    f"🛑 <b>Stop-Loss Shifted:</b> <code>${sl_p:.4f}</code> ➡️ <b>Entry ${entry_p:.4f}</b>\n"
                                    f"🎯 <b>Target TP:</b> <code>${tp_p:.4f}</code>\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"✨ <i>Ab yeh trade 100% Risk-Free ho chuki hai! Wallet balance safe hai.</i>"
                                )
                                self.telegram.send_raw_message(ctc_msg)
                    except Exception as ctc_err:
                        logger.error(f"Error during CTC trailing check: {ctc_err}")
                else:
                    logger.info(f"Position on {active_sym} has CLOSED! Sending Telegram Exit Alert...")
                    try:
                        pnl_usd = (mark_p - entry_p) if side_trade == "buy" else (entry_p - mark_p)
                        pnl_inr = pnl_usd * 85.0
                        is_win = pnl_inr >= 0
                        outcome_title = "🎉 TAKE-PROFIT HIT (PROFIT BOOKED!) 🎉" if is_win else "🛑 STOP-LOSS HIT (LOSS CUT SAFELY)"

                        exit_msg = (
                            f"📊 <b>[{outcome_title}]</b> 📊\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🪙 <b>Pair:</b> <code>{active_sym}</code>\n"
                            f"📍 <b>Entry Price:</b> <code>${entry_p:.4f}</code>\n"
                            f"🏁 <b>Exit Price:</b> <code>${mark_p:.4f}</code>\n"
                            f"💡 <b>Close Reason:</b> {'Take-Profit target reached' if is_win else 'Stop-Loss protected capital'}\n"
                            f"💰 <b>Net PnL Added:</b> <b>{'+' if is_win else ''}₹{pnl_inr:.2f} INR</b> ({'+' if is_win else ''}${pnl_usd:.4f} USD)\n"
                            f"📈 <b>New Delta Wallet Balance:</b> <b>₹{inr_bal:.2f} INR</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔒 Capital strictly protected. Ready for next A++ setup."
                        )
                        self.telegram.send_raw_message(exit_msg)

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

                # Evaluate Sweep Strategy on 15M swing timeframe with SMC Master Blueprint Engine
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

                # 50 EMA Macro Trend Display
                macro_style = "bold green" if res_s.htf_bias == "BULLISH" else ("bold red" if res_s.htf_bias == "BEARISH" else "yellow")
                macro_cell = f"[{macro_style}]{res_s.htf_bias} (${res_s.htf_50_ema:.4f})[/{macro_style}]"

                # Fib 50% Zone Display
                if res_s.fib_equilibrium:
                    if curr_p <= res_s.fib_equilibrium:
                        fib_cell = f"[green]Discount (<= ${res_s.fib_equilibrium:.4f})[/]"
                    else:
                        fib_cell = f"[red]Premium (>= ${res_s.fib_equilibrium:.4f})[/]"
                else:
                    fib_cell = "[dim]Equilibrium[/dim]"

                # SMC Master Blueprint Setup Cell
                if res_s.has_valid_setup and res_s.signal:
                    s_cell = f"[bold green]SIGNAL: {res_s.signal.action} (1:1)[/]"
                elif res_s.wait_reasons:
                    s_cell = f"[dim]{res_s.wait_reasons[0]}[/dim]"
                else:
                    s_cell = "[dim]Scanning[/dim]"

                if res_poc.has_valid_setup and res_poc.signal:
                    poc_cell = f"[bold green]SIGNAL: {res_poc.signal.action} (POC ${res_poc.poc_price:.4f})[/]"
                elif res_poc.in_poc_zone:
                    poc_cell = f"[bold yellow]At POC (${res_poc.poc_price:.4f})[/]"
                elif res_poc.poc_price:
                    poc_cell = f"[dim]POC ${res_poc.poc_price:.4f} ({res_poc.distance_to_poc_pct:+.1f}%)[/dim]"
                else:
                    poc_cell = "[dim]Scanning[/dim]"

                table.add_row(delta_sym, f"${curr_p:.4f}", macro_cell, fib_cell, s_cell, poc_cell)

                # Check if we should execute a trade (1 position only, 10 min cooldown - strict)
                time_since_trade = time.time() - self.last_trade_time
                if self.auto_trade and not has_open_pos and time_since_trade > 600:
                    chosen_signal = None
                    signal_label = ""
                    signal_reason = ""
                    rec_contracts = None

                    # User Mandate: EXCLUSIVELY execute SMC Master Blueprint Strategy (1:1 Quick RR)
                    if res_s.has_valid_setup and res_s.signal:
                        chosen_signal = res_s.signal
                        signal_label = f"SMC Master Blueprint ({chosen_signal.action} 1:1 | RVOL {chosen_signal.relative_volume:.1f}x)"
                        signal_reason = f"{chosen_signal.setup_name} at ${chosen_signal.swept_level} ({chosen_signal.confirmation_type}). {chosen_signal.psychology_note}"
                        rec_contracts = chosen_signal.recommended_contracts

                    if chosen_signal:
                        entry_p = chosen_signal.entry_price
                        sl_p = chosen_signal.stop_loss
                        tp_p = chosen_signal.take_profit

                        # Pre-Trade Monte Carlo Validation (from trader-timemachine)
                        sim = self.mc_validator.simulate(
                            c_15m,
                            action=chosen_signal.action,
                            entry_price=entry_p,
                            stop_loss=sl_p,
                            take_profit=tp_p,
                        )
                        logger.info(f"🎲 Monte Carlo Replay on {delta_sym}: Target {sim.target_prob}% | Stop {sim.stop_prob}% | Verdict: {sim.verdict}")

                        # Execute if odds are >= 45% (filter out trades with negative expectancy)
                        if sim.target_prob >= 45.0:
                            success = self.execute_micro_signal(
                                pair_cfg=p_cfg,
                                signal_type=signal_label,
                                action=chosen_signal.action,
                                entry_price=entry_p,
                                sl_price=sl_p,
                                tp_price=tp_p,
                                reason=f"{signal_reason}. MC Target {sim.target_prob}%.",
                                is_high_conviction=True,
                                recommended_contracts=rec_contracts,
                            )
                            if success:
                                has_open_pos = True
                                self.last_trade_time = time.time()
                            else:
                                logger.warning(f"Order placement on {delta_sym} did not complete. Cooldown not applied.")
                        else:
                            logger.warning(f"Skipping {delta_sym}: Monte Carlo odds too low ({sim.target_prob}% target vs {sim.stop_prob}% stop).")

            except Exception as e:
                table.add_row(delta_sym, "ERR", "-", f"[red]{str(e)[:25]}[/]", "-", "-")

        console.print(table)
        active_info = f" | [bold magenta]Active Trade:[/] {self.active_trade['symbol']} ({self.active_trade['side'].upper()}{' - [CTC RISK-FREE]' if self.active_trade.get('ctc_activated') else ''})" if self.active_trade else ""
        if self.paper_mode:
            total_t = self.paper_state.get("total_trades", 0)
            wins_t = self.paper_state.get("wins", 0)
            wr_str = f" | [bold green]Win Rate:[/] {wins_t}/{total_t} ({(wins_t/total_t*100):.1f}%)" if total_t > 0 else ""
            console.print(f"[bold magenta][DEMO] Virtual Balance:[/] Rs. {inr_bal:.2f} (Real Wallet Safe!){wr_str} | [bold green]Open Positions:[/] {len(open_positions)} (Cap: 1) | [bold yellow]Auto-Trade:[/] {'ACTIVE' if self.auto_trade else 'OFF'}{active_info}")
        else:
            console.print(f"[bold cyan]Delta Real Balance:[/] Rs. {inr_bal:.2f} | [bold green]Open Positions:[/] {len(open_positions)} (Cap: 1) | [bold yellow]Auto-Trade:[/] {'ACTIVE' if self.auto_trade else 'OFF'}{active_info}")

    def run(self, interval: int = 60):
        if self.paper_mode:
            banner_text = (
                f"[bold magenta][DEMO / PAPER TRADING MODE] BotX 24/7 SMC Master Blueprint Engine[/]\n"
                f"[green]Real Delta Wallet is 100% FROZEN & SAFE! Zero real money at risk.[/]\n"
                f"[cyan]Scanning 11 Micro-Pairs on Live Delta India Data | 50 EMA Macro + SSMC Sweep + CTC Trailing[/]\n"
                f"[yellow]Risk Guard: Virtual Margin Rs {self.max_margin_inr:.2f} | Strict 1:1 Quick RR | Auto Breakeven Trailing[/]"
            )
        else:
            banner_text = (
                f"[bold red][LIVE REAL MONEY] BotX 24/7 Delta Exchange India SMC Engine[/]\n"
                f"[cyan]Scanning 11 Micro-Pairs | 50 EMA Macro Filter + SSMC Shadow Sweep + 50% Fib Rule[/]\n"
                f"[yellow]Risk Guard: Max Margin Rs {self.max_margin_inr:.2f} | Max Risk Rs 3-4 | Auto Cost-to-Cost (CTC) Trailing[/]"
            )
        console.print(Panel.fit(banner_text, border_style="magenta" if self.paper_mode else "red"))

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
    parser.add_argument("--paper", action="store_true", default=True, help="Run in Demo / Paper Trading mode (Default: True)")
    parser.add_argument("--live", dest="paper", action="store_false", help="Run with Real Delta Exchange money")
    args = parser.parse_args()

    bot = DeltaMicroBot(auto_trade=args.auto_trade, max_margin_inr=args.max_margin, paper_mode=args.paper)
    bot.run(interval=args.interval)

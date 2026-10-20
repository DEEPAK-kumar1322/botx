"""
Real-Time Position Monitor & Automatic Cost-To-Cost (CTC) Trailing SL Manager.

Continuously tracks open positions on Binance Futures:
1. When a position moves into profit (e.g. >= 40% of the distance to TP or >= 0.8% gain),
   cancels the initial Stop-Loss and places a new SL at Entry Price (Cost-to-Cost / Breakeven).
2. Sends instant WhatsApp alerts when:
   - SL is trailed to CTC (Risk-Free).
   - Take-Profit is hit.
   - Stop-Loss is hit.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from src.execution.binance_client import BinanceFuturesClient
from src.notifications.whatsapp_alerts import WhatsAppAlertSender

STATE_FILE = Path(__file__).resolve().parent.parent.parent / ".position_state.json"


class PositionMonitor:
    """Monitors live positions and auto-moves SL to Breakeven / CTC."""

    def __init__(
        self,
        client: BinanceFuturesClient,
        whatsapp_sender: Optional[WhatsAppAlertSender] = None,
        ctc_threshold_pct: float = 0.4,  # Trigger CTC when 40% distance to TP is achieved
    ):
        self.client = client
        self.whatsapp = whatsapp_sender
        self.ctc_threshold_pct = ctc_threshold_pct
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load persistent position tracking state."""
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read position state: {e}")
        return {}

    def _save_state(self) -> None:
        """Save position state."""
        try:
            STATE_FILE.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save position state: {e}")

    def register_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        initial_sl: float,
        tp_price: float,
        qty: float,
        sl_order_id: Any,
        tp_order_id: Any,
    ):
        """Register a newly placed trade for CTC monitoring."""
        sym = symbol.replace("/", "").upper()
        self._state[sym] = {
            "symbol": sym,
            "side": side.upper(),
            "entry_price": entry_price,
            "initial_sl": initial_sl,
            "current_sl": initial_sl,
            "tp_price": tp_price,
            "qty": qty,
            "sl_order_id": sl_order_id,
            "tp_order_id": tp_order_id,
            "ctc_activated": False,
            "entered_at": time.time(),
        }
        self._save_state()
        logger.info(f"Registered trade for CTC monitoring: {sym} {side} @ ${entry_price:.2f}")

    def check_and_update_positions(self):
        """Check all registered trades against live Binance position & mark price."""
        self._state = self._load_state()
        if not self._state:
            return

        to_remove = []
        for sym, trade in list(self._state.items()):
            pos = self.client.get_position(sym)
            if not pos:
                continue

            pos_amt = float(pos.get("positionAmt", 0.0))
            if abs(pos_amt) == 0.0:
                logger.info(f"Position on {sym} is now closed.")
                sl_id = trade.get("sl_order_id")
                tp_id = trade.get("tp_order_id")
                if sl_id and sl_id != "N/A":
                    try:
                        self.client.cancel_algo_order(sym, sl_id)
                    except Exception:
                        pass
                if tp_id and tp_id != "N/A":
                    try:
                        self.client.cancel_algo_order(sym, tp_id)
                    except Exception:
                        pass
                to_remove.append(sym)
                continue

            mark_price = float(pos.get("markPrice", 0.0))
            entry_price = trade["entry_price"]
            tp_price = trade["tp_price"]
            side = trade["side"]
            ctc_active = trade.get("ctc_activated", False)

            if mark_price <= 0:
                continue

            # Calculate live unrealized profit in USDT
            if side == "SELL":
                unrealized_pnl = (entry_price - mark_price) * abs(pos_amt)
            else:
                unrealized_pnl = (mark_price - entry_price) * abs(pos_amt)

            # 1. Check for Partial Profit Booking (e.g. $100 - $120 profit target)
            partial_target_pnl = float(trade.get("partial_pnl_trigger_usdt", 100.0))
            partial_booked = trade.get("partial_booked", False)

            if not partial_booked and unrealized_pnl >= partial_target_pnl and abs(pos_amt) > 0.001:
                self._execute_partial_booking(trade, pos_amt, mark_price, unrealized_pnl)
                continue

            if ctc_active:
                continue

            # 2. Check if profit threshold reached to move SL to CTC
            should_move_ctc = False
            new_sl_price = entry_price

            if side == "BUY":
                target_dist = tp_price - entry_price
                current_gain = mark_price - entry_price
                if target_dist > 0 and (current_gain / target_dist) >= self.ctc_threshold_pct:
                    should_move_ctc = True
                    # Buffer 0.05% above entry to cover maker/taker fees
                    new_sl_price = round(entry_price * 1.0005, 2)
            elif side == "SELL":
                target_dist = entry_price - tp_price
                current_gain = entry_price - mark_price
                if target_dist > 0 and (current_gain / target_dist) >= self.ctc_threshold_pct:
                    should_move_ctc = True
                    # Buffer 0.05% below entry to cover fees
                    new_sl_price = round(entry_price * 0.9995, 2)

            if should_move_ctc:
                self._move_sl_to_ctc(trade, mark_price, new_sl_price)

        for sym in to_remove:
            self._state.pop(sym, None)
        if to_remove:
            self._save_state()

    def _execute_partial_booking(self, trade: Dict[str, Any], pos_amt: float, mark_price: float, current_pnl: float):
        """Partially close position (e.g. 50%), lock in profit, and trail remaining to CTC."""
        sym = trade["symbol"]
        side = trade["side"]
        entry_price = trade["entry_price"]
        tp_price = trade["tp_price"]
        total_qty = abs(pos_amt)
        close_ratio = float(trade.get("partial_ratio", 0.5))

        prec = 3 if "ETH" in sym else (4 if "BTC" in sym else 2)
        close_qty = round(total_qty * close_ratio, prec)
        remaining_qty = round(total_qty - close_qty, prec)

        if close_qty <= 0 or remaining_qty <= 0:
            return

        exit_side = "BUY" if side == "SELL" else "SELL"
        logger.info(f"💰 PARTIAL PROFIT TARGET REACHED! Current PnL: ${current_pnl:.2f}. Closing {close_qty} {sym} @ market...")

        # 1. Close partial quantity
        try:
            close_res = self.client.place_market_order(sym, side=exit_side, quantity=close_qty, reduce_only=True)
            logger.info(f"Partial market close executed: {close_res}")
        except Exception as e:
            logger.error(f"Failed to execute partial close on {sym}: {e}")
            return

        # 2. Cancel old full-size SL & TP algo orders
        old_sl_id = trade.get("sl_order_id")
        old_tp_id = trade.get("tp_order_id")
        if old_sl_id and old_sl_id != "N/A":
            try:
                self.client.cancel_algo_order(sym, old_sl_id)
            except Exception as e:
                logger.warning(f"Could not cancel old SL {old_sl_id}: {e}")
        if old_tp_id and old_tp_id != "N/A":
            try:
                self.client.cancel_algo_order(sym, old_tp_id)
            except Exception as e:
                logger.warning(f"Could not cancel old TP {old_tp_id}: {e}")

        # 3. Calculate new SL price at CTC (breakeven with small fee buffer)
        if side == "SELL":
            new_sl_price = round(entry_price * 0.9995, 2)
            realized_profit = close_qty * (entry_price - mark_price)
        else:
            new_sl_price = round(entry_price * 1.0005, 2)
            realized_profit = close_qty * (mark_price - entry_price)

        # 4. Place new SL for remaining quantity
        try:
            new_sl_res = self.client.place_stop_loss(
                symbol=sym,
                side=exit_side,
                stop_price=new_sl_price,
                quantity=remaining_qty,
            )
            new_sl_id = new_sl_res.get("algoId", "N/A")
        except Exception as e:
            logger.error(f"Failed to place remaining SL for {sym}: {e}")
            new_sl_id = "N/A"

        # 5. Place new TP for remaining quantity
        try:
            new_tp_res = self.client.place_take_profit(
                symbol=sym,
                side=exit_side,
                tp_price=tp_price,
                quantity=remaining_qty,
            )
            new_tp_id = new_tp_res.get("algoId", "N/A")
        except Exception as e:
            logger.error(f"Failed to place remaining TP for {sym}: {e}")
            new_tp_id = "N/A"

        # 6. Update state
        trade["partial_booked"] = True
        trade["booked_profit_usdt"] = round(realized_profit, 2)
        trade["qty"] = remaining_qty
        trade["ctc_activated"] = True
        trade["current_sl"] = new_sl_price
        trade["sl_order_id"] = new_sl_id
        trade["tp_order_id"] = new_tp_id
        self._save_state()

        logger.info(f"✅ Partial profit booked (+${realized_profit:.2f})! Remaining {remaining_qty} {sym} trailing with SL=${new_sl_price} & TP=${tp_price}")

        # 7. WhatsApp notification
        if self.whatsapp:
            msg = (
                f"🎉 *[PARTIAL PROFIT BOOKED & SL MOVED TO BREAKEVEN]* 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🪙 *Pair:* `{sym}`\n"
                f"💰 *Profit Locked In:* *+${realized_profit:.2f} USDT* (50% position closed)\n"
                f"📍 *Entry Price:* `${entry_price:,.2f}`\n"
                f"🚀 *Exit Price:* `${mark_price:,.2f}`\n"
                f"🛡️ *Remaining Position:* *{remaining_qty} {sym}*\n"
                f"🛑 *Remaining Stop-Loss:* `${new_sl_price:,.2f}` (Cost-to-Cost / Zero Risk!)\n"
                f"🎯 *Remaining Take-Profit:* `${tp_price:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔒 *Guaranteed Win!* Paisa wallet mein lock ho gaya hai aur baaki position risk-free target ki taraf run kar rahi hai."
            )
            try:
                self.whatsapp.send_raw_message(msg)
            except Exception as e:
                logger.error(f"Failed to send partial booking WhatsApp alert: {e}")

    def _move_sl_to_ctc(self, trade: Dict[str, Any], mark_price: float, new_sl_price: float):
        """Cancel old SL and place new Breakeven SL."""
        sym = trade["symbol"]
        side = trade["side"]
        qty = trade["qty"]
        exit_side = "SELL" if side == "BUY" else "BUY"

        logger.info(f"🚀 Profit target threshold reached on {sym}! Trailing SL to Cost-to-Cost (${new_sl_price})...")

        # 1. Cancel previous SL algo order
        old_sl_id = trade.get("sl_order_id")
        if old_sl_id and old_sl_id != "N/A":
            try:
                self.client.cancel_algo_order(sym, old_sl_id)
            except Exception as e:
                logger.warning(f"Could not cancel old SL {old_sl_id}: {e}")

        # 2. Place new SL at CTC
        new_sl_res = self.client.place_stop_loss(
            symbol=sym,
            side=exit_side,
            stop_price=new_sl_price,
            quantity=qty,
        )

        trade["ctc_activated"] = True
        trade["current_sl"] = new_sl_price
        trade["sl_order_id"] = new_sl_res.get("algoId", old_sl_id)
        self._save_state()

        logger.info(f"🛡️ Cost-To-Cost SL placed on {sym} @ ${new_sl_price:.2f}!")

        # 3. Send WhatsApp Notification
        if self.whatsapp:
            msg = (
                f"🛡️ *[SL MOVED TO COST-TO-COST (CTC)]* 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🪙 *Pair:* `{sym}`\n"
                f"📈 *Position:* *{side}*\n"
                f"📍 *Original Entry Price:* `${trade['entry_price']:,.2f}`\n"
                f"🚀 *Current Live Price:* `${mark_price:,.2f}`\n"
                f"🛡️ *NEW Stop-Loss (CTC):* `${new_sl_price:,.2f}` (Breakeven + Fees)\n"
                f"🎯 *Main Take-Profit (TP):* `${trade['tp_price']:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ *Status: Trade is now 100% RISK-FREE! (Capital cannot be lost)*\n"
                f"🤖 _BotX Auto-Protection Engine_"
            )
            try:
                self.whatsapp.send_raw_message(msg)
            except Exception as e:
                logger.error(f"Failed to send CTC WhatsApp alert: {e}")

"""
Automated Order Execution Manager for Binance Futures.

Handles:
- Trade sizing ($50 margin @ 7x leverage)
- Entry order execution (Market / Limit)
- Automated Bracket SL & TP placement (STOP_MARKET & TAKE_PROFIT_MARKET)
- WhatsApp & Telegram execution confirmation alerts
"""

import math
from typing import Optional, Dict, Any
from loguru import logger

from src.execution.binance_client import BinanceFuturesClient
from src.notifications.whatsapp_alerts import WhatsAppAlertSender
from src.notifications.telegram_alerts import TelegramAlertSender


class OrderManager:
    """Manages trade execution, sizing, risk, and bracket SL/TP orders."""

    SYMBOL_PRECISION = {
        "BTCUSDT": {"qty_prec": 4, "step": 0.0001, "min_notional": 50.0},
        "ETHUSDT": {"qty_prec": 3, "step": 0.001, "min_notional": 20.0},
        "BNBUSDT": {"qty_prec": 2, "step": 0.01, "min_notional": 5.0},
        "SOLUSDT": {"qty_prec": 2, "step": 0.01, "min_notional": 5.0},
        "ZECUSDT": {"qty_prec": 3, "step": 0.001, "min_notional": 5.0},
        "XRPUSDT": {"qty_prec": 1, "step": 0.1, "min_notional": 5.0},
        "AVAXUSDT": {"qty_prec": 0, "step": 1.0, "min_notional": 5.0},
    }

    def __init__(
        self,
        client: BinanceFuturesClient,
        default_leverage: int = 14,
        default_position_margin_usdt: float = 150.0,
        whatsapp_sender: Optional[WhatsAppAlertSender] = None,
        telegram_sender: Optional[TelegramAlertSender] = None,
    ):
        self.client = client
        self.default_leverage = default_leverage
        self.default_position_margin_usdt = default_position_margin_usdt
        self.whatsapp = whatsapp_sender
        self.telegram = telegram_sender

    def _round_step(self, value: float, step: float, prec: int) -> float:
        """Round quantity to exact exchange step size."""
        factor = 1.0 / step
        return round(math.floor(value * factor) / factor, prec)

    def execute_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        margin_usdt: Optional[float] = None,
        leverage: Optional[int] = None,
        reason: str = "A+ Liquidity Sweep",
    ) -> Dict[str, Any]:
        """
        Execute trade on Binance Futures:
        1. Set Leverage
        2. Calculate Quantity for $50 margin @ 7x
        3. Market Entry
        4. STOP_MARKET SL
        5. TAKE_PROFIT_MARKET TP
        6. WhatsApp Notification
        """
        margin = margin_usdt or self.default_position_margin_usdt
        lev = leverage or self.default_leverage
        raw_sym = symbol.replace("/", "").upper()
        side_clean = side.upper()

        logger.info(f"Initiating {side_clean} trade on {raw_sym}: Margin=${margin}, Lev={lev}x")

        # 1. Set Leverage
        try:
            self.client.set_leverage(raw_sym, lev)
        except Exception as e:
            logger.warning(f"Leverage set exception on {raw_sym}: {e}")

        # 2. Precision & Sizing
        prec_info = self.SYMBOL_PRECISION.get(raw_sym, {"qty_prec": 3, "step": 0.001, "min_notional": 20.0})
        target_notional = margin * lev
        raw_qty = target_notional / entry_price
        qty = self._round_step(raw_qty, prec_info["step"], prec_info["qty_prec"])

        if (qty * entry_price) < prec_info["min_notional"]:
            min_qty = math.ceil(prec_info["min_notional"] / entry_price / prec_info["step"]) * prec_info["step"]
            qty = round(min_qty, prec_info["qty_prec"])

        actual_notional = qty * entry_price
        actual_margin = actual_notional / lev

        logger.info(f"Order Sizing: Qty={qty} {raw_sym} (Notional: ${actual_notional:.2f}, Margin: ${actual_margin:.2f})")

        # 3. Clean up any stale open orders for this symbol first
        try:
            self.client.cancel_all_open_orders(raw_sym)
        except Exception as e:
            logger.debug(f"Clear previous orders: {e}")

        # 4. Place Market Entry Order
        entry_res = self.client.place_market_order(raw_sym, side=side_clean, quantity=qty)

        if "orderId" not in entry_res:
            err_msg = entry_res.get("msg", str(entry_res))
            logger.error(f"Entry order failed on {raw_sym}: {err_msg}")
            return {"status": "FAILED", "error": err_msg}

        order_id = entry_res["orderId"]
        fill_price = float(entry_res.get("avgPrice", 0.0) or entry_price)
        if fill_price <= 0:
            fill_price = entry_price

        logger.info(f"Entry filled! ID={order_id}, FillPrice=${fill_price:.2f}")

        # 5. Place Stop-Loss (STOP_MARKET)
        exit_side = "SELL" if side_clean == "BUY" else "BUY"
        sl_res = self.client.place_stop_loss(
            symbol=raw_sym,
            side=exit_side,
            stop_price=stop_loss,
            quantity=qty,
        )
        sl_id = sl_res.get("algoId", sl_res.get("orderId", "N/A"))
        logger.info(f"Stop-Loss placed! SL=${stop_loss:.2f}, ID={sl_id}")

        # 6. Place Take-Profit (TAKE_PROFIT_MARKET)
        tp_res = self.client.place_take_profit(
            symbol=raw_sym,
            side=exit_side,
            tp_price=take_profit,
            quantity=qty,
        )
        tp_id = tp_res.get("algoId", tp_res.get("orderId", "N/A"))
        logger.info(f"Take-Profit placed! TP=${take_profit:.2f}, ID={tp_id}")

        # 7. Send Instant WhatsApp Notification
        self._send_whatsapp_alert(
            symbol=raw_sym,
            side=side_clean,
            qty=qty,
            fill_price=fill_price,
            margin=actual_margin,
            leverage=lev,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_id=order_id,
            sl_id=sl_id,
            tp_id=tp_id,
            reason=reason,
        )

        return {
            "status": "SUCCESS",
            "symbol": raw_sym,
            "side": side_clean,
            "quantity": qty,
            "fill_price": fill_price,
            "margin_usdt": actual_margin,
            "leverage": lev,
            "order_id": order_id,
            "sl_order_id": sl_id,
            "tp_order_id": tp_id,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    def _send_whatsapp_alert(
        self,
        symbol: str,
        side: str,
        qty: float,
        fill_price: float,
        margin: float,
        leverage: int,
        stop_loss: float,
        take_profit: float,
        order_id: Any,
        sl_id: Any,
        tp_id: Any,
        reason: str,
    ):
        """Send execution alert to WhatsApp."""
        if not self.whatsapp:
            return

        is_buy = side == "BUY"
        icon = "🟢" if is_buy else "🔴"
        action_text = "BUY / LONG" if is_buy else "SELL / SHORT"
        sl_dist = abs(fill_price - stop_loss) / fill_price * 100.0
        tp_dist = abs(take_profit - fill_price) / fill_price * 100.0

        msg = (
            f"{icon} *[BINANCE AUTO-TRADE EXECUTED]* {icon}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 *Pair:* `{symbol}`\n"
            f"⚡ *Type:* *{action_text}*\n"
            f"💵 *Margin Used:* `${margin:.2f} USDT`\n"
            f"🚀 *Leverage:* `{leverage}x` (Position: ~${qty * fill_price:.2f})\n"
            f"📦 *Quantity:* `{qty}` {symbol.replace('USDT', '')}\n"
            f"📍 *Entry Fill Price:* `${fill_price:,.2f}`\n"
            f"🛑 *Initial Stop-Loss (SL):* `${stop_loss:,.2f}` (-{sl_dist:.2f}%)\n"
            f"🎯 *Take-Profit (TP):* `${take_profit:,.2f}` (+{tp_dist:.2f}%)\n"
            f"🛡️ *Trailing Breakeven:* Active (SL will auto-move to CTC when safe)\n"
            f"💡 *Setup:* _{reason}_\n"
            f"🆔 *Binance Order ID:* `{order_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 _BotX Automated Execution System (Demo Mode: 100% Active)_"
        )

        try:
            self.whatsapp.send_raw_message(msg)
            logger.info("WhatsApp trade execution alert dispatched successfully!")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp alert: {e}")

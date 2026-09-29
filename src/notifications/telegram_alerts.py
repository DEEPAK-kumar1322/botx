"""
Dedicated Telegram Notification Module for Multi-Timeframe (15m & 1h) SMC Setups.

Formats and dispatches alerts for:
- Fair Value Gaps (FVG)
- Institutional Order Blocks (OB)
- Multi-Timeframe Consolidated Summaries

Directly uses the Telegram Bot API via requests.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
import requests
from loguru import logger

from src.config import config
from src.analysis.models import BiasType, FairValueGap, OrderBlock


class TelegramAlertSender:
    """
    Dispatches formatted trading strategy and SMC alerts to Telegram.
    Includes state-tracker anti-spam cooldown protection to prevent duplicate alert spam.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, cooldown_seconds: int = 1800):
        self.bot_token = bot_token or config.telegram_bot_token
        self.chat_id = chat_id or config.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.cooldown_seconds = cooldown_seconds
        # Setup State Tracker: Key = fingerprint, Value = timestamp of last dispatch
        self._dispatched_setups: Dict[str, float] = {}

    @property
    def is_ready(self) -> bool:
        """Verify bot credentials are configured."""
        return bool(self.bot_token and self.chat_id)

    def get_setup_fingerprint(
        self,
        symbol: str,
        strategy_id: str,
        action: str,
        price: float,
        timeframe: str
    ) -> str:
        """Generate normalized fingerprint for a trade setup to track its lifecycle."""
        # Price bucketed to roughly 0.25% to prevent spam on minor tick fluctuations
        bucket_factor = 10.0 if price > 1000 else 1.0
        price_bucket = round(price / bucket_factor) * bucket_factor
        return f"{symbol.upper()}_{strategy_id.lower()}_{action.upper()}_{price_bucket}_{timeframe.lower()}"

    def is_in_cooldown(self, fingerprint: str) -> Tuple[bool, float]:
        """Check if setup fingerprint is currently in cooldown window. Returns (is_cooling, remaining_seconds)."""
        now = time.time()
        last_time = self._dispatched_setups.get(fingerprint)
        if last_time is not None:
            elapsed = now - last_time
            if elapsed < self.cooldown_seconds:
                remaining = self.cooldown_seconds - elapsed
                return True, remaining
        return False, 0.0

    def record_dispatched_setup(self, fingerprint: str) -> None:
        """Record dispatched setup timestamp in the state tracker."""
        self._dispatched_setups[fingerprint] = time.time()

    def send_raw_message(self, html_text: str) -> bool:
        """Send formatted HTML message to the configured Telegram chat."""
        if not self.is_ready:
            logger.warning("[Telegram Alert] Bot token or Chat ID missing. Simulated dispatch mode.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("ok"):
                logger.info("Telegram alert dispatched successfully.")
                return True
            else:
                logger.error(f"Telegram API delivery failed: {data.get('description')}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to Telegram API: {e}")
            return False

    def send_strategy_execution_alert(
        self,
        symbol: str,
        strategy_name: str,
        strategy_id: str,
        action: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        risk_reward_ratio: str,
        timeframe: str,
        confluence_score: int,
        trigger_reason: str,
        directional_bias: str,
        force: bool = False
    ) -> Tuple[bool, str]:
        """
        Dispatches a high-probability strategy execution signal card to Telegram.
        Protected by anti-spam state-tracker cooldown.
        """
        fingerprint = self.get_setup_fingerprint(
            symbol=symbol,
            strategy_id=strategy_id,
            action=action,
            price=entry_price,
            timeframe=timeframe
        )

        is_cooling, remaining = self.is_in_cooldown(fingerprint)
        if is_cooling and not force:
            logger.info(
                f"[Telegram Cooldown] Alert suppressed for {fingerprint} "
                f"({int(remaining)}s remaining in cooldown window)."
            )
            return False, f"Cooldown active: Alert already sent ({int(remaining)}s left)"

        action_icon = "🟢 <b>BUY / LONG</b>" if action.upper() == "BUY" else "🔴 <b>SELL / SHORT</b>"
        bias_icon = "📈" if directional_bias.upper() == "BULLISH" else ("📉" if directional_bias.upper() == "BEARISH" else "⚖️")

        msg = (
            f"⚡ <b>BOTX STRATEGY EXECUTION SIGNAL</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Asset</b>: <code>{symbol}</code>\n"
            f"⏱️ <b>Timeframe</b>: <code>{timeframe.upper()}</code>\n"
            f"🧩 <b>Strategy</b>: <b>{strategy_name}</b>\n"
            f"🎯 <b>Action</b>: {action_icon}\n"
            f"🧭 <b>Structure Bias</b>: <b>{directional_bias}</b> {bias_icon}\n"
            f"💎 <b>Confluence Score</b>: <code>{confluence_score}% HIGH PROBABILITY</code>\n\n"
            f"📍 <b>PRECISION ORDER LEVELS</b>:\n"
            f"   • <b>Exact Entry</b>: <code>${entry_price:,.2f}</code>\n"
            f"   • <b>Stop Loss (SL)</b>: <code>${stop_loss:,.2f}</code>\n"
            f"   • <b>Take Profit 1</b>: <code>${take_profit_1:,.2f}</code>\n"
            f"   • <b>Take Profit 2</b>: <code>${take_profit_2:,.2f}</code>\n"
            f"   • <b>Risk:Reward Ratio</b>: <b>{risk_reward_ratio}</b>\n\n"
            f"🔍 <b>Trigger Confluence</b>:\n"
            f"   <i>{trigger_reason}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <i>Strict confluence verified by BotX Algorithmic Engine</i>\n"
            f"⏰ <code>{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}</code>"
        )

        sent = self.send_raw_message(msg)
        if sent or not self.is_ready:
            self.record_dispatched_setup(fingerprint)
            return True, "Alert dispatched successfully to Telegram"
        return False, "Failed to deliver Telegram message"

    def send_fvg_alert(self, symbol: str, timeframe: str, fvg: FairValueGap, current_price: float) -> bool:
        """Format and send a Fair Value Gap (FVG) alert message."""
        bias_icon = "🟢" if fvg.bias == BiasType.BULLISH else "🔴"
        status_text = "Active (Untested)" if not fvg.mitigated and not fvg.fully_filled else (
            "Partially Mitigated" if fvg.mitigated and not fvg.fully_filled else "Filled"
        )

        msg = (
            f"🚨 <b>BOTX SMC TRADING ALERT</b> 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Coin</b>: <code>{symbol}</code>\n"
            f"⏱️ <b>Timeframe</b>: <code>{timeframe.upper()}</code>\n"
            f"🎯 <b>Setup Type</b>: <b>Fair Value Gap (FVG)</b> {bias_icon}\n"
            f"🧭 <b>Bias</b>: <b>{fvg.bias.value}</b>\n"
            f"💰 <b>Current Price</b>: <code>${current_price:,.2f}</code>\n\n"
            f"📍 <b>Key Price Levels</b>:\n"
            f"   • <b>Zone Top</b>: <code>${fvg.top:,.2f}</code>\n"
            f"   • <b>Zone Bottom</b>: <code>${fvg.bottom:,.2f}</code>\n"
            f"   • <b>Gap Size</b>: <code>${fvg.gap_size:,.2f} ({fvg.gap_pct:.2f}%)</code>\n\n"
            f"📌 <b>Status</b>: <code>{status_text}</code>\n"
            f"⏰ <b>Displacement Time (UTC)</b>: <code>{fvg.timestamp.strftime('%Y-%m-%d %H:%M')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Powered by Botx Multi-Timeframe SMC Engine</i>"
        )
        return self.send_raw_message(msg)

    def send_order_block_alert(self, symbol: str, timeframe: str, ob: OrderBlock, current_price: float) -> bool:
        """Format and send an Institutional Order Block (OB) alert message."""
        bias_icon = "🟢" if ob.bias == BiasType.BULLISH else "🔴"
        status_text = "Active (Untested)" if not ob.mitigated and not ob.broken else (
            "Tested Zone" if ob.mitigated and not ob.broken else "Broken (Invalid)"
        )
        conf_text = "YES ⚡" if ob.has_confluence_fvg else "NO"

        msg = (
            f"🚨 <b>BOTX SMC TRADING ALERT</b> 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Coin</b>: <code>{symbol}</code>\n"
            f"⏱️ <b>Timeframe</b>: <code>{timeframe.upper()}</code>\n"
            f"🎯 <b>Setup Type</b>: <b>Institutional Order Block (OB)</b> {bias_icon}\n"
            f"🧭 <b>Bias</b>: <b>{ob.bias.value}</b>\n"
            f"💰 <b>Current Price</b>: <code>${current_price:,.2f}</code>\n\n"
            f"📍 <b>Key Price Levels</b>:\n"
            f"   • <b>Zone High</b>: <code>${ob.top:,.2f}</code>\n"
            f"   • <b>Zone Low</b>: <code>${ob.bottom:,.2f}</code>\n"
            f"   • <b>Displacement</b>: <code>{ob.displacement_pct:+.2f}%</code>\n"
            f"   • <b>FVG Confluence</b>: <code>{conf_text}</code>\n\n"
            f"📌 <b>Status</b>: <code>{status_text}</code>\n"
            f"⏰ <b>Block Candle Time (UTC)</b>: <code>{ob.timestamp.strftime('%Y-%m-%d %H:%M')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Powered by Botx Multi-Timeframe SMC Engine</i>"
        )
        return self.send_raw_message(msg)

    def send_mtf_summary_alert(
        self,
        symbol: str,
        res_15m: Dict[str, Any],
        res_1h: Dict[str, Any],
        current_price: float,
    ) -> bool:
        """Format and send a consolidated multi-timeframe executive summary."""
        active_fvg_15m = len([f for f in res_15m.get("fvgs", []) if not f.mitigated and not f.fully_filled])
        active_ob_15m = len([o for o in res_15m.get("obs", []) if not o.broken])
        active_fvg_1h = len([f for f in res_1h.get("fvgs", []) if not f.mitigated and not f.fully_filled])
        active_ob_1h = len([o for o in res_1h.get("obs", []) if not o.broken])

        msg = (
            f"📊 <b>BOTX MULTI-TIMEFRAME SMC SUMMARY</b> 📊\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Coin</b>: <code>{symbol}</code>\n"
            f"💰 <b>Current Price</b>: <code>${current_price:,.2f}</code>\n\n"
            f"⏱️ <b>15-Minute (15M) Analysis</b>:\n"
            f"   • Fair Value Gaps: <b>{len(res_15m.get('fvgs', []))}</b> ({active_fvg_15m} Active)\n"
            f"   • Order Blocks: <b>{len(res_15m.get('obs', []))}</b> ({active_ob_15m} Valid)\n\n"
            f"⏱️ <b>1-Hour (1H) Analysis</b>:\n"
            f"   • Fair Value Gaps: <b>{len(res_1h.get('fvgs', []))}</b> ({active_fvg_1h} Active)\n"
            f"   • Order Blocks: <b>{len(res_1h.get('obs', []))}</b> ({active_ob_1h} Valid)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Detailed individual setup alerts sent above.</i>"
        )
        return self.send_raw_message(msg)

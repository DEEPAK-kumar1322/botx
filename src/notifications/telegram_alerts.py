"""
Dedicated Telegram Notification Module for Multi-Timeframe (15m & 1h) SMC Setups.

Formats and dispatches alerts for:
- Fair Value Gaps (FVG)
- Institutional Order Blocks (OB)
- Multi-Timeframe Consolidated Summaries

Directly uses the Telegram Bot API via requests.
"""

from typing import Dict, Any, List, Optional
import requests
from loguru import logger

from src.config import config
from src.analysis.models import BiasType, FairValueGap, OrderBlock


class TelegramAlertSender:
    """Dispatches formatted Smart Money Concepts (SMC) alerts to Telegram."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or config.telegram_bot_token
        self.chat_id = chat_id or config.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    @property
    def is_ready(self) -> bool:
        """Verify bot credentials are configured."""
        return bool(self.bot_token and self.chat_id)

    def send_raw_message(self, html_text: str) -> bool:
        """Send formatted HTML message to the configured Telegram chat."""
        if not self.is_ready:
            logger.warning("[Telegram Alert] Bot token or Chat ID missing. Running in simulated mode.")
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

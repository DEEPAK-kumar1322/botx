"""
Telegram Alert Dispatcher for Botx AI Trading Engine.

Sends real-time trading setup notifications (FVGs, Order Blocks, Price Triggers)
via Telegram Bot API. Supports simulation/dry-run mode when credentials are not configured.
"""

from typing import Optional, Dict, Any
import requests
from loguru import logger

from src.config import config
from src.analysis.models import TechnicalSetup, BiasType, SetupType


class TelegramNotifier:
    """Telegram notification dispatcher with support for live delivery and dry-run fallback."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.bot_token = bot_token or config.telegram_bot_token
        self.chat_id = chat_id or config.telegram_chat_id
        self.enabled = config.telegram_enabled if enabled is None else enabled
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    @property
    def is_configured(self) -> bool:
        """Check if active Telegram bot token and chat ID are provided."""
        return bool(self.bot_token and self.chat_id and self.enabled)

    def test_connection(self) -> Dict[str, Any]:
        """Test Telegram Bot API connection using getMe."""
        if not self.bot_token:
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}

        try:
            url = f"{self.base_url}/getMe"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("ok"):
                username = data.get("result", {}).get("username", "Unknown")
                logger.info(f"Connected to Telegram bot: @{username}")
                return {"ok": True, "bot_username": username}
            else:
                return {"ok": False, "error": data.get("description", "Unknown API error")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a formatted text message to the target chat ID."""
        if not self.enabled:
            logger.debug("Telegram notifications are disabled in configuration.")
            return False

        if not self.is_configured:
            logger.warning("[Telegram DRY-RUN] Credentials not set. Simulated Message:\n" + text)
            return True

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            res_data = response.json()
            if res_data.get("ok"):
                logger.info("Telegram alert delivered successfully.")
                return True
            else:
                logger.error(f"Telegram API delivery failed: {res_data.get('description')}")
                return False
        except Exception as e:
            logger.error(f"Failed to dispatch Telegram message: {e}")
            return False

    def send_setup_alert(self, setup: TechnicalSetup) -> bool:
        """Format and dispatch a structured Smart Money Concept (SMC) alert."""
        bias_emoji = "🟢 BULLISH" if setup.bias == BiasType.BULLISH else "🔴 BEARISH"
        type_title = "FAIR VALUE GAP (FVG)" if setup.setup_type == SetupType.FAIR_VALUE_GAP else "INSTITUTIONAL ORDER BLOCK (OB)"

        # HTML formatting for Telegram
        html_msg = (
            f"⚡ <b>BOTX AI TRADING ENGINE ALERT</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Setup</b>: <code>{type_title}</code>\n"
            f"🧭 <b>Bias</b>: <b>{bias_emoji}</b>\n"
            f"🪙 <b>Symbol</b>: <code>{setup.symbol}</code> ({setup.timeframe})\n"
            f"💰 <b>Current Price</b>: <code>${setup.current_price:,.2f}</code>\n"
            f"📊 <b>Target Zone</b>:\n"
            f"   • High: <code>${setup.zone_high:,.2f}</code>\n"
            f"   • Low:  <code>${setup.zone_low:,.2f}</code>\n"
            f"📌 <b>Status</b>: <code>{setup.status}</code>\n"
            f"ℹ️ <b>Details</b>: {setup.details}\n"
            f"⏰ <b>Detected (UTC)</b>: <code>{setup.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Powered by Botx Smart Money Concepts Engine</i>"
        )

        return self.send_message(html_msg, parse_mode="HTML")

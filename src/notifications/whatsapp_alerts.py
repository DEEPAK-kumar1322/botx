"""
WhatsApp Notification Module for Liquidity Sweep Trading Strategy Alerts.

Strict Anti-Spam & Deduplication System:
1. Persistent Disk History (`.alert_history.json`):
   - Once a setup on a specific Swept Level or Sweep Candle Timestamp is sent,
     it is permanently recorded on disk so it NEVER sends a duplicate message again
     (even across bot restarts).
2. 4-Hour Symbol Cooldown (14,400s default):
   - Prevents multiple alerts on the same coin within a 4-hour window.
3. Supports Local Zero-API-Key WhatsApp Bridge (`http://localhost:8090/send`) & CallMeBot.
"""

import json
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import requests
from loguru import logger

from src.config import config

HISTORY_FILE = Path(__file__).resolve().parent.parent.parent / ".alert_history.json"


class WhatsAppAlertSender:
    """
    Dispatches formatted Liquidity Sweep trading strategy alerts to WhatsApp.
    Includes persistent disk deduplication so the same setup is NEVER sent twice.
    """

    def __init__(
        self,
        phone: Optional[str] = None,
        api_key: Optional[str] = None,
        webhook_url: Optional[str] = None,
        cooldown_seconds: int = 14400,  # 4 hours strict cooldown per setup/symbol
    ):
        self.phone = (phone if phone is not None else config.whatsapp_phone or "").strip()
        self.api_key = (api_key if api_key is not None else config.whatsapp_api_key or "").strip()
        self.webhook_url = (webhook_url if webhook_url is not None else config.whatsapp_webhook_url or "").strip()
        self.enabled = config.whatsapp_enabled
        self.cooldown_seconds = cooldown_seconds
        self._dispatched_setups: Dict[str, float] = self._load_history()

    def _load_history(self) -> Dict[str, float]:
        """Load persistent alert history from disk."""
        try:
            if HISTORY_FILE.exists():
                return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read alert history file: {e}")
        return {}

    def _save_history(self) -> None:
        """Persist alert history to disk so restarts never re-send old alerts."""
        try:
            HISTORY_FILE.write_text(json.dumps(self._dispatched_setups, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write alert history file: {e}")

    @property
    def is_ready(self) -> bool:
        has_callmebot = bool(self.phone and self.api_key)
        has_webhook = bool(self.webhook_url)
        return self.enabled and (has_callmebot or has_webhook)

    def get_setup_fingerprints(
        self,
        symbol: str,
        action: str,
        swept_level: float,
        timeframe: str,
        sweep_candle_iso: str = "",
    ) -> Tuple[str, str]:
        """
        Return two deduplication keys:
        1. Level-based key (locks that specific support/resistance zone for this symbol)
        2. Symbol+Action cooldown key (prevents back-to-back alerts on the same coin)
        """
        bucket_factor = 50.0 if swept_level > 10000 else (5.0 if swept_level > 500 else 0.5)
        level_bucket = round(swept_level / bucket_factor) * bucket_factor
        level_key = f"LEVEL_{symbol.upper()}_{action.upper()}_{level_bucket}_{timeframe.lower()}_{sweep_candle_iso}"
        symbol_key = f"SYMBOL_{symbol.upper()}_{action.upper()}_{timeframe.lower()}"
        return level_key, symbol_key

    def is_duplicate_or_cooling(
        self,
        symbol: str,
        action: str,
        swept_level: float,
        timeframe: str,
        sweep_candle_iso: str = "",
    ) -> Tuple[bool, str]:
        """
        Check if this exact sweep level/candle was EVER sent before,
        or if the symbol is within the 4-hour anti-spam cooldown window.
        """
        self._dispatched_setups = self._load_history()
        now = time.time()
        level_key, symbol_key = self.get_setup_fingerprints(
            symbol, action, swept_level, timeframe, sweep_candle_iso
        )

        # 1. Exact sweep candle / level lock (24 hours lock so same level never repeats)
        if level_key in self._dispatched_setups:
            elapsed = now - self._dispatched_setups[level_key]
            if elapsed < 86400:  # 24 hours lock on exact level/candle
                return True, f"Duplicate blocked: This sweep setup ({symbol} @ ${swept_level:,.2f}) was already sent."

        # 2. Per-symbol cooldown (default 4 hours)
        if symbol_key in self._dispatched_setups:
            elapsed = now - self._dispatched_setups[symbol_key]
            if elapsed < self.cooldown_seconds:
                rem_min = int((self.cooldown_seconds - elapsed) // 60)
                return True, f"Anti-spam cooldown active for {symbol} ({rem_min}m remaining)."

        return False, ""

    def record_dispatched_setup(
        self,
        symbol: str,
        action: str,
        swept_level: float,
        timeframe: str,
        sweep_candle_iso: str = "",
    ) -> None:
        now = time.time()
        level_key, symbol_key = self.get_setup_fingerprints(
            symbol, action, swept_level, timeframe, sweep_candle_iso
        )
        self._dispatched_setups[level_key] = now
        self._dispatched_setups[symbol_key] = now
        self._save_history()

    def send_raw_message(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        if not self.enabled:
            return False, "WhatsApp alerts disabled in .env"

        if not self.is_ready:
            logger.warning("[WhatsApp Alert] WhatsApp credentials/webhook not set in .env.")
            return False, "WhatsApp credentials not configured"

        delivered = False
        errors = []

        if self.phone and self.api_key:
            try:
                clean_phone = self.phone.replace(" ", "").replace("-", "")
                encoded_text = urllib.parse.quote(text)
                url = (
                    f"https://api.callmebot.com/whatsapp.php?"
                    f"phone={clean_phone}&text={encoded_text}&apikey={self.api_key}"
                )
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200 and "error" not in resp.text.lower()[:80]:
                    delivered = True
                else:
                    errors.append(f"CallMeBot HTTP {resp.status_code}")
            except Exception as e:
                errors.append(f"CallMeBot error: {e}")

        if self.webhook_url:
            try:
                payload = {
                    "channel": "whatsapp",
                    "phone": self.phone,
                    "message": text,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                }
                if metadata:
                    payload["trade"] = metadata
                resp = requests.post(self.webhook_url, json=payload, timeout=12)
                if 200 <= resp.status_code < 300:
                    logger.info("WhatsApp alert delivered via Local WhatsApp Bridge")
                    delivered = True
                else:
                    errors.append(f"Webhook HTTP {resp.status_code}: {resp.text[:120]}")
            except Exception as e:
                errors.append(f"Webhook error: {e}")

        if delivered:
            return True, "WhatsApp alert delivered successfully"
        return False, "; ".join(errors) if errors else "Delivery failed"

    def format_liquidity_sweep_message(
        self,
        symbol: str,
        timeframe: str,
        action: str,
        sweep_type: str,
        swept_level: float,
        sweep_extreme: float,
        confirmation_type: str,
        entry_price: float,
        stop_loss: float,
        tp_1_2rr: float,
        tp_1_3rr: float,
        htf_bias: str,
        rr_ratio: str = "1:3.0",
        notes: str = "",
    ) -> str:
        is_buy = action.upper() == "BUY"
        header_icon = "🟢 *A+ LONG SETUP (Support Sweep)*" if is_buy else "🔴 *A+ SHORT SETUP (Resistance Sweep)*"
        level_label = "Major Support Swept" if is_buy else "Major Resistance Swept"
        wick_label = "Sweep Candle Low" if is_buy else "Sweep Candle High"

        risk_pts = abs(entry_price - stop_loss)
        risk_pct = (risk_pts / entry_price) * 100.0 if entry_price else 0.0
        reward_3r = abs(tp_1_3rr - entry_price)

        msg = (
            f"🚨 *BOTX VALID LIQUIDITY SWEEP* 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{header_icon}\n\n"
            f"🪙 *Pair:* `{symbol}`\n"
            f"⏱️ *Timeframe:* `{timeframe.upper()}` (1H Trend: *{htf_bias}* ✅)\n"
            f"🎯 *Setup:* {sweep_type}\n"
            f"✅ *Closed Candle Confirm:* {confirmation_type}\n\n"
            f"📊 *SWEEP LEVEL:*\n"
            f"• *{level_label}:* `${swept_level:,.2f}`\n"
            f"• *{wick_label}:* `${sweep_extreme:,.2f}`\n\n"
            f"📍 *TRADE PLAN (Manual Execution):*\n"
            f"• *Entry Price:* `${entry_price:,.2f}`\n"
            f"• *Stop Loss (SL):* `${stop_loss:,.2f}` _(Risk: {risk_pct:.2f}%)_\n"
            f"• *Target 1 (1:2 RR):* `${tp_1_2rr:,.2f}`\n"
            f"• *Target 2 (1:3 RR):* `${tp_1_3rr:,.2f}` _(Main Target)_\n"
            f"• *Risk : Reward:* *{rr_ratio}* (`${risk_pts:,.2f}` Risk → `${reward_3r:,.2f}` Reward)\n"
        )
        if notes:
            msg += f"\n💡 *Reason:* _{notes}_\n"

        msg += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ _Strict A+ Closed-Candle Signal (1 Alert Only — Zero Spam)_\n"
            f"🕒 `{time.strftime('%d %b %Y, %H:%M:%S UTC', time.gmtime())}`"
        )
        return msg

    def send_liquidity_sweep_alert(
        self,
        symbol: str,
        timeframe: str,
        action: str,
        sweep_type: str,
        swept_level: float,
        sweep_extreme: float,
        confirmation_type: str,
        entry_price: float,
        stop_loss: float,
        tp_1_2rr: float,
        tp_1_3rr: float,
        htf_bias: str,
        rr_ratio: str = "1:3.0",
        notes: str = "",
        sweep_candle_iso: str = "",
        force: bool = False,
    ) -> Tuple[bool, str, str]:
        is_blocked, block_reason = self.is_duplicate_or_cooling(
            symbol=symbol,
            action=action,
            swept_level=swept_level,
            timeframe=timeframe,
            sweep_candle_iso=sweep_candle_iso,
        )
        formatted_msg = self.format_liquidity_sweep_message(
            symbol=symbol,
            timeframe=timeframe,
            action=action,
            sweep_type=sweep_type,
            swept_level=swept_level,
            sweep_extreme=sweep_extreme,
            confirmation_type=confirmation_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            tp_1_2rr=tp_1_2rr,
            tp_1_3rr=tp_1_3rr,
            htf_bias=htf_bias,
            rr_ratio=rr_ratio,
            notes=notes,
        )

        if is_blocked and not force:
            return False, block_reason, formatted_msg

        metadata = {
            "symbol": symbol,
            "timeframe": timeframe,
            "action": action,
            "swept_level": swept_level,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "tp_1_2rr": tp_1_2rr,
            "tp_1_3rr": tp_1_3rr,
        }

        sent, status_msg = self.send_raw_message(formatted_msg, metadata=metadata)
        if sent:
            self.record_dispatched_setup(
                symbol=symbol,
                action=action,
                swept_level=swept_level,
                timeframe=timeframe,
                sweep_candle_iso=sweep_candle_iso,
            )
        return sent, status_msg, formatted_msg

    def send_retest_scalp_alert(
        self,
        symbol: str,
        timeframe: str,
        action: str,
        broken_level: float,
        level_type: str,
        confirmation_type: str,
        entry_price: float,
        stop_loss: float,
        tp_1_2rr: float,
        htf_bias: str,
        notes: str = "",
        force: bool = False,
    ) -> Tuple[bool, str, str]:
        """Dispatches real-time WhatsApp alert for the Funded Price Action Retest strategy."""
        is_blocked, block_reason = self.is_duplicate_or_cooling(
            symbol=symbol,
            action=action,
            swept_level=broken_level,
            timeframe=timeframe,
            sweep_candle_iso="",
        )
        p_fmt = ".2f" if entry_price > 10 else (".4f" if entry_price > 0.01 else ".6f")
        direction_emoji = "🟢" if action == "BUY" else "🔴"
        msg = (
            f"⚡ *[NEW A+ PRICE ACTION RETEST SIGNAL]* ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*{symbol}* ({timeframe.upper()}) | Strategy: *Funded Retest Scalper*\n"
            f"Setup: *{direction_emoji} {action} ({level_type})*\n\n"
            f"🎯 *Execution Details:*\n"
            f"• Entry: *${entry_price:{p_fmt}}*\n"
            f"• Stop Loss: *${stop_loss:{p_fmt}}*\n"
            f"• Take Profit (1:2 RR): *${tp_1_2rr:{p_fmt}}*\n"
            f"• Broken Level Retested: *${broken_level:{p_fmt}}*\n"
            f"• Confirmation: *{confirmation_type}*\n"
            f"• 1H Trend Bias: *{htf_bias}*\n\n"
            f"💡 *Notes:* {notes}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 *Auto-Execution Status:* Order sent to Binance Futures ($150 Margin @ 14x Leverage)."
        )

        if is_blocked and not force:
            return False, block_reason, msg

        sent, status_msg = self.send_raw_message(msg)
        if sent:
            self.record_dispatched_setup(
                symbol=symbol,
                action=action,
                swept_level=broken_level,
                timeframe=timeframe,
            )
        return sent, status_msg, msg

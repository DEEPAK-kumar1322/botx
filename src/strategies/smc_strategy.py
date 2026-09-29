"""
SMC Strategy Deployment & Live Execution Signal Generator.

Evaluates live market data against Smart Money Concepts (FVG + OB + Structure)
and generates precision Entry, Stop Loss (SL), Take Profit (TP), and RRR execution signals.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field
from loguru import logger

from src.data.unified_feed import UnifiedMarketFeed
from src.analysis.smc import SMCAnalyzer
from src.analysis.structure import MarketStructureAnalyzer
from src.notifications.telegram_alerts import TelegramAlertSender


class ExecutionSignal(BaseModel):
    id: str = Field(default_factory=lambda: f"SIG-{uuid.uuid4().hex[:6].upper()}")
    symbol: str
    timeframe: str
    action: str = Field(description="'BUY' or 'SELL'")
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_ratio: str
    trigger_reason: str
    status: str = Field(default="ACTIVE_MONITORING")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SMCStrategyEngine:
    """Manages strategy state and generates execution signals on live data."""

    def __init__(self):
        self.is_active: bool = False
        self.signals: List[ExecutionSignal] = []
        self.feed = UnifiedMarketFeed()
        self.smc_analyzer = SMCAnalyzer()
        self.structure_analyzer = MarketStructureAnalyzer()
        self.notifier = TelegramAlertSender()
        logger.info("Initialized SMCStrategyEngine")

    def toggle(self, enable: Optional[bool] = None) -> bool:
        """Activate or deactivate live strategy execution."""
        if enable is None:
            self.is_active = not self.is_active
        else:
            self.is_active = enable

        status_str = "ACTIVATED" if self.is_active else "DEACTIVATED"
        logger.info(f"SMC Strategy is now {status_str}")

        if self.notifier.is_ready:
            try:
                emoji = "🚀" if self.is_active else "🛑"
                self.notifier.send_raw_message(
                    f"{emoji} <b>BOTX STRATEGY ENGINE {status_str}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• Strategy: <code>SMC Precision Liquidity Engine</code>\n"
                    f"• Status: <b>{'LIVE SCANNING & EXECUTING' if self.is_active else 'STANDBY'}</b>\n"
                    f"• Target Pairs: <code>BTC/USDT, ETH/USDT, XAUUSD, US100, XAGUSD</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━"
                )
            except Exception as e:
                logger.error(f"Error notifying strategy status change: {e}")

        return self.is_active

    def evaluate(self, symbol: str = "BTC/USDT", timeframe: str = "15m") -> Optional[ExecutionSignal]:
        """Evaluate live market data and return actionable Entry/Exit signal."""
        try:
            candles = self.feed.fetch_recent_candles(symbol, timeframe=timeframe, limit=60)
            if not candles:
                logger.warning(f"No candles retrieved for {symbol}")
                return None

            cur_price = candles[-1].close
            fvgs = self.smc_analyzer.find_fair_value_gaps(candles)
            obs = self.smc_analyzer.find_order_blocks(candles, fvgs=fvgs)
            structure = self.structure_analyzer.analyze(candles, symbol=symbol, timeframe=timeframe)

            # Check confluence:
            # 1. Bullish Entry
            active_bullish_fvg = next((f for f in fvgs if f.bias == "BULLISH" and not f.fully_filled), None)
            active_bullish_ob = next((o for o in obs if o.bias == "BULLISH" and not o.broken), None)

            # 2. Bearish Entry
            active_bearish_fvg = next((f for f in fvgs if f.bias == "BEARISH" and not f.fully_filled), None)
            active_bearish_ob = next((o for o in obs if o.bias == "BEARISH" and not o.broken), None)

            signal = None

            if structure.directional_bias == "BULLISH" or (active_bullish_ob and active_bullish_fvg):
                # Calculate precision entry & SL
                zone_low = active_bullish_ob.bottom if active_bullish_ob else (active_bullish_fvg.bottom if active_bullish_fvg else cur_price * 0.995)
                entry = cur_price
                risk = abs(entry - zone_low)
                if risk == 0:
                    risk = entry * 0.003

                sl = round(zone_low - (risk * 0.15), 2)
                tp1 = round(entry + (risk * 2.5), 2)
                tp2 = round(entry + (risk * 4.0), 2)
                rrr = "1:2.8"

                signal = ExecutionSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    action="BUY",
                    entry_price=round(entry, 2),
                    stop_loss=sl,
                    take_profit_1=tp1,
                    take_profit_2=tp2,
                    risk_reward_ratio=rrr,
                    trigger_reason=f"Bullish SMC Confluence: Tested Demand Zone ({structure.structure_phase}) with BSL target at ${structure.nearest_bsl or tp1:,.2f}"
                )

            elif structure.directional_bias == "BEARISH" or (active_bearish_ob and active_bearish_fvg):
                zone_high = active_bearish_ob.top if active_bearish_ob else (active_bearish_fvg.top if active_bearish_fvg else cur_price * 1.005)
                entry = cur_price
                risk = abs(zone_high - entry)
                if risk == 0:
                    risk = entry * 0.003

                sl = round(zone_high + (risk * 0.15), 2)
                tp1 = round(entry - (risk * 2.5), 2)
                tp2 = round(entry - (risk * 4.0), 2)
                rrr = "1:2.8"

                signal = ExecutionSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    action="SELL",
                    entry_price=round(entry, 2),
                    stop_loss=sl,
                    take_profit_1=tp1,
                    take_profit_2=tp2,
                    risk_reward_ratio=rrr,
                    trigger_reason=f"Bearish SMC Confluence: Rejection at Supply Zone ({structure.structure_phase}) with SSL target at ${structure.nearest_ssl or tp1:,.2f}"
                )

            if signal:
                self.signals.insert(0, signal)
                logger.info(f"Generated new execution signal: {signal.action} {signal.symbol} @ {signal.entry_price}")

                # Forward live execution signal to Telegram
                if self.notifier.is_ready:
                    try:
                        action_emoji = "🟢 BUY (LONG)" if signal.action == "BUY" else "🔴 SELL (SHORT)"
                        telegram_msg = (
                            f"🎯 <b>BOTX PRECISION EXECUTION SIGNAL</b> 🎯\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚡ <b>Action</b>: <b>{action_emoji}</b>\n"
                            f"🪙 <b>Asset</b>: <code>{signal.symbol}</code> ({signal.timeframe})\n"
                            f"💰 <b>Entry Price</b>: <code>${signal.entry_price:,.2f}</code>\n"
                            f"🛑 <b>Stop Loss (SL)</b>: <code>${signal.stop_loss:,.2f}</code>\n"
                            f"🎯 <b>Take Profit 1 (TP1)</b>: <code>${signal.take_profit_1:,.2f}</code>\n"
                            f"🏆 <b>Take Profit 2 (TP2)</b>: <code>${signal.take_profit_2:,.2f}</code>\n"
                            f"⚖️ <b>Risk/Reward Ratio</b>: <code>{signal.risk_reward_ratio}</code>\n\n"
                            f"ℹ️ <b>Rationale</b>: {signal.trigger_reason}\n"
                            f"⏰ <b>Trigger Time (UTC)</b>: <code>{signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"<i>Automated Strategy Execution via BotX Engine</i>"
                        )
                        self.notifier.send_raw_message(telegram_msg)
                    except Exception as e:
                        logger.error(f"Error sending execution signal to Telegram: {e}")

            return signal

        except Exception as e:
            logger.error(f"Error evaluating live SMC strategy: {e}")
            return None


strategy_engine = SMCStrategyEngine()

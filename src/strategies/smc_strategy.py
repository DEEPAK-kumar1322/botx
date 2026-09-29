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


from src.strategies.strategy_engine import strategy_manager


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
        logger.info("Initialized SMCStrategyEngine with Global Sniper Mode Gate")

    def toggle(self, enable: Optional[bool] = None) -> bool:
        """Activate or deactivate live strategy execution."""
        if enable is None:
            self.is_active = not self.is_active
        else:
            self.is_active = enable

        strategy_manager.set_active_strategy("smc", enable=self.is_active)
        status_str = "ACTIVATED" if self.is_active else "DEACTIVATED"
        logger.info(f"SMC Strategy is now {status_str}")

        if self.notifier.is_ready:
            try:
                emoji = "🚀" if self.is_active else "🛑"
                self.notifier.send_raw_message(
                    f"{emoji} <b>BOTX STRATEGY ENGINE {status_str}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• Strategy: <code>SMC Precision Liquidity Engine</code>\n"
                    f"• Status: <b>{'LIVE SNIPER SCANNING' if self.is_active else 'STANDBY'}</b>\n"
                    f"• Quality Gate: <b>100% Strict Sniper Mode (4 Conditions)</b>\n"
                    f"• Target Pairs: <code>BTC/USDT, ETH/USDT, XAUUSD, US100, XAGUSD</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━"
                )
            except Exception as e:
                logger.error(f"Error notifying strategy status change: {e}")

        return self.is_active

    def evaluate(self, symbol: str = "BTC/USDT", timeframe: str = "15m") -> Optional[ExecutionSignal]:
        """
        Evaluate live market data through the Global Sniper Mode validator.
        Returns an ExecutionSignal ONLY if 100% of Sniper Mode conditions are met simultaneously:
        1. Liquidity Sweep First (BSL/SSL Purge)
        2. Strong Displacement & CHoCH (FVG Imbalance)
        3. Deep Mitigation (Discount/Premium Array)
        4. Higher Timeframe Alignment (15m + 1H + 4H)

        If even ONE condition fails, returns None (STANDBY / ZERO signals).
        """
        try:
            analysis = strategy_manager.run_strategy_analysis(symbol=symbol, timeframe=timeframe, strategy_id="smc")
            if not analysis.has_entry or not analysis.entry_zone:
                logger.info(
                    f"Sniper Mode Gate: Zero execution signal for {symbol} on {timeframe}. "
                    f"Standby enforced. Missing criteria: {', '.join(analysis.wait_reasons)}"
                )
                return None

            ez = analysis.entry_zone
            signal = ExecutionSignal(
                symbol=symbol,
                timeframe=timeframe,
                action=ez.action,
                entry_price=ez.entry,
                stop_loss=ez.stop_loss,
                take_profit_1=ez.take_profit_1,
                take_profit_2=ez.take_profit_2,
                risk_reward_ratio=ez.risk_reward_ratio,
                trigger_reason=f"Sniper A+ Setup: {analysis.strategy_name} verified with Sweep, CHoCH, Deep Mitigation, and 1H/4H Alignment."
            )

            self.signals.insert(0, signal)
            if len(self.signals) > 30:
                self.signals.pop()

            logger.info(f"Sniper Mode: 100% Confirmed Execution Signal Generated: {signal.action} {signal.symbol} @ {signal.entry_price}")
            return signal

        except Exception as e:
            logger.error(f"Error evaluating live SMC strategy with Sniper Mode: {e}")
            return None


strategy_engine = SMCStrategyEngine()

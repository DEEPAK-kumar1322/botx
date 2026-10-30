"""
Enhanced Liquidity Sweep & Master Blueprint Engine (BotX).
Synchronized with 'Smart Money Concepts & Price Action Master Blueprint'.

Enforces:
1. 50 EMA Macro Structure Filter (1H/4H).
2. SSMC Shadow Sweep (Wick Sweep vs Body Close Invalidation).
3. Fibonacci 50% Rule (Discount for Longs, Premium for Shorts).
4. 3-Candle Fair Value Gap (FVG) and Order Block validation.
5. Candlestick Classification confirmation (Pin Bar / Hammer / Engulfing).
6. Handwritten Capital Math & Risk Control.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.data.base import CandleData
from src.strategies.master_blueprint_engine import (
    MasterBlueprintEngine,
    BlueprintSignal,
    BlueprintEvaluation,
    calculate_ema,
)

# Re-export for seamless backward compatibility
EnhancedSweepSignal = BlueprintSignal
EnhancedSweepEvaluation = BlueprintEvaluation


class EnhancedSweepAnalyzer:
    """
    Adapter class connecting MasterBlueprintEngine to BotX systems.
    """

    def __init__(
        self,
        swing_window: int = 5,
        min_rvol: float = 1.05,
        max_chase_r: float = 0.45,
    ):
        self.engine = MasterBlueprintEngine(
            swing_window=swing_window,
            min_rvol=min_rvol,
            max_chase_r=max_chase_r,
        )
        self.min_rvol = min_rvol

    def evaluate(
        self,
        candles_ltf: List[CandleData],
        candles_htf: List[CandleData],
        symbol: str = "BTC/USDT",
        timeframe: str = "15m",
        max_loss_inr: float = 4.0,
        contract_multiplier: float = 1.0,
        leverage: float = 10.0,
        inr_per_usd: float = 85.0,
        allow_counter_trend: bool = False,
    ) -> BlueprintEvaluation:
        return self.engine.evaluate(
            candles_ltf=candles_ltf,
            candles_htf=candles_htf,
            symbol=symbol,
            timeframe=timeframe,
            capital_inr=110.0,
            risk_pct=0.035,
            max_loss_inr=max_loss_inr,
            contract_multiplier=contract_multiplier,
            leverage=leverage,
            inr_per_usd=inr_per_usd,
            allow_counter_trend=allow_counter_trend,
        )

"""
Market Structure & Liquidity Analyzer (SMC).

Identifies:
1. Swing Points: Higher Highs (HH), Higher Lows (HL), Lower Highs (LH), Lower Lows (LL).
2. Directional Bias: Bullish, Bearish, or Ranging with confidence & rationale.
3. Liquidity Levels:
   - Buy-Side Liquidity (BSL) / Swing Highs
   - Sell-Side Liquidity (SSL) / Swing Lows
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import numpy as np

from src.data.base import CandleData


class SwingPoint(BaseModel):
    index: int
    timestamp: datetime
    price: float
    point_type: str = Field(description="'HIGH' or 'LOW'")
    label: str = Field(description="'HH', 'HL', 'LH', 'LL'")


class LiquidityLevel(BaseModel):
    level_type: str = Field(description="'BSL' (Buy Side Liquidity) or 'SSL' (Sell Side Liquidity)")
    price: float
    timestamp: datetime
    description: str
    distance_pct: float


class StructureAnalysisResult(BaseModel):
    symbol: str
    timeframe: str
    current_price: float
    directional_bias: str = Field(description="'BULLISH', 'BEARISH', or 'RANGING'")
    confidence: int = Field(description="Confidence percentage (0-100)")
    rationale: str
    structure_phase: str = Field(description="'BULLISH_EXPANSION', 'BEARISH_EXPANSION', 'CONSOLIDATION', 'CHOCH_REVERSAL'")
    swing_points: List[SwingPoint]
    bsl_levels: List[LiquidityLevel]
    ssl_levels: List[LiquidityLevel]
    nearest_bsl: Optional[float]
    nearest_ssl: Optional[float]
    analyzed_at: datetime


class MarketStructureAnalyzer:
    """Calculates swing highs/lows, market structure breaks, and liquidity pools."""

    def __init__(self, swing_window: int = 3):
        """
        :param swing_window: Number of candles left and right required to form a swing high/low.
        """
        self.swing_window = swing_window

    def find_swing_points(self, candles: List[CandleData]) -> List[SwingPoint]:
        """Detect swing highs and lows and label them (HH, HL, LH, LL)."""
        if len(candles) < (self.swing_window * 2 + 1):
            return []

        w = self.swing_window
        raw_swings: List[Dict[str, Any]] = []

        for i in range(w, len(candles) - w):
            c = candles[i]
            # Check swing high
            is_high = all(candles[j].high <= c.high for j in range(i - w, i + w + 1) if j != i)
            # Check swing low
            is_low = all(candles[j].low >= c.low for j in range(i - w, i + w + 1) if j != i)

            if is_high:
                raw_swings.append({
                    "index": i,
                    "timestamp": c.timestamp,
                    "price": c.high,
                    "type": "HIGH"
                })
            elif is_low:
                raw_swings.append({
                    "index": i,
                    "timestamp": c.timestamp,
                    "price": c.low,
                    "type": "LOW"
                })

        # Classify HH, HL, LH, LL
        classified_swings: List[SwingPoint] = []
        last_high: Optional[float] = None
        last_low: Optional[float] = None

        for s in raw_swings:
            if s["type"] == "HIGH":
                if last_high is None:
                    label = "HIGH"
                elif s["price"] > last_high:
                    label = "HH"  # Higher High
                else:
                    label = "LH"  # Lower High
                last_high = s["price"]

            else:  # LOW
                if last_low is None:
                    label = "LOW"
                elif s["price"] > last_low:
                    label = "HL"  # Higher Low
                else:
                    label = "LL"  # Lower Low
                last_low = s["price"]

            prec = 6 if s["price"] < 1.0 else (4 if s["price"] < 10.0 else 2)
            classified_swings.append(
                SwingPoint(
                    index=s["index"],
                    timestamp=s["timestamp"],
                    price=round(s["price"], prec),
                    point_type=s["type"],
                    label=label
                )
            )

        return classified_swings

    def analyze(self, candles: List[CandleData], symbol: str, timeframe: str = "15m") -> StructureAnalysisResult:
        """Full market structure, directional bias, and liquidity analysis."""
        if not candles:
            raise ValueError("Candles series cannot be empty")

        cur_price = candles[-1].close
        prec = 6 if cur_price < 1.0 else (4 if cur_price < 10.0 else 2)
        swings = self.find_swing_points(candles)

        high_swings = [s for s in swings if s.point_type == "HIGH"]
        low_swings = [s for s in swings if s.point_type == "LOW"]

        # 1. Determine Directional Bias & Structure Phase
        bullish_score = 0
        bearish_score = 0
        reasons = []

        if len(high_swings) >= 2:
            if high_swings[-1].price > high_swings[-2].price:
                bullish_score += 2
                reasons.append("Recent Higher High formed")
            else:
                bearish_score += 2
                reasons.append("Recent Lower High formed")

        if len(low_swings) >= 2:
            if low_swings[-1].price > low_swings[-2].price:
                bullish_score += 2
                reasons.append("Higher Low confirmed above previous demand")
            else:
                bearish_score += 2
                reasons.append("Lower Low printed, breaking market structure")

        # Trend momentum via moving average
        closes = [c.close for c in candles]
        ma_20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else cur_price
        if cur_price > ma_20:
            bullish_score += 1
            reasons.append("Price holding above 20-period EMA baseline")
        else:
            bearish_score += 1
            reasons.append("Price trading below 20-period baseline")

        # Finalize Bias & Phase
        if bullish_score > bearish_score:
            directional_bias = "BULLISH"
            phase = "BULLISH_EXPANSION"
            conf = min(92, 60 + bullish_score * 8)
            rationale = "Bullish structure confirmed. " + "; ".join(reasons)
        elif bearish_score > bullish_score:
            directional_bias = "BEARISH"
            phase = "BEARISH_EXPANSION"
            conf = min(92, 60 + bearish_score * 8)
            rationale = "Bearish structure confirmed. " + "; ".join(reasons)
        else:
            directional_bias = "RANGING"
            phase = "CONSOLIDATION"
            conf = 55
            rationale = "Neutral equilibrium range. " + "; ".join(reasons)

        # 2. Extract Liquidity Levels (BSL & SSL)
        # BSL: key swing highs above current price (or recent major highs)
        bsl_levels: List[LiquidityLevel] = []
        for h in high_swings[-5:]:
            dist = ((h.price - cur_price) / cur_price) * 100.0
            bsl_levels.append(
                LiquidityLevel(
                    level_type="BSL",
                    price=h.price,
                    timestamp=h.timestamp,
                    description=f"{h.label} Swing High Liquidity",
                    distance_pct=round(dist, 2)
                )
            )

        # SSL: key swing lows below current price (or recent major lows)
        ssl_levels: List[LiquidityLevel] = []
        for l in low_swings[-5:]:
            dist = ((cur_price - l.price) / cur_price) * 100.0
            ssl_levels.append(
                LiquidityLevel(
                    level_type="SSL",
                    price=l.price,
                    timestamp=l.timestamp,
                    description=f"{l.label} Swing Low Liquidity",
                    distance_pct=round(dist, 2)
                )
            )

        # Sort and select nearest
        highs_above = [b.price for b in bsl_levels if b.price > cur_price]
        nearest_bsl = min(highs_above) if highs_above else (max([b.price for b in bsl_levels]) if bsl_levels else None)

        lows_below = [s.price for s in ssl_levels if s.price < cur_price]
        nearest_ssl = max(lows_below) if lows_below else (min([s.price for s in ssl_levels]) if ssl_levels else None)

        return StructureAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            current_price=round(cur_price, prec),
            directional_bias=directional_bias,
            confidence=conf,
            rationale=rationale,
            structure_phase=phase,
            swing_points=swings[-8:],  # Return recent 8 points
            bsl_levels=bsl_levels[-4:],
            ssl_levels=ssl_levels[-4:],
            nearest_bsl=nearest_bsl,
            nearest_ssl=nearest_ssl,
            analyzed_at=datetime.utcnow()
        )

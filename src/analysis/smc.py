"""
Smart Money Concepts (SMC) Technical Analysis Engine.

Detects:
1. Fair Value Gaps (FVGs) - 3-candle imbalance zones with mitigation tracking.
2. Institutional Order Blocks (OBs) - Supply/Demand zones formed before displacement.
"""

from typing import List, Optional
import numpy as np
from loguru import logger

from src.data.base import CandleData
from .models import BiasType, SetupType, FairValueGap, OrderBlock, TechnicalSetup


class SMCAnalyzer:
    """Smart Money Concepts (SMC) pattern analyzer for candlestick series."""

    def __init__(self, min_gap_pct: float = 0.005, displacement_factor: float = 1.3):
        """
        :param min_gap_pct: Minimum gap size as a % of price to filter noise (default 0.005% for liquid pairs).
        :param displacement_factor: Multiplier over average candle range to qualify strong impulse.
        """
        self.min_gap_pct = min_gap_pct
        self.displacement_factor = displacement_factor

    def find_fair_value_gaps(
        self, candles: List[CandleData], unmitigated_only: bool = False
    ) -> List[FairValueGap]:
        """
        Detect Bullish and Bearish Fair Value Gaps (3-candle sequence).
        
        Bullish FVG: Candle 1 High < Candle 3 Low (Gap = [c1.high, c3.low])
        Bearish FVG: Candle 1 Low > Candle 3 High (Gap = [c3.high, c1.low])
        """
        if len(candles) < 3:
            return []

        fvgs: List[FairValueGap] = []
        n = len(candles)

        for i in range(n - 2):
            c1 = candles[i]
            c2 = candles[i + 1]  # Displacement candle
            c3 = candles[i + 2]

            # 1. Bullish FVG
            if c3.low > c1.high:
                bottom = c1.high
                top = c3.low
                gap_size = top - bottom
                gap_pct = (gap_size / bottom) * 100.0

                if gap_pct >= self.min_gap_pct:
                    # Check subsequent mitigation
                    mitigated = False
                    fully_filled = False
                    for j in range(i + 3, n):
                        future_candle = candles[j]
                        if future_candle.low <= top:
                            mitigated = True
                        if future_candle.low <= bottom:
                            fully_filled = True
                            break

                    fvg = FairValueGap(
                        bias=BiasType.BULLISH,
                        top=round(top, 4),
                        bottom=round(bottom, 4),
                        gap_size=round(gap_size, 4),
                        gap_pct=round(gap_pct, 4),
                        timestamp=c2.timestamp,
                        candle_index=i + 1,
                        mitigated=mitigated,
                        fully_filled=fully_filled,
                    )
                    if not (unmitigated_only and fully_filled):
                        fvgs.append(fvg)

            # 2. Bearish FVG
            elif c3.high < c1.low:
                bottom = c3.high
                top = c1.low
                gap_size = top - bottom
                gap_pct = (gap_size / bottom) * 100.0

                if gap_pct >= self.min_gap_pct:
                    # Check subsequent mitigation
                    mitigated = False
                    fully_filled = False
                    for j in range(i + 3, n):
                        future_candle = candles[j]
                        if future_candle.high >= bottom:
                            mitigated = True
                        if future_candle.high >= top:
                            fully_filled = True
                            break

                    fvg = FairValueGap(
                        bias=BiasType.BEARISH,
                        top=round(top, 4),
                        bottom=round(bottom, 4),
                        gap_size=round(gap_size, 4),
                        gap_pct=round(gap_pct, 4),
                        timestamp=c2.timestamp,
                        candle_index=i + 1,
                        mitigated=mitigated,
                        fully_filled=fully_filled,
                    )
                    if not (unmitigated_only and fully_filled):
                        fvgs.append(fvg)

        return fvgs

    def find_order_blocks(
        self,
        candles: List[CandleData],
        fvgs: Optional[List[FairValueGap]] = None,
        unmitigated_only: bool = False,
    ) -> List[OrderBlock]:
        """
        Detect Institutional Order Blocks (Bullish & Bearish).
        
        Bullish OB: The last down-candle before a strong upward impulse/displacement.
        Bearish OB: The last up-candle before a strong downward impulse/displacement.
        """
        if len(candles) < 5:
            return []

        if fvgs is None:
            fvgs = self.find_fair_value_gaps(candles)

        fvg_indices = {f.candle_index: f for f in fvgs}
        n = len(candles)
        order_blocks: List[OrderBlock] = []

        # Calculate average candle body range
        body_sizes = [abs(c.close - c.open) for c in candles]
        avg_body = float(np.mean(body_sizes)) if body_sizes else 0.0

        for i in range(1, n - 2):
            curr = candles[i]
            prev = candles[i - 1]
            next_1 = candles[i + 1]
            next_2 = candles[i + 2] if (i + 2) < n else None

            # Look ahead for displacement
            impulse_candles = [next_1]
            if next_2:
                impulse_candles.append(next_2)

            # Check if this candle is followed by an FVG
            has_fvg = (i + 1) in fvg_indices or (i + 2) in fvg_indices

            # 1. Bullish Order Block (Red candle before explosive green breakout)
            if curr.close < curr.open:  # Down candle
                displacement_high = max(c.high for c in impulse_candles)
                displacement_close = impulse_candles[-1].close
                move_size = displacement_close - curr.low
                move_pct = (move_size / curr.low) * 100.0 if curr.low > 0 else 0.0

                is_displacement = (
                    displacement_high > max(prev.high, curr.high) and
                    (move_size >= avg_body * self.displacement_factor or has_fvg)
                )

                if is_displacement:
                    zone_top = curr.high
                    zone_bottom = curr.low

                    # Check mitigation in subsequent candles
                    mitigated = False
                    broken = False
                    start_check = i + 1 + len(impulse_candles)
                    for j in range(start_check, n):
                        c = candles[j]
                        if c.low <= zone_top:
                            mitigated = True
                        if c.close < zone_bottom:
                            broken = True
                            break

                    ob = OrderBlock(
                        bias=BiasType.BULLISH,
                        top=round(zone_top, 4),
                        bottom=round(zone_bottom, 4),
                        timestamp=curr.timestamp,
                        candle_index=i,
                        volume=curr.volume,
                        displacement_pct=round(move_pct, 3),
                        has_confluence_fvg=has_fvg,
                        mitigated=mitigated,
                        broken=broken,
                    )
                    if not (unmitigated_only and broken):
                        order_blocks.append(ob)

            # 2. Bearish Order Block (Green candle before explosive downward drop)
            elif curr.close > curr.open:  # Up candle
                displacement_low = min(c.low for c in impulse_candles)
                displacement_close = impulse_candles[-1].close
                move_size = curr.high - displacement_close
                move_pct = (move_size / curr.high) * 100.0 if curr.high > 0 else 0.0

                is_displacement = (
                    displacement_low < min(prev.low, curr.low) and
                    (move_size >= avg_body * self.displacement_factor or has_fvg)
                )

                if is_displacement:
                    zone_top = curr.high
                    zone_bottom = curr.low

                    mitigated = False
                    broken = False
                    start_check = i + 1 + len(impulse_candles)
                    for j in range(start_check, n):
                        c = candles[j]
                        if c.high >= zone_bottom:
                            mitigated = True
                        if c.close > zone_top:
                            broken = True
                            break

                    ob = OrderBlock(
                        bias=BiasType.BEARISH,
                        top=round(zone_top, 4),
                        bottom=round(zone_bottom, 4),
                        timestamp=curr.timestamp,
                        candle_index=i,
                        volume=curr.volume,
                        displacement_pct=round(move_pct, 3),
                        has_confluence_fvg=has_fvg,
                        mitigated=mitigated,
                        broken=broken,
                    )
                    if not (unmitigated_only and broken):
                        order_blocks.append(ob)

        return order_blocks

    def extract_setups(
        self,
        candles: List[CandleData],
        symbol: str,
        timeframe: str,
        current_price: Optional[float] = None,
    ) -> List[TechnicalSetup]:
        """Extract actionable, consolidated setups from recent candles."""
        if not candles:
            return []

        cur_price = current_price or candles[-1].close
        fvgs = self.find_fair_value_gaps(candles, unmitigated_only=False)
        obs = self.find_order_blocks(candles, fvgs=fvgs, unmitigated_only=False)

        setups: List[TechnicalSetup] = []

        # Convert recent FVGs
        for f in fvgs[-5:]:  # Most recent 5
            if f.fully_filled:
                status = "FULLY_FILLED"
            elif f.mitigated:
                status = "PARTIAL_MITIGATION"
            else:
                status = "ACTIVE_UNTESTED"

            setups.append(
                TechnicalSetup(
                    symbol=symbol,
                    timeframe=timeframe,
                    setup_type=SetupType.FAIR_VALUE_GAP,
                    bias=f.bias,
                    zone_high=f.top,
                    zone_low=f.bottom,
                    current_price=cur_price,
                    timestamp=f.timestamp,
                    status=status,
                    details=f"Gap Size: ${f.gap_size:,.2f} ({f.gap_pct:.2f}%)",
                )
            )

        # Convert recent Order Blocks
        for ob in obs[-5:]:  # Most recent 5
            if ob.broken:
                status = "INVALIDATED"
            elif ob.mitigated:
                status = "TESTED_ZONE"
            else:
                status = "ACTIVE_UNTESTED"

            conf = " + FVG Confluence" if ob.has_confluence_fvg else ""
            setups.append(
                TechnicalSetup(
                    symbol=symbol,
                    timeframe=timeframe,
                    setup_type=SetupType.ORDER_BLOCK,
                    bias=ob.bias,
                    zone_high=ob.top,
                    zone_low=ob.bottom,
                    current_price=cur_price,
                    timestamp=ob.timestamp,
                    status=status,
                    details=f"Displacement: {ob.displacement_pct:.2f}%{conf}",
                )
            )

        return setups

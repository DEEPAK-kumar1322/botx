"""
Multi-Timeframe Fixed Range Volume Profile (POC Pullback Strategy) Engine.

Strategy Concept:
1. Higher Timeframe (4H):
   - Identifies the most recent major impulsive price swing (Swing Low to Swing High for an uptrend,
     or Swing High to Swing Low for a downtrend).
   - Applies Fixed Range Volume Profile (FRVP) across that exact impulsive leg.
   - Extracts the Point of Control (POC) — the exact price level where institutional volume was highest.
   - Also calculates the Value Area (VAH / VAL) representing 70% of traded volume.

2. Lower Timeframe Execution (30m):
   - Monitors price action as it retraces/pulls back into the 4H POC zone.
   - Long Setup: In an uptrend, price retraces down into the 4H POC zone and prints a confirmed
     bullish bounce / rejection candle (closed green candle or long lower absorption wick >= 35%).
   - Short Setup: In a downtrend, price rallies up into the 4H POC zone and prints a confirmed
     bearish rejection candle (closed red candle or long upper rejection wick >= 35%).

3. Risk Management:
   - Stop Loss (SL): Placed just beyond the 30m rejection wick / POC zone extreme with 0.5x ATR buffer.
   - Take Profit (TP): Target the origin 4H Swing High (for Longs) or Swing Low (for Shorts),
     strictly enforcing a minimum 1:2 to 1:3 Risk-to-Reward Ratio.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
import numpy as np
from pydantic import BaseModel, Field

from src.data.base import CandleData
from src.analysis.structure import MarketStructureAnalyzer


class FixedRangeVolumeProfile(BaseModel):
    """Result of Fixed Range Volume Profile calculation."""
    poc_price: float = Field(description="Point of Control (highest volume price)")
    vah: float = Field(description="Value Area High (70% volume upper band)")
    val: float = Field(description="Value Area Low (70% volume lower band)")
    swing_low: float
    swing_high: float
    swing_type: str = Field(description="'UPTREND' (Low to High) or 'DOWNTREND' (High to Low)")
    total_volume: float
    num_bins: int = 50


class POCPullbackSignal(BaseModel):
    """Confirmed Trade Signal for POC Pullback Strategy."""
    symbol: str
    action: str = Field(description="'BUY' or 'SELL'")
    entry_price: float
    stop_loss: float
    take_profit: float
    poc_price: float
    swing_origin: float
    risk_reward_ratio: str = "1:2.5"
    rejection_type: str
    htf_trend: str
    notes: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class POCPullbackEvaluation(BaseModel):
    """Complete evaluation state of the POC Pullback Strategy."""
    symbol: str
    current_price: float
    htf_trend: str
    swing_low: Optional[float] = None
    swing_high: Optional[float] = None
    poc_price: Optional[float] = None
    vah: Optional[float] = None
    val: Optional[float] = None
    distance_to_poc_pct: float = 0.0
    in_poc_zone: bool = False
    has_valid_setup: bool = False
    signal: Optional[POCPullbackSignal] = None
    wait_reasons: List[str] = Field(default_factory=list)


class POCPullbackAnalyzer:
    """
    Production-grade Multi-Timeframe Fixed Range Volume Profile (POC Pullback) Analyzer.
    Analyzes 4H market structure, extracts the 4H FRVP Point of Control (POC),
    and validates 30M closed-candle pullback rejections.
    """

    def __init__(self, num_bins: int = 50, poc_zone_pct: float = 0.006, min_swing_pct: float = 0.025):
        """
        num_bins: Number of price bins for Volume Profile calculation (default 50).
        poc_zone_pct: POC sensitivity zone (0.006 = +-0.6% around the POC price).
        min_swing_pct: Minimum percentage move required to qualify as a major 4H impulse (2.5%).
        """
        self.num_bins = num_bins
        self.poc_zone_pct = poc_zone_pct
        self.min_swing_pct = min_swing_pct
        self.structure_analyzer = MarketStructureAnalyzer(swing_window=3)

    def compute_frvp(self, candles: List[CandleData]) -> Optional[FixedRangeVolumeProfile]:
        """
        Compute Fixed Range Volume Profile across a list of candles.
        Distributes volume across overlapping price bins to accurately locate the Point of Control (POC).
        """
        if not candles or len(candles) < 2:
            return None

        low_range = min(c.low for c in candles)
        high_range = max(c.high for c in candles)

        if high_range <= low_range:
            return None

        bins = np.linspace(low_range, high_range, self.num_bins + 1)
        bin_volumes = np.zeros(self.num_bins)
        total_vol = 0.0

        for c in candles:
            c_low, c_high, c_vol = c.low, c.high, max(c.volume, 0.0)
            total_vol += c_vol
            c_span = max(c_high - c_low, 1e-8)

            for b in range(self.num_bins):
                b_low, b_high = bins[b], bins[b + 1]
                overlap = max(0.0, min(c_high, b_high) - max(c_low, b_low))
                if overlap > 0:
                    bin_volumes[b] += c_vol * (overlap / c_span)

        if total_vol <= 0 or np.sum(bin_volumes) <= 0:
            # Fallback if volume data is zero
            poc_price = (high_range + low_range) / 2.0
            return FixedRangeVolumeProfile(
                poc_price=poc_price,
                vah=high_range,
                val=low_range,
                swing_low=low_range,
                swing_high=high_range,
                swing_type="UPTREND",
                total_volume=0.0,
                num_bins=self.num_bins,
            )

        # POC is midpoint of the maximum volume bin
        max_bin_idx = int(np.argmax(bin_volumes))
        poc_price = float((bins[max_bin_idx] + bins[max_bin_idx + 1]) / 2.0)

        # Value Area (70% of total volume)
        target_va_vol = 0.70 * np.sum(bin_volumes)
        current_va_vol = bin_volumes[max_bin_idx]
        up_idx = max_bin_idx
        down_idx = max_bin_idx

        while current_va_vol < target_va_vol and (up_idx < self.num_bins - 1 or down_idx > 0):
            up_vol = bin_volumes[up_idx + 1] if up_idx < self.num_bins - 1 else 0.0
            down_vol = bin_volumes[down_idx - 1] if down_idx > 0 else 0.0

            if up_vol >= down_vol and up_idx < self.num_bins - 1:
                up_idx += 1
                current_va_vol += up_vol
            elif down_idx > 0:
                down_idx -= 1
                current_va_vol += down_vol
            else:
                break

        val = float(bins[down_idx])
        vah = float(bins[up_idx + 1])

        # Determine swing type: was start lower than end?
        swing_type = "UPTREND" if candles[-1].close >= candles[0].open else "DOWNTREND"

        return FixedRangeVolumeProfile(
            poc_price=poc_price,
            vah=vah,
            val=val,
            swing_low=low_range,
            swing_high=high_range,
            swing_type=swing_type,
            total_volume=float(total_vol),
            num_bins=self.num_bins,
        )

    def find_major_impulse_swing(self, candles_4h: List[CandleData]) -> Optional[Tuple[int, int, str, float, float]]:
        """
        Detects the most recent impulsive 4H swing leg.
        Returns: (start_idx, end_idx, direction, swing_low, swing_high)
        """
        if len(candles_4h) < 10:
            return None

        # Look at the last 15-20 4H candles to find major swing points
        recent = candles_4h[-20:]
        offset = len(candles_4h) - len(recent)

        highs = [c.high for c in recent]
        lows = [c.low for c in recent]

        min_rel_idx = int(np.argmin(lows))
        max_rel_idx = int(np.argmax(highs))

        swing_low_val = lows[min_rel_idx]
        swing_high_val = highs[max_rel_idx]

        if swing_high_val <= swing_low_val:
            return None

        pct_move = (swing_high_val - swing_low_val) / swing_low_val
        if pct_move < self.min_swing_pct:
            return None

        if min_rel_idx < max_rel_idx:
            # Swing Low formed first, then pumped to Swing High -> UPTREND IMPULSE
            direction = "UPTREND"
            start_idx = offset + min_rel_idx
            end_idx = offset + max_rel_idx
        else:
            # Swing High formed first, then dumped to Swing Low -> DOWNTREND IMPULSE
            direction = "DOWNTREND"
            start_idx = offset + max_rel_idx
            end_idx = offset + min_rel_idx

        return start_idx, end_idx, direction, swing_low_val, swing_high_val

    def _calc_atr(self, candles: List[CandleData], period: int = 14) -> float:
        """Calculate Average True Range for buffer sizing."""
        if len(candles) < 2:
            return 0.001
        trs = []
        for i in range(1, len(candles)):
            h = candles[i].high
            l = candles[i].low
            prev_c = candles[i - 1].close
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)
        return float(np.mean(trs[-period:]) if trs else 0.001)

    def evaluate(
        self,
        candles_30m: List[CandleData],
        candles_4h: List[CandleData],
        symbol: str = "BTC/USDT"
    ) -> POCPullbackEvaluation:
        """
        Evaluate full Multi-Timeframe Fixed Range Volume Profile (POC Pullback Strategy).
        """
        if not candles_30m or len(candles_30m) < 10 or not candles_4h or len(candles_4h) < 10:
            return POCPullbackEvaluation(
                symbol=symbol,
                current_price=candles_30m[-1].close if candles_30m else 0.0,
                htf_trend="NEUTRAL",
                wait_reasons=["Insufficient candle history on 30m or 4h."],
            )

        curr_p = candles_30m[-1].close

        # 1. Higher Timeframe 4H Analysis: Find impulsive swing
        swing_info = self.find_major_impulse_swing(candles_4h)
        if not swing_info:
            return POCPullbackEvaluation(
                symbol=symbol,
                current_price=curr_p,
                htf_trend="RANGING",
                wait_reasons=["No clear 4H impulsive swing move found."],
            )

        start_idx, end_idx, direction, sw_low, sw_high = swing_info
        impulse_slice = candles_4h[min(start_idx, end_idx): max(start_idx, end_idx) + 1]

        # 2. Compute 4H Fixed Range Volume Profile across the impulsive slice
        frvp = self.compute_frvp(impulse_slice)
        if not frvp or frvp.poc_price <= 0:
            return POCPullbackEvaluation(
                symbol=symbol,
                current_price=curr_p,
                htf_trend="RANGING",
                wait_reasons=["Failed to compute Volume Profile POC."],
            )

        poc = frvp.poc_price
        dist_pct = ((curr_p - poc) / poc) * 100.0

        # Define the POC sensitivity zone (+- poc_zone_pct)
        poc_buffer = poc * self.poc_zone_pct
        poc_zone_low = poc - poc_buffer
        poc_zone_high = poc + poc_buffer

        # Check if the recent 30M candles tested the POC zone
        # We evaluate the just-closed 30M candle (candles_30m[-2] or candles_30m[-1])
        c_test = candles_30m[-1]
        c_prev = candles_30m[-2] if len(candles_30m) >= 2 else c_test

        in_poc_zone = (c_test.low <= poc_zone_high and c_test.high >= poc_zone_low) or \
                      (c_prev.low <= poc_zone_high and c_prev.high >= poc_zone_low)

        atr_30m = self._calc_atr(candles_30m, period=14)

        wait_reasons = []
        if not in_poc_zone:
            wait_reasons.append(
                f"Waiting for pullback: Price (${curr_p:.4f}) is {abs(dist_pct):.2f}% away from 4H POC (${poc:.4f})."
            )

        # 3. Check for 30M Entry Triggers
        signal: Optional[POCPullbackSignal] = None

        if direction == "UPTREND" and in_poc_zone:
            # We want a bullish bounce/rejection off the POC
            # Candle touched POC from above and showed green close or strong lower wick
            tested_poc_support = min(c_test.low, c_prev.low) <= poc_zone_high
            has_lower_wick = (min(c_test.close, c_test.open) - c_test.low) >= (0.35 * max(c_test.high - c_test.low, 1e-6))
            is_green_bounce = c_test.close > c_test.open and c_test.close >= poc

            if tested_poc_support and (has_lower_wick or is_green_bounce):
                entry = round(curr_p, 4)
                sl = round(min(c_test.low, c_prev.low, poc - poc_buffer) - (0.5 * atr_30m), 4)
                risk = max(entry - sl, 0.0001)

                # Target origin 4H Swing High, with minimum 1:2.0 RR check
                tp_target = round(max(sw_high, entry + (2.0 * risk)), 4)
                reward = tp_target - entry
                rr_ratio = reward / risk

                rejection_desc = "Bullish Pin Bar / Absorption Wick at POC" if has_lower_wick else "Green Rejection Bounce off 4H POC"
                signal = POCPullbackSignal(
                    symbol=symbol,
                    action="BUY",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp_target,
                    poc_price=round(poc, 4),
                    swing_origin=round(sw_high, 4),
                    risk_reward_ratio=f"1:{rr_ratio:.1f}",
                    rejection_type=rejection_desc,
                    htf_trend="BULLISH_UPTREND",
                    notes=f"4H Impulse ({sw_low:.4f} -> {sw_high:.4f}). Retest into 4H POC (${poc:.4f}) confirmed on 30m.",
                )

        elif direction == "DOWNTREND" and in_poc_zone:
            # We want a bearish rejection off the POC
            # Candle touched POC from below and showed red close or strong upper wick
            tested_poc_resistance = max(c_test.high, c_prev.high) >= poc_zone_low
            has_upper_wick = (c_test.high - max(c_test.close, c_test.open)) >= (0.35 * max(c_test.high - c_test.low, 1e-6))
            is_red_rejection = c_test.close < c_test.open and c_test.close <= poc

            if tested_poc_resistance and (has_upper_wick or is_red_rejection):
                entry = round(curr_p, 4)
                sl = round(max(c_test.high, c_prev.high, poc + poc_buffer) + (0.5 * atr_30m), 4)
                risk = max(sl - entry, 0.0001)

                # Target origin 4H Swing Low, with minimum 1:2.0 RR check
                tp_target = round(min(sw_low, entry - (2.0 * risk)), 4)
                reward = entry - tp_target
                rr_ratio = reward / risk

                rejection_desc = "Bearish Shooting Star / Upper Rejection Wick at POC" if has_upper_wick else "Red Rejection Drop off 4H POC"
                signal = POCPullbackSignal(
                    symbol=symbol,
                    action="SELL",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp_target,
                    poc_price=round(poc, 4),
                    swing_origin=round(sw_low, 4),
                    risk_reward_ratio=f"1:{rr_ratio:.1f}",
                    rejection_type=rejection_desc,
                    htf_trend="BEARISH_DOWNTREND",
                    notes=f"4H Impulse ({sw_high:.4f} -> {sw_low:.4f}). Pullback rally into 4H POC (${poc:.4f}) rejected on 30m.",
                )

        has_valid_setup = signal is not None

        return POCPullbackEvaluation(
            symbol=symbol,
            current_price=curr_p,
            htf_trend=direction,
            swing_low=sw_low,
            swing_high=sw_high,
            poc_price=poc,
            vah=frvp.vah,
            val=frvp.val,
            distance_to_poc_pct=dist_pct,
            in_poc_zone=in_poc_zone,
            has_valid_setup=has_valid_setup,
            signal=signal,
            wait_reasons=wait_reasons,
        )

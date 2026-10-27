"""
Liquidity Sweep Trading Strategy Engine (Strict A+ Valid Setup Filter & Closed-Candle Logic).

Enforces 6 Strict Institutional Rules so ONLY genuine, high-probability setups trigger:
1. Major Key Support / Resistance Only:
   - Requires a major structural Swing High / Swing Low (5-bar left/right pivot), ignoring minor inside noise.
2. True Stop-Hunt Sweep vs Touch Filter (Closed Candle):
   - Price must pierce past the key level by a meaningful margin (hunting stops) and CLOSE back inside the range.
   - Evaluates CLOSED candles for the sweep & confirmation so mid-candle fakeouts never trigger false alerts.
3. Strict Confirmation (Pin Bar Wick Absorption OR Pause Candle Breakout):
   - Rejection Pin Bar: Wick >= 45% of candle range + strong close back inside range, OR
   - Pause Candle Break: Closed candle decisively breaking the Pause Candle High (Long) / Low (Short).
4. Strict 1H Higher Timeframe (HTF) Trend Alignment:
   - Long (Support Sweep) ONLY when 1H is BULLISH.
   - Short (Resistance Sweep) ONLY when 1H is BEARISH.
   - Counter-trend trades are 100% blocked.
5. Defined Risk & Minimum 1:3 RR:
   - SL beyond Sweep Candle extreme + safety buffer.
   - TP1 at 1:2 RR, TP2 at 1:3 RR.
6. Freshness Gate:
   - Signal must have confirmed on the JUST-CLOSED candle (within the last 1 closed bar),
     never re-alerting old historical sweeps.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.data.base import CandleData
from src.analysis.structure import MarketStructureAnalyzer


class LiquiditySweepSignal(BaseModel):
    """Detected & Confirmed A+ Liquidity Sweep Trade Setup."""
    symbol: str
    timeframe: str
    action: str = Field(description="'BUY' (Support Sweep) or 'SELL' (Resistance Sweep)")
    sweep_type: str = Field(description="'Support Sweep (SSL Hunt)' or 'Resistance Sweep (BSL Hunt)'")
    swept_level: float = Field(description="Key Support or Resistance price level that was swept")
    sweep_extreme: float = Field(description="Sweep candle low (for BUY) or high (for SELL)")
    sweep_candle_time: datetime
    confirmation_candle_time: datetime
    confirmation_type: str = Field(description="'Rejection Pin Bar / Wick' or 'Pause Candle High/Low Break'")
    entry_price: float
    stop_loss: float
    tp_1_2rr: float
    tp_1_3rr: float
    next_liquidity_zone: Optional[float] = None
    risk_reward_ratio: str = "1:3.0"
    htf_bias: str
    htf_aligned: bool
    psychology_note: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiquiditySweepEvaluation(BaseModel):
    """Complete evaluation state of the Liquidity Sweep strategy on a symbol."""
    symbol: str
    timeframe: str
    current_price: float
    htf_bias: str
    htf_confidence: int
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    has_valid_setup: bool
    signal: Optional[LiquiditySweepSignal] = None
    checklist: List[Tuple[str, bool, str]] = Field(default_factory=list)
    wait_reasons: List[str] = Field(default_factory=list)


class LiquiditySweepAnalyzer:
    """
    Strict A+ Liquidity Sweep Analyzer.
    Evaluates ONLY closed candles for confirmation and requires major structural levels
    + strict 1H HTF alignment so only genuine setups pass.
    """

    def __init__(self, swing_window: int = 5, lookback_sweep_bars: int = 3):
        # swing_window=5 ensures only major Support/Resistance pivots are used (not tiny noise)
        self.structure_analyzer = MarketStructureAnalyzer(swing_window=swing_window)
        self.htf_analyzer = MarketStructureAnalyzer(swing_window=3)
        self.lookback_sweep_bars = lookback_sweep_bars

    def evaluate(
        self,
        candles_ltf: List[CandleData],
        candles_htf: List[CandleData],
        symbol: str = "BTC/USDT",
        timeframe: str = "15m",
        allow_counter_trend: bool = False,
    ) -> LiquiditySweepEvaluation:
        if len(candles_ltf) < 35:
            return LiquiditySweepEvaluation(
                symbol=symbol,
                timeframe=timeframe,
                current_price=candles_ltf[-1].close if candles_ltf else 0.0,
                htf_bias="NEUTRAL",
                htf_confidence=50,
                has_valid_setup=False,
                wait_reasons=["Insufficient candle history (minimum 35 candles required)."],
            )

        live_price = candles_ltf[-1].close
        # Use closed candles (exclude the currently forming candle candles_ltf[-1])
        # so we NEVER alert on an unclosed wick that hasn't confirmed!
        closed_candles = candles_ltf[:-1]

        # 1. Analyze 1H HTF Structure
        structure_htf = self.htf_analyzer.analyze(candles_htf, symbol=symbol, timeframe="1h")
        htf_bias = structure_htf.directional_bias  # 'BULLISH', 'BEARISH', or 'RANGING'
        htf_conf = structure_htf.confidence

        # 2. Extract Major Key Support (SSL) & Resistance (BSL) prior to the recent sweep window
        cutoff_idx = len(closed_candles) - self.lookback_sweep_bars
        prior_swings = self.structure_analyzer.find_swing_points(closed_candles[:cutoff_idx + 2])

        support_levels = sorted(list({s.price for s in prior_swings if s.point_type == "LOW"}))
        resistance_levels = sorted(list({s.price for s in prior_swings if s.point_type == "HIGH"}))

        nearest_support = max(
            [p for p in support_levels if p <= live_price],
            default=(support_levels[0] if support_levels else None),
        )
        nearest_resistance = min(
            [p for p in resistance_levels if p >= live_price],
            default=(resistance_levels[-1] if resistance_levels else None),
        )

        # 3. Evaluate ONLY fresh setups that confirmed on the JUST-CLOSED candle (closed_candles[-1])
        support_candidate = self._detect_fresh_support_sweep(
            closed_candles=closed_candles,
            live_price=live_price,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            symbol=symbol,
            timeframe=timeframe,
            htf_bias=htf_bias,
        )

        resistance_candidate = self._detect_fresh_resistance_sweep(
            closed_candles=closed_candles,
            live_price=live_price,
            resistance_levels=resistance_levels,
            support_levels=support_levels,
            symbol=symbol,
            timeframe=timeframe,
            htf_bias=htf_bias,
        )

        checklist: List[Tuple[str, bool, str]] = []
        wait_reasons: List[str] = []

        chosen_candidate: Optional[LiquiditySweepSignal] = None
        if support_candidate and resistance_candidate:
            if htf_bias == "BULLISH":
                chosen_candidate = support_candidate
            elif htf_bias == "BEARISH":
                chosen_candidate = resistance_candidate
            else:
                chosen_candidate = support_candidate
        else:
            chosen_candidate = support_candidate or resistance_candidate

        if chosen_candidate:
            htf_passed = chosen_candidate.htf_aligned or allow_counter_trend
            checklist.append((
                "1. Major Key Level Liquidity Sweep (Closed Candle Reclaim)",
                True,
                f"{chosen_candidate.sweep_type}: Swept major level ${chosen_candidate.swept_level:,.2f} "
                f"(wick to ${chosen_candidate.sweep_extreme:,.2f}) and closed back inside range."
            ))
            checklist.append((
                "2. Closed-Candle Confirmation (Pin Bar / Pause Break)",
                True,
                f"Confirmed on closed candle via {chosen_candidate.confirmation_type}."
            ))
            checklist.append((
                "3. Risk Management (1:3 RR & Sweep Extreme SL)",
                True,
                f"SL: ${chosen_candidate.stop_loss:,.2f} | TP1 (1:2): ${chosen_candidate.tp_1_2rr:,.2f} | TP2 (1:3): ${chosen_candidate.tp_1_3rr:,.2f}."
            ))

            if htf_passed:
                checklist.append((
                    "4. Strict 1H Higher Timeframe Trend Filter",
                    True,
                    f"1H Trend is {htf_bias} ({htf_conf}% confidence) — Aligned with {chosen_candidate.action}."
                ))
            else:
                checklist.append((
                    "4. Strict 1H Higher Timeframe Trend Filter",
                    False,
                    f"Blocked by HTF Filter: 1H is {htf_bias}, counter-trend {chosen_candidate.action} rejected."
                ))
                wait_reasons.append(
                    f"HTF Filter Blocked: 1H trend is {htf_bias}. Counter-trend {chosen_candidate.action} ignored."
                )
        else:
            sup_str = f"${nearest_support:,.2f}" if nearest_support else "N/A"
            res_str = f"${nearest_resistance:,.2f}" if nearest_resistance else "N/A"
            checklist.append((
                "1. Major Key Level Liquidity Sweep (Closed Candle Reclaim)",
                False,
                f"No fresh sweep on last closed candle. Price (${live_price:,.2f}) between Support ({sup_str}) & Resistance ({res_str})."
            ))
            checklist.append((
                "2. Closed-Candle Confirmation (Pin Bar / Pause Break)",
                False,
                "Waiting for a closed Pin Bar rejection or Pause Candle High/Low break."
            ))
            checklist.append((
                "3. Risk Management (1:3 RR & Sweep Extreme SL)",
                True,
                "Strict 1:3 RR gate active."
            ))
            checklist.append((
                "4. Strict 1H Higher Timeframe Trend Filter",
                True,
                f"1H Bias is {htf_bias} ({htf_conf}%) — Only looking for {'Support Sweep LONG' if htf_bias == 'BULLISH' else ('Resistance Sweep SHORT' if htf_bias == 'BEARISH' else 'Major Range Extreme Sweep')}."
            ))
            wait_reasons.append(
                f"Standby: Price (${live_price:,.2f}) trading normally between Support ({sup_str}) & Resistance ({res_str})."
            )

        def _r(v: Optional[float]) -> Optional[float]:
            if v is None:
                return None
            return round(v, 6 if v < 1.0 else (4 if v < 10.0 else 2))

        has_valid = bool(chosen_candidate and (chosen_candidate.htf_aligned or allow_counter_trend))
        return LiquiditySweepEvaluation(
            symbol=symbol,
            timeframe=timeframe,
            current_price=_r(live_price) or 0.0,
            htf_bias=htf_bias,
            htf_confidence=htf_conf,
            nearest_support=_r(nearest_support),
            nearest_resistance=_r(nearest_resistance),
            has_valid_setup=has_valid,
            signal=chosen_candidate if has_valid else None,
            checklist=checklist,
            wait_reasons=wait_reasons,
        )

    def _detect_fresh_support_sweep(
        self,
        closed_candles: List[CandleData],
        live_price: float,
        support_levels: List[float],
        resistance_levels: List[float],
        symbol: str,
        timeframe: str,
        htf_bias: str,
    ) -> Optional[LiquiditySweepSignal]:
        """
        Detect a FRESH Support Sweep (LONG) confirmed on the most recently CLOSED candle (`closed_candles[-1]`).
        Case A: `closed_candles[-1]` itself swept a major Support level with >= 45% lower wick and closed back above Support.
        Case B: `closed_candles[-2]` (or `[-3]`) swept Support & reclaimed, and `closed_candles[-1]` just broke above the Pause Candle High!
        """
        if not support_levels or len(closed_candles) < 10:
            return None

        last_closed = closed_candles[-1]
        prev_closed = closed_candles[-2]

        # Check last 3 closed candles as potential sweep candle, PROVIDED confirmation happened on `last_closed`
        for offset in (1, 2, 3):
            sc_idx = len(closed_candles) - offset
            sc = closed_candles[sc_idx]
            c_range = max(sc.high - sc.low, 1e-8)
            lower_wick = min(sc.open, sc.close) - sc.low
            lower_wick_ratio = lower_wick / c_range

            # Must pierce below a major support by at least 0.05% (real stop hunt, not just a touch)
            swept_supports = [
                lvl for lvl in support_levels
                if sc.low <= lvl * 0.9995 and max(sc.close, last_closed.close) > lvl
            ]
            if not swept_supports:
                continue

            swept_level = min(swept_supports, key=lambda lvl: abs(lvl - sc.low))
            sweep_low = sc.low

            # Invalidation check: no subsequent candle broke below sweep_low
            if any(c.low < sweep_low for c in closed_candles[sc_idx + 1:]):
                continue
            if live_price <= swept_level or last_closed.close <= swept_level:
                continue

            confirmation_type = None

            if offset == 1:
                # The just-closed candle itself is the Sweep + Pin Bar Rejection candle
                if sc.close > swept_level and lower_wick_ratio >= 0.45 and sc.close >= (sc.low + 0.6 * c_range):
                    confirmation_type = f"Closed Bullish Pin Bar / Hammer ({int(lower_wick_ratio * 100)}% lower wick stop-hunt reclaim)"
            else:
                # Sweep happened 1-2 bars ago; `last_closed` must be the fresh breakout candle above the pause candle's high!
                pause_candle = closed_candles[sc_idx] if sc.close >= swept_level else closed_candles[sc_idx + 1]
                # Ensure it JUST broke on `last_closed` ( wasn't already broken earlier )
                already_broken_before = any(c.close > pause_candle.high for c in closed_candles[sc_idx + 1:-1])
                if (
                    not already_broken_before
                    and last_closed.close > pause_candle.high
                    and last_closed.close > last_closed.open
                ):
                    confirmation_type = f"Closed Pause Candle High Breakout (Closed above ${pause_candle.high:,.2f})"

            if not confirmation_type:
                continue

            # Smart precision and ATR-based buffer to survive institutional stop-loss sweeps
            prec = 4 if live_price < 10.0 else 2
            entry = round(live_price, prec)
            
            # Calculate ATR for breathing room
            ranges = [max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close)) for c, prev in zip(closed_candles[1:], closed_candles[:-1])]
            atr = sum(ranges[-14:]) / min(len(ranges), 14) if ranges else entry * 0.005
            buffer = max(atr * 0.5, entry * 0.003)
            
            sl = round(sweep_low - buffer, prec)
            risk = max(entry - sl, entry * 0.002)

            # Do not chase if entry is already > 1.5R away from swept level
            if (entry - swept_level) > (risk * 1.5):
                continue

            tp_1_2rr = round(entry + (risk * 2.0), prec)
            tp_1_3rr = round(entry + (risk * 3.0), prec)
            higher_res = [r for r in resistance_levels if r > tp_1_2rr]
            next_liq = round(min(higher_res), prec) if higher_res else tp_1_3rr

            # Strict HTF alignment: Longs allowed when 1H is BULLISH (or RANGING at major support)
            htf_aligned = (htf_bias == "BULLISH")

            return LiquiditySweepSignal(
                symbol=symbol,
                timeframe=timeframe,
                action="BUY",
                sweep_type="Support Sweep (SSL Stop-Hunt & Reclaim)",
                swept_level=round(swept_level, 2),
                sweep_extreme=round(sweep_low, 2),
                sweep_candle_time=sc.timestamp,
                confirmation_candle_time=last_closed.timestamp,
                confirmation_type=confirmation_type,
                entry_price=entry,
                stop_loss=sl,
                tp_1_2rr=tp_1_2rr,
                tp_1_3rr=tp_1_3rr,
                next_liquidity_zone=next_liq,
                risk_reward_ratio="1:3.0",
                htf_bias=htf_bias,
                htf_aligned=htf_aligned,
                psychology_note=(
                    f"Smart money swept retail SL below ${swept_level:,.2f} (low ${sweep_low:,.2f}), "
                    f"trapped breakdown sellers, and closed back above support ({confirmation_type})."
                ),
            )

        return None

    def _detect_fresh_resistance_sweep(
        self,
        closed_candles: List[CandleData],
        live_price: float,
        resistance_levels: List[float],
        support_levels: List[float],
        symbol: str,
        timeframe: str,
        htf_bias: str,
    ) -> Optional[LiquiditySweepSignal]:
        """
        Detect a FRESH Resistance Sweep (SHORT) confirmed on the most recently CLOSED candle (`closed_candles[-1]`).
        Case A: `closed_candles[-1]` itself swept a major Resistance level with >= 45% upper wick and closed back below Resistance.
        Case B: `closed_candles[-2]` (or `[-3]`) swept Resistance & rejected, and `closed_candles[-1]` just broke below the Pause Candle Low!
        """
        if not resistance_levels or len(closed_candles) < 10:
            return None

        last_closed = closed_candles[-1]

        for offset in (1, 2, 3):
            sc_idx = len(closed_candles) - offset
            sc = closed_candles[sc_idx]
            c_range = max(sc.high - sc.low, 1e-8)
            upper_wick = sc.high - max(sc.open, sc.close)
            upper_wick_ratio = upper_wick / c_range

            # Must pierce above a major resistance by at least 0.05% (real stop hunt, not just a touch)
            swept_resistances = [
                lvl for lvl in resistance_levels
                if sc.high >= lvl * 1.0005 and min(sc.close, last_closed.close) < lvl
            ]
            if not swept_resistances:
                continue

            swept_level = min(swept_resistances, key=lambda lvl: abs(sc.high - lvl))
            sweep_high = sc.high

            # Invalidation check: no subsequent candle broke above sweep_high
            if any(c.high > sweep_high for c in closed_candles[sc_idx + 1:]):
                continue
            if live_price >= swept_level or last_closed.close >= swept_level:
                continue

            confirmation_type = None

            if offset == 1:
                # The just-closed candle itself is the Sweep + Shooting Star / Pin Bar Rejection candle
                if sc.close < swept_level and upper_wick_ratio >= 0.45 and sc.close <= (sc.high - 0.6 * c_range):
                    confirmation_type = f"Closed Bearish Pin Bar / Shooting Star ({int(upper_wick_ratio * 100)}% upper wick trap)"
            else:
                # Sweep happened 1-2 bars ago; `last_closed` must be the fresh breakdown candle below the pause candle's low!
                pause_candle = closed_candles[sc_idx] if sc.close <= swept_level else closed_candles[sc_idx + 1]
                already_broken_before = any(c.close < pause_candle.low for c in closed_candles[sc_idx + 1:-1])
                if (
                    not already_broken_before
                    and last_closed.close < pause_candle.low
                    and last_closed.close < last_closed.open
                ):
                    confirmation_type = f"Closed Pause Candle Low Breakdown (Closed below ${pause_candle.low:,.2f})"

            if not confirmation_type:
                continue

            # Smart precision and ATR-based buffer to survive institutional stop-loss sweeps
            prec = 4 if live_price < 10.0 else 2
            entry = round(live_price, prec)
            
            # Calculate ATR for breathing room
            ranges = [max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close)) for c, prev in zip(closed_candles[1:], closed_candles[:-1])]
            atr = sum(ranges[-14:]) / min(len(ranges), 14) if ranges else entry * 0.005
            buffer = max(atr * 0.5, entry * 0.003)

            sl = round(sweep_high + buffer, prec)
            risk = max(sl - entry, entry * 0.002)

            if (swept_level - entry) > (risk * 1.5):
                continue

            tp_1_2rr = round(entry - (risk * 2.0), prec)
            tp_1_3rr = round(entry - (risk * 3.0), prec)
            lower_sup = [s for s in support_levels if s < tp_1_2rr]
            next_liq = round(max(lower_sup), prec) if lower_sup else tp_1_3rr

            # Strict HTF alignment: Shorts allowed when 1H is BEARISH
            htf_aligned = (htf_bias == "BEARISH")

            return LiquiditySweepSignal(
                symbol=symbol,
                timeframe=timeframe,
                action="SELL",
                sweep_type="Resistance Sweep (BSL Breakout Trap & Reject)",
                swept_level=round(swept_level, 2),
                sweep_extreme=round(sweep_high, 2),
                sweep_candle_time=sc.timestamp,
                confirmation_candle_time=last_closed.timestamp,
                confirmation_type=confirmation_type,
                entry_price=entry,
                stop_loss=sl,
                tp_1_2rr=tp_1_2rr,
                tp_1_3rr=tp_1_3rr,
                next_liquidity_zone=next_liq,
                risk_reward_ratio="1:3.0",
                htf_bias=htf_bias,
                htf_aligned=htf_aligned,
                psychology_note=(
                    f"Smart money trapped breakout buyers above ${swept_level:,.2f} (high ${sweep_high:,.2f}), "
                    f"hunted buy-stops, and closed back below resistance ({confirmation_type})."
                ),
            )

        return None

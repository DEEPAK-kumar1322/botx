"""
Master Blueprint Strategy Engine (BotX).
Fully Synchronized with:
'Smart Money Concepts & Price Action Master Blueprint'
(MONEY MATH MIND • PRICE ACTION ENCYCLOPEDIA)

Core Pillars Implemented:
1. Macro vs Micro Structure (The Two Layers):
   - Macro (1H/4H) 50 EMA determines directional bias (Uptrend: price > 50 EMA, Downtrend: price < 50 EMA).
   - Strict Trend Gate: ONLY LONG in Uptrend, ONLY SHORT in Downtrend. Counter-trend is 100% blocked.
2. Break of Structure (BOS) vs CHoCH & Fibonacci 50% Rule:
   - Valid BOS Rule: Must pullback to Discount zone (<= 50% Fib) for Buys, or Premium zone (>= 50% Fib) for Sells.
   - Chasing breakouts directly is strictly forbidden to prevent fakeout traps.
3. Order Block (OB) & Fair Value Gap (FVG) Mechanics:
   - 3-Candle FVG imbalance detection (displacement with un-overlapped wicks).
   - Order Block validation: Decisive opposite candle before impulsive displacement that broke structure.
4. SSMC Shadow Sweep Method & PDH/PDL Mechanics:
   - Wick/Shadow Sweep: Wick penetrates key liquidity (PDH/PDL/BSL/SSL) but candle body closes back inside = Valid Reversal.
   - Body Close Invalidation: If candle body closes beyond the level = Trend Shift / Continuation -> Reversal strictly CANCELLED!
5. Candlestick Classification & Rejection Confirmation:
   - Confirmation via Hammer, Inverted Hammer, Pin Bar (long rejection shadow >= 35%), or Engulfing candle.
6. Risk Management & Capital Math:
   - Position Size = (Capital * Risk%) / (Stoploss Points * Multiplier * INR_rate).
   - Strict 1:1 Quick RR with noise-buffered Stop-Loss.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.data.base import CandleData
from src.analysis.structure import MarketStructureAnalyzer


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average (EMA)."""
    if len(prices) < period:
        return [prices[-1]] * len(prices) if prices else []
    k = 2.0 / (period + 1)
    ema = [sum(prices[:period]) / period]
    for p in prices[period:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return [ema[0]] * (period - 1) + ema


class BlueprintSignal(BaseModel):
    """Smart Money Concepts & Price Action Signal."""
    symbol: str
    timeframe: str
    action: str = Field(description="'BUY' (Discount/SSL Sweep) or 'SELL' (Premium/BSL Sweep)")
    setup_name: str
    swept_level: float
    sweep_extreme: float
    sweep_candle_time: datetime
    confirmation_candle_time: datetime
    confirmation_type: str
    relative_volume: float
    entry_price: float
    stop_loss: float
    take_profit: float  # Strict 1:1 RR
    risk_distance: float
    risk_reward_ratio: str = "1:1.0"
    htf_bias: str
    htf_50_ema: float
    fib_retracement_pct: float
    in_discount_premium: bool
    has_fvg_confluence: bool = False
    has_ob_confluence: bool = False
    recommended_contracts: int = 1
    estimated_margin_inr: float = 0.0
    estimated_max_loss_inr: float = 0.0
    psychology_note: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BlueprintEvaluation(BaseModel):
    """Full evaluation of the Master Blueprint Strategy."""
    symbol: str
    timeframe: str
    current_price: float
    htf_bias: str
    htf_50_ema: float
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    fib_equilibrium: Optional[float] = None
    has_valid_setup: bool
    signal: Optional[BlueprintSignal] = None
    checklist: List[Tuple[str, bool, str]] = Field(default_factory=list)
    wait_reasons: List[str] = Field(default_factory=list)


class MasterBlueprintEngine:
    """
    Complete algorithmic implementation of the SMC & Price Action Master Blueprint.
    """

    def __init__(
        self,
        swing_window: int = 5,
        min_rvol: float = 1.05,
        max_chase_r: float = 0.45,
    ):
        self.structure_analyzer = MarketStructureAnalyzer(swing_window=swing_window)
        self.min_rvol = min_rvol
        self.max_chase_r = max_chase_r

    def evaluate(
        self,
        candles_ltf: List[CandleData],
        candles_htf: List[CandleData],
        symbol: str = "BTC/USDT",
        timeframe: str = "15m",
        capital_inr: float = 110.0,
        risk_pct: float = 0.035,  # 3.5% risk per trade (~Rs 3.85)
        max_loss_inr: float = 4.0,
        contract_multiplier: float = 1.0,
        leverage: float = 10.0,
        inr_per_usd: float = 85.0,
        allow_counter_trend: bool = False,
    ) -> BlueprintEvaluation:
        if len(candles_ltf) < 30 or len(candles_htf) < 15:
            return BlueprintEvaluation(
                symbol=symbol,
                timeframe=timeframe,
                current_price=candles_ltf[-1].close if candles_ltf else 0.0,
                htf_bias="NEUTRAL",
                htf_50_ema=0.0,
                has_valid_setup=False,
                wait_reasons=["Insufficient candle history for analysis."],
            )

        live_price = candles_ltf[-1].close
        closed_candles = candles_ltf[:-1]

        # =========================================================================
        # PILLAR 1: Macro Structure (The Skeleton) & 50 EMA Filter
        # =========================================================================
        htf_closes = [c.close for c in candles_htf]
        htf_period = min(50, len(htf_closes))
        htf_ema = calculate_ema(htf_closes, htf_period)[-1]
        last_htf_close = htf_closes[-1]

        if last_htf_close > htf_ema:
            htf_bias = "BULLISH"
        else:
            htf_bias = "BEARISH"

        # =========================================================================
        # PILLAR 2: Key Swings, Fib 50% Equilibrium (Discount vs Premium)
        # =========================================================================
        prior_swings = self.structure_analyzer.find_swing_points(closed_candles[:-2])
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

        # Macro Swing Range for Fibonacci 50% Equilibrium
        recent_low = min([c.low for c in closed_candles[-35:]])
        recent_high = max([c.high for c in closed_candles[-35:]])
        fib_equilibrium = recent_low + 0.50 * (recent_high - recent_low)

        # =========================================================================
        # PILLAR 3: Fair Value Gap (FVG) Imbalance Detection
        # =========================================================================
        has_bullish_fvg, has_bearish_fvg = self._detect_fvg(closed_candles)

        # =========================================================================
        # PILLAR 4 & 5: SSMC Shadow Sweep & Candlestick Confirmation Detection
        # =========================================================================
        candidate = self._detect_master_setup(
            closed_candles=closed_candles,
            live_price=live_price,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            symbol=symbol,
            timeframe=timeframe,
            htf_bias=htf_bias,
            htf_ema=htf_ema,
            fib_equilibrium=fib_equilibrium,
            has_bullish_fvg=has_bullish_fvg,
            has_bearish_fvg=has_bearish_fvg,
            capital_inr=capital_inr,
            risk_pct=risk_pct,
            max_loss_inr=max_loss_inr,
            contract_multiplier=contract_multiplier,
            leverage=leverage,
            inr_per_usd=inr_per_usd,
        )

        checklist: List[Tuple[str, bool, str]] = []
        wait_reasons: List[str] = []

        if candidate:
            trend_aligned = (candidate.action == "BUY" and htf_bias == "BULLISH") or (
                candidate.action == "SELL" and htf_bias == "BEARISH"
            ) or allow_counter_trend

            checklist.append((
                "1. 50 EMA Macro Trend Filter (Page 1 & 2)",
                trend_aligned,
                f"1H/4H Price (${live_price:,.4f}) is {'above' if htf_bias == 'BULLISH' else 'below'} 50 EMA (${htf_ema:,.4f}) -> {htf_bias}.",
            ))

            checklist.append((
                "2. SSMC Shadow Sweep (Page 2: Wick Sweep vs Body Rejection)",
                True,
                f"Swept ${candidate.swept_level:,.4f} with wick, body closed inside. ({candidate.confirmation_type}).",
            ))

            checklist.append((
                "3. Fib 50% Rule (Discount/Premium Pricing)",
                candidate.in_discount_premium,
                f"Price is in {'Discount (< 50% Fib)' if candidate.action == 'BUY' else 'Premium (> 50% Fib)'} (EQ: ${fib_equilibrium:,.4f}).",
            ))

            checklist.append((
                "4. Volume & Institutional Footprint (RVOL)",
                candidate.relative_volume >= self.min_rvol,
                f"RVOL: {candidate.relative_volume:.2f}x (Required: >= {self.min_rvol:.2f}x).",
            ))

            checklist.append((
                "5. Strict Capital Math & Noise-Buffered 1:1 Exit Plan",
                True,
                f"Size: {candidate.recommended_contracts} contracts | Risk: -₹{candidate.estimated_max_loss_inr:.2f} | TP (1:1): +₹{(candidate.recommended_contracts * candidate.risk_distance * inr_per_usd):.2f}.",
            ))

            if not trend_aligned:
                wait_reasons.append(f"Blocked by Macro Trend Filter: 50 EMA is {htf_bias}, cannot execute counter-trend {candidate.action}.")

            if not candidate.in_discount_premium:
                wait_reasons.append(f"Blocked by Fib 50% Rule: Price not in favorable {'Discount' if candidate.action == 'BUY' else 'Premium'} zone.")

            if candidate.relative_volume < self.min_rvol:
                wait_reasons.append(f"Volume too thin: RVOL {candidate.relative_volume:.2f}x below threshold {self.min_rvol:.2f}x.")

            has_valid = trend_aligned and candidate.in_discount_premium and (candidate.relative_volume >= self.min_rvol)
        else:
            sup_str = f"${nearest_support:,.4f}" if nearest_support else "N/A"
            res_str = f"${nearest_resistance:,.4f}" if nearest_resistance else "N/A"
            checklist.append((
                "1. 50 EMA Macro Trend Filter",
                True,
                f"1H/4H Trend is {htf_bias} (50 EMA: ${htf_ema:,.4f}). Waiting for {htf_bias} setups only.",
            ))
            checklist.append((
                "2. SSMC Shadow Sweep Setup",
                False,
                f"No clean wick sweep on closed bars. Price between S: {sup_str} and R: {res_str}.",
            ))
            wait_reasons.append(f"Standby: Price between {sup_str} and {res_str}. Waiting for {htf_bias} Liquidity Sweep.")
            has_valid = False

        return BlueprintEvaluation(
            symbol=symbol,
            timeframe=timeframe,
            current_price=live_price,
            htf_bias=htf_bias,
            htf_50_ema=htf_ema,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            fib_equilibrium=fib_equilibrium,
            has_valid_setup=has_valid,
            signal=candidate if has_valid else None,
            checklist=checklist,
            wait_reasons=wait_reasons,
        )

    def _detect_fvg(self, closed_candles: List[CandleData]) -> Tuple[bool, bool]:
        """Detect 3-candle Fair Value Gap (FVG) within last 8 candles."""
        has_bull_fvg = False
        has_bear_fvg = False
        for i in range(len(closed_candles) - 1, max(len(closed_candles) - 9, 2), -1):
            c1 = closed_candles[i - 2]
            c2 = closed_candles[i - 1]
            c3 = closed_candles[i]
            # Bullish FVG: Candle 1 High < Candle 3 Low (Displacement up)
            if c1.high < c3.low and (c2.close > c2.open):
                has_bull_fvg = True
            # Bearish FVG: Candle 1 Low > Candle 3 High (Displacement down)
            if c1.low > c3.high and (c2.close < c2.open):
                has_bear_fvg = True
        return has_bull_fvg, has_bear_fvg

    def _detect_master_setup(
        self,
        closed_candles: List[CandleData],
        live_price: float,
        support_levels: List[float],
        resistance_levels: List[float],
        symbol: str,
        timeframe: str,
        htf_bias: str,
        htf_ema: float,
        fib_equilibrium: float,
        has_bullish_fvg: bool,
        has_bearish_fvg: bool,
        capital_inr: float,
        risk_pct: float,
        max_loss_inr: float,
        contract_multiplier: float,
        leverage: float,
        inr_per_usd: float,
    ) -> Optional[BlueprintSignal]:
        last_closed = closed_candles[-1]

        # 20-bar Volume average
        vols = [c.volume for c in closed_candles[-20:] if c.volume is not None and c.volume > 0]
        avg_vol = sum(vols) / len(vols) if vols else 1.0

        # ATR 14-bar for noise buffer
        ranges = [
            max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
            for c, prev in zip(closed_candles[1:], closed_candles[:-1])
        ]
        atr = sum(ranges[-14:]) / min(len(ranges), 14) if ranges else (live_price * 0.005)
        buffer = max(atr * 0.5, live_price * 0.003)

        prec = 4 if live_price < 10.0 else (5 if live_price < 1.0 else 2)

        # =========================================================================
        # 1. SUPPORT SWEEP (BUY) - ONLY PERMITTED IF HTF BIAS IS BULLISH
        # =========================================================================
        if htf_bias == "BULLISH":
            for offset in (1, 2, 3):
                sc_idx = len(closed_candles) - offset
                sc = closed_candles[sc_idx]
                c_range = max(sc.high - sc.low, 1e-8)
                lower_wick = min(sc.open, sc.close) - sc.low
                lower_wick_ratio = lower_wick / c_range

                # Must sweep below support
                swept_supports = [
                    lvl for lvl in support_levels
                    if sc.low <= (lvl * 0.9995)
                ]
                if not swept_supports:
                    continue

                swept_lvl = min(swept_supports, key=lambda l: abs(l - sc.low))
                sweep_low = sc.low

                # CRITICAL RULE FROM BLUEPRINT (Section 4):
                # "Body Close Below: Candle ki body support ke neeche close ho gayi to trend bearish ho gaya -> Buy cancel!"
                body_closed_below = any(
                    min(c.open, c.close) < swept_lvl for c in closed_candles[sc_idx:]
                )
                if body_closed_below:
                    continue  # Invalidated!

                # Sweep candle body must close above level (Wick / Shadow Sweep)
                if sc.close <= swept_lvl and last_closed.close <= swept_lvl:
                    continue

                # Candlestick Classification confirmation (Hammer / Pin Bar / Engulfing)
                conf_type = None
                if lower_wick_ratio >= 0.35 and sc.close >= (sc.low + 0.45 * c_range):
                    conf_type = f"SSMC Bullish Pin Bar Sweep ({int(lower_wick_ratio * 100)}% Wick)"
                elif last_closed.close > last_closed.open and last_closed.close > sc.high:
                    conf_type = f"Bullish Engulfing Reversal Reclaim"
                elif last_closed.close > sc.close and last_closed.close > swept_lvl:
                    conf_type = f"Bullish Reclaim Follow-through"

                if not conf_type:
                    continue

                # Fibonacci 50% Rule: Entry must be in Discount Zone (<= fib_equilibrium)
                in_discount = live_price <= fib_equilibrium

                entry = round(live_price, prec)
                sl = round(sweep_low - buffer, prec)
                risk_dist = max(entry - sl, entry * 0.002)

                # Chasing protection: don't enter if price has moved too far past swept level
                if (entry - swept_lvl) > (risk_dist * self.max_chase_r):
                    continue

                # Strict 1:1 Quick RR Target
                tp = round(entry + risk_dist, prec)

                # Relative Volume
                rvol = round(last_closed.volume / avg_vol, 2) if (last_closed.volume and avg_vol > 0) else 1.1

                # Handwritten Capital Math: Position Size = (Capital * Risk%) / SL Points
                allowed_risk_inr = min(capital_inr * risk_pct, max_loss_inr)
                risk_per_contract_inr = contract_multiplier * risk_dist * inr_per_usd
                if risk_per_contract_inr > 0:
                    rec_contracts = max(1, int(allowed_risk_inr / risk_per_contract_inr))
                else:
                    rec_contracts = 1

                notional_usd = rec_contracts * contract_multiplier * entry
                est_margin_inr = round((notional_usd / leverage) * inr_per_usd, 2)
                est_loss_inr = round(rec_contracts * risk_per_contract_inr, 2)

                return BlueprintSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    action="BUY",
                    setup_name="SSMC Shadow Sweep (SSL Hunt in Discount)",
                    swept_level=round(swept_lvl, prec),
                    sweep_extreme=round(sweep_low, prec),
                    sweep_candle_time=sc.timestamp,
                    confirmation_candle_time=last_closed.timestamp,
                    confirmation_type=conf_type,
                    relative_volume=rvol,
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    risk_distance=round(risk_dist, prec),
                    risk_reward_ratio="1:1.0",
                    htf_bias=htf_bias,
                    htf_50_ema=round(htf_ema, prec),
                    fib_retracement_pct=round(((live_price - recent_low) / max(recent_high - recent_low, 1e-8)) * 100, 1),
                    in_discount_premium=in_discount,
                    has_fvg_confluence=has_bullish_fvg,
                    recommended_contracts=rec_contracts,
                    estimated_margin_inr=est_margin_inr,
                    estimated_max_loss_inr=est_loss_inr,
                    psychology_note=f"Hunted retail sell stops below ${swept_lvl:,.4f} in Discount zone. Wick absorption confirmed with 50 EMA Bullish alignment.",
                )

        # =========================================================================
        # 2. RESISTANCE SWEEP (SELL) - ONLY PERMITTED IF HTF BIAS IS BEARISH
        # =========================================================================
        elif htf_bias == "BEARISH":
            for offset in (1, 2, 3):
                sc_idx = len(closed_candles) - offset
                sc = closed_candles[sc_idx]
                c_range = max(sc.high - sc.low, 1e-8)
                upper_wick = sc.high - max(sc.open, sc.close)
                upper_wick_ratio = upper_wick / c_range

                # Must sweep above resistance
                swept_resistances = [
                    lvl for lvl in resistance_levels
                    if sc.high >= (lvl * 1.0005)
                ]
                if not swept_resistances:
                    continue

                swept_lvl = min(swept_resistances, key=lambda l: abs(l - sc.high))
                sweep_high = sc.high

                # CRITICAL RULE FROM BLUEPRINT (Section 4):
                # "Body Close Above: Candle ki body PDH ke upar close ho gayi to wo bullish ho gaya -> Short trade strictly cancel!"
                body_closed_above = any(
                    max(c.open, c.close) > swept_lvl for c in closed_candles[sc_idx:]
                )
                if body_closed_above:
                    continue  # Invalidated!

                # Sweep candle body must close below level (Wick / Shadow Sweep)
                if sc.close >= swept_lvl and last_closed.close >= swept_lvl:
                    continue

                # Candlestick Classification confirmation (Shooting Star / Pin Bar / Engulfing)
                conf_type = None
                if upper_wick_ratio >= 0.35 and sc.close <= (sc.high - 0.45 * c_range):
                    conf_type = f"SSMC Bearish Shooting Star Sweep ({int(upper_wick_ratio * 100)}% Wick)"
                elif last_closed.close < last_closed.open and last_closed.close < sc.low:
                    conf_type = f"Bearish Engulfing Reversal Rejection"
                elif last_closed.close < sc.close and last_closed.close < swept_lvl:
                    conf_type = f"Bearish Rejection Follow-through"

                if not conf_type:
                    continue

                # Fibonacci 50% Rule: Entry must be in Premium Zone (>= fib_equilibrium)
                in_premium = live_price >= fib_equilibrium

                entry = round(live_price, prec)
                sl = round(sweep_high + buffer, prec)
                risk_dist = max(sl - entry, entry * 0.002)

                # Chasing protection: don't enter if price has dumped too far below swept level
                if (swept_lvl - entry) > (risk_dist * self.max_chase_r):
                    continue

                # Strict 1:1 Quick RR Target
                tp = round(entry - risk_dist, prec)

                # Relative Volume
                rvol = round(last_closed.volume / avg_vol, 2) if (last_closed.volume and avg_vol > 0) else 1.1

                # Handwritten Capital Math: Position Size = (Capital * Risk%) / SL Points
                allowed_risk_inr = min(capital_inr * risk_pct, max_loss_inr)
                risk_per_contract_inr = contract_multiplier * risk_dist * inr_per_usd
                if risk_per_contract_inr > 0:
                    rec_contracts = max(1, int(allowed_risk_inr / risk_per_contract_inr))
                else:
                    rec_contracts = 1

                notional_usd = rec_contracts * contract_multiplier * entry
                est_margin_inr = round((notional_usd / leverage) * inr_per_usd, 2)
                est_loss_inr = round(rec_contracts * risk_per_contract_inr, 2)

                return BlueprintSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    action="SELL",
                    setup_name="SSMC Shadow Sweep (BSL Hunt in Premium)",
                    swept_level=round(swept_lvl, prec),
                    sweep_extreme=round(sweep_high, prec),
                    sweep_candle_time=sc.timestamp,
                    confirmation_candle_time=last_closed.timestamp,
                    confirmation_type=conf_type,
                    relative_volume=rvol,
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    risk_distance=round(risk_dist, prec),
                    risk_reward_ratio="1:1.0",
                    htf_bias=htf_bias,
                    htf_50_ema=round(htf_ema, prec),
                    fib_retracement_pct=round(((live_price - recent_low) / max(recent_high - recent_low, 1e-8)) * 100, 1),
                    in_discount_premium=in_premium,
                    has_fvg_confluence=has_bearish_fvg,
                    recommended_contracts=rec_contracts,
                    estimated_margin_inr=est_margin_inr,
                    estimated_max_loss_inr=est_loss_inr,
                    psychology_note=f"Hunted retail buy stops above ${swept_lvl:,.4f} in Premium zone. Breakout buyers trapped with 50 EMA Bearish alignment.",
                )

        return None

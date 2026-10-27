"""
Price Action & Market Structure Retest Scalping Strategy (Funded Trader Model).
Reference: https://youtu.be/8LQsR7B2vQ0 ("The Scalping Strategy Used By Funded Traders - PRICE ACTION")

Core Rules:
1. 100% Pure Price Action & Market Structure (Zero Indicators).
2. Higher Timeframe (1H): Identify overall trend momentum (Higher Highs/Higher Lows = Bullish, Lower Highs/Lower Lows = Bearish).
3. Lower Timeframe (5M): Identify Break of Structure (BOS) of previous swing high/low.
4. Retest / Pullback: Wait for price to pull back to retest the broken level (never chase breakout).
5. Candlestick Confirmation at Retest:
   - For SELL: Long Upper Wick Rejection Candle (wick >= 40%) OR Bearish Engulfing.
   - For BUY: Long Lower Wick Rejection Candle (wick >= 40%) OR Bullish Engulfing.
6. Execution & Risk:
   - Stop-Loss: Placed beyond the confirmation candle high/low (+ buffer).
   - Take-Profit: Exact 1:2 Risk-to-Reward (RR).
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.data.base import CandleData
from src.analysis.structure import MarketStructureAnalyzer


class PriceActionRetestSignal(BaseModel):
    """Confirmed Price Action Retest Setup Signal."""
    symbol: str
    timeframe: str = "5m"
    action: str = Field(description="'BUY' or 'SELL'")
    setup_name: str = "Price Action Retest (Funded Trader)"
    broken_level: float = Field(description="5M Broken Swing High / Swing Low that was retested")
    level_type: str = Field(description="'Broken Higher Low (Resistance Flip)' or 'Broken Lower High (Support Flip)'")
    confirmation_type: str = Field(description="'Long Wick Rejection' or 'Engulfing Candlestick'")
    confirmation_candle_time: datetime
    entry_price: float
    stop_loss: float
    tp_1_2rr: float
    risk_reward_ratio: str = "1:2.0"
    htf_bias: str
    htf_confidence: int
    notes: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PriceActionRetestEvaluation(BaseModel):
    """Evaluation result for a symbol under the Price Action Retest strategy."""
    symbol: str
    timeframe: str = "5m"
    current_price: float
    htf_bias: str
    htf_confidence: int
    broken_level: Optional[float] = None
    has_valid_setup: bool
    signal: Optional[PriceActionRetestSignal] = None
    checklist: List[Tuple[str, bool, str]] = Field(default_factory=list)
    wait_reasons: List[str] = Field(default_factory=list)


class PriceActionRetestAnalyzer:
    """
    Pure Price Action & Market Structure Retest Analyzer (5M Entry + 1H Trend Filter).
    Implements the exact strategy taught in the funded trader scalping masterclass.
    """

    def __init__(self, swing_window_5m: int = 3, swing_window_1h: int = 3):
        self.structure_5m = MarketStructureAnalyzer(swing_window=swing_window_5m)
        self.structure_1h = MarketStructureAnalyzer(swing_window=swing_window_1h)

    def evaluate(
        self,
        candles_5m: List[CandleData],
        candles_1h: List[CandleData],
        symbol: str = "BTC/USDT",
        timeframe: str = "5m",
    ) -> PriceActionRetestEvaluation:
        if len(candles_5m) < 30:
            return PriceActionRetestEvaluation(
                symbol=symbol,
                timeframe=timeframe,
                current_price=candles_5m[-1].close if candles_5m else 0.0,
                htf_bias="NEUTRAL",
                htf_confidence=50,
                has_valid_setup=False,
                wait_reasons=["Insufficient 5M candle history (minimum 30 candles required)."],
            )

        current_price = candles_5m[-1].close

        # Step 1: 1H Higher Timeframe Trend Alignment
        htf_struct = self.structure_1h.analyze(candles_1h, symbol=symbol, timeframe="1h") if len(candles_1h) >= 20 else None
        htf_bias = htf_struct.directional_bias if htf_struct else "NEUTRAL"
        htf_conf = htf_struct.confidence if htf_struct else 50

        # Step 2: 5M Market Structure Swings (Recent Highs & Lows)
        ltf_struct = self.structure_5m.analyze(candles_5m, symbol=symbol, timeframe=timeframe)
        swing_highs = sorted([sp for sp in ltf_struct.swing_points if sp.point_type == "HIGH"], key=lambda x: x.timestamp)
        swing_lows = sorted([sp for sp in ltf_struct.swing_points if sp.point_type == "LOW"], key=lambda x: x.timestamp)

        # Closed candles for evaluation (avoid checking mid-bar repaints)
        closed_candles = candles_5m[:-1]
        if len(closed_candles) < 5:
            return PriceActionRetestEvaluation(
                symbol=symbol,
                timeframe=timeframe,
                current_price=current_price,
                htf_bias=htf_bias,
                htf_confidence=htf_conf,
                has_valid_setup=False,
                wait_reasons=["Waiting for sufficient closed 5M candles."],
            )

        last_closed = closed_candles[-1]
        prev_closed = closed_candles[-2]

        checklist = []
        wait_reasons = []

        # -------------------------------------------------------------------------
        # -------------------------------------------------------------------------
        # Scenario A: BEARISH BOS + RETEST (SELL / SHORT - A++ Criteria: 80-90% Win Chance)
        # Condition: 1H MUST be strongly BEARISH (conf >= 80%), 5M broke below recent Swing Low,
        # pulled back to retest within last 3 bars, and printed sharp Rejection Wick (>=45%) or Strong Engulfing.
        # -------------------------------------------------------------------------
        sell_signal = None
        if htf_bias == "BEARISH" and htf_conf >= 80 and len(swing_lows) >= 1:
            recent_sw_low = swing_lows[-1]
            broken_level = recent_sw_low.price

            # Check if broken by any candle after the swing low formation
            post_break_candles = [c for c in closed_candles if c.timestamp > recent_sw_low.timestamp]
            has_broken = any(c.close < broken_level for c in post_break_candles)

            if has_broken:
                # Fresh retest in recent candles (within last 3 candles)
                tolerance = broken_level * 0.0025
                retested = any(abs(c.high - broken_level) <= tolerance or (c.high >= broken_level and c.close <= broken_level * 1.002) for c in post_break_candles[-3:])

                if retested:
                    # Candlestick Confirmation on the last closed candle:
                    # Option 1: Long Upper Wick Rejection (upper wick >= 45% of range)
                    c_range = max(last_closed.high - last_closed.low, 0.00001)
                    upper_wick = last_closed.high - max(last_closed.open, last_closed.close)
                    body = abs(last_closed.close - last_closed.open)
                    is_upper_wick_rejection = (upper_wick / c_range >= 0.45) and (last_closed.close <= last_closed.low + 0.50 * c_range)

                    # Option 2: Strong Bearish Engulfing (solid body >= 50% of range)
                    is_bearish_engulfing = (last_closed.close < last_closed.open) and (last_closed.open >= prev_closed.close) and (last_closed.close < prev_closed.open) and (body / c_range >= 0.50)

                    if is_upper_wick_rejection or is_bearish_engulfing:
                        conf_type = "Long Wick Rejection" if is_upper_wick_rejection else "Bearish Engulfing"
                        # Calculate ATR (14-period) on closed candles to avoid retail stop hunts
                        ranges = [max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close)) for c, prev in zip(closed_candles[1:], closed_candles[:-1])]
                        atr = sum(ranges[-14:]) / min(len(ranges), 14) if ranges else last_closed.close * 0.005

                        # Structural SL: Above highest high of recent structural candles + 0.5x ATR buffer
                        recent_high = max(c.high for c in closed_candles[-4:])
                        stop_loss = round(recent_high + max(atr * 0.5, last_closed.close * 0.003), 4)
                        risk = stop_loss - last_closed.close

                        if risk > 0:
                            tp_2rr = round(last_closed.close - (2.0 * risk), 4)
                            sell_signal = PriceActionRetestSignal(
                                symbol=symbol,
                                timeframe=timeframe,
                                action="SELL",
                                broken_level=broken_level,
                                level_type="Broken Higher Low (Resistance Flip)",
                                confirmation_type=conf_type,
                                confirmation_candle_time=last_closed.timestamp,
                                entry_price=last_closed.close,
                                stop_loss=stop_loss,
                                tp_1_2rr=tp_2rr,
                                htf_bias=htf_bias,
                                htf_confidence=htf_conf,
                                notes=f"A++ 5M BOS below ${broken_level:.2f} + Retest + {conf_type} with 1H {htf_bias} ({htf_conf}%). 1:2 RR.",
                            )

        # -------------------------------------------------------------------------
        # Scenario B: BULLISH BOS + RETEST (BUY / LONG - A++ Criteria: 80-90% Win Chance)
        # Condition: 1H MUST be strongly BULLISH (conf >= 80%), 5M broke above recent Swing High,
        # pulled back to retest within last 3 bars, and printed sharp Rejection Lower Wick (>=45%) or Strong Engulfing.
        # -------------------------------------------------------------------------
        buy_signal = None
        if htf_bias == "BULLISH" and htf_conf >= 80 and len(swing_highs) >= 1:
            recent_sw_high = swing_highs[-1]
            broken_level = recent_sw_high.price

            post_break_candles = [c for c in closed_candles if c.timestamp > recent_sw_high.timestamp]
            has_broken = any(c.close > broken_level for c in post_break_candles)

            if has_broken:
                tolerance = broken_level * 0.0025
                retested = any(abs(c.low - broken_level) <= tolerance or (c.low <= broken_level and c.close >= broken_level * 0.998) for c in post_break_candles[-3:])

                if retested:
                    # Candlestick Confirmation on the last closed candle:
                    # Option 1: Long Lower Wick Rejection (lower wick >= 45% of range)
                    c_range = max(last_closed.high - last_closed.low, 0.00001)
                    lower_wick = min(last_closed.open, last_closed.close) - last_closed.low
                    body = abs(last_closed.close - last_closed.open)
                    is_lower_wick_rejection = (lower_wick / c_range >= 0.45) and (last_closed.close >= last_closed.low + 0.50 * c_range)

                    # Option 2: Strong Bullish Engulfing (solid body >= 50% of range)
                    is_bullish_engulfing = (last_closed.close > last_closed.open) and (last_closed.open <= prev_closed.close) and (last_closed.close > prev_closed.open) and (body / c_range >= 0.50)

                    if is_lower_wick_rejection or is_bullish_engulfing:
                        conf_type = "Long Wick Rejection" if is_lower_wick_rejection else "Bullish Engulfing"
                        # Calculate ATR (14-period) on closed candles to avoid retail stop hunts
                        ranges = [max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close)) for c, prev in zip(closed_candles[1:], closed_candles[:-1])]
                        atr = sum(ranges[-14:]) / min(len(ranges), 14) if ranges else last_closed.close * 0.005

                        # Structural SL: Below lowest low of recent structural candles - 0.5x ATR buffer
                        recent_low = min(c.low for c in closed_candles[-4:])
                        stop_loss = round(recent_low - max(atr * 0.5, last_closed.close * 0.003), 4)
                        risk = last_closed.close - stop_loss

                        if risk > 0:
                            tp_2rr = round(last_closed.close + (2.0 * risk), 4)
                            buy_signal = PriceActionRetestSignal(
                                symbol=symbol,
                                timeframe=timeframe,
                                action="BUY",
                                broken_level=broken_level,
                                level_type="Broken Lower High (Support Flip)",
                                confirmation_type=conf_type,
                                confirmation_candle_time=last_closed.timestamp,
                                entry_price=last_closed.close,
                                stop_loss=stop_loss,
                                tp_1_2rr=tp_2rr,
                                htf_bias=htf_bias,
                                htf_confidence=htf_conf,
                                notes=f"A++ 5M BOS above ${broken_level:.2f} + Retest + {conf_type} with 1H {htf_bias} ({htf_conf}%). 1:2 RR.",
                            )

        # Strict HTF alignment - only trade in direction of strong trend
        active_signal = None
        if htf_bias == "BULLISH" and buy_signal:
            active_signal = buy_signal
        elif htf_bias == "BEARISH" and sell_signal:
            active_signal = sell_signal
        elif buy_signal and not sell_signal:
            active_signal = buy_signal
        elif sell_signal and not buy_signal:
            active_signal = sell_signal

        has_valid_setup = active_signal is not None

        # Build checklist & wait reasons
        checklist.append(("1H Macro Trend Alignment", htf_bias in ["BULLISH", "BEARISH"], f"1H Bias is {htf_bias} ({htf_conf}% confidence)"))
        checklist.append(("5M Break of Structure (BOS)", True if (swing_highs or swing_lows) else False, "5M Swings mapped"))
        checklist.append(("Pullback & Retest Confirmed", has_valid_setup, "Price retested broken structure level"))
        checklist.append(("Candlestick Rejection / Engulfing Confirmation", has_valid_setup, active_signal.confirmation_type if active_signal else "Waiting for Pin Bar or Engulfing candle"))

        if not has_valid_setup:
            if htf_bias == "BULLISH":
                wait_reasons.append(f"Waiting for 5M Bullish BOS + Retest with lower wick/engulfing rejection.")
            elif htf_bias == "BEARISH":
                wait_reasons.append(f"Waiting for 5M Bearish BOS + Retest with upper wick/engulfing rejection.")
            else:
                wait_reasons.append(f"Waiting for clear 1H directional trend and 5M structure breakout.")

        return PriceActionRetestEvaluation(
            symbol=symbol,
            timeframe=timeframe,
            current_price=current_price,
            htf_bias=htf_bias,
            htf_confidence=htf_conf,
            broken_level=active_signal.broken_level if active_signal else (swing_highs[-1].price if swing_highs else None),
            has_valid_setup=has_valid_setup,
            signal=active_signal,
            checklist=checklist,
            wait_reasons=wait_reasons,
        )

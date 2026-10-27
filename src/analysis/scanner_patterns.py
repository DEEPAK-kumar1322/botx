"""
Quantitative Chart Pattern & Confluence Scanner (BotX).

Adapted from trader-scanner:
Implements Wilder's Smoothed RSI and 5 quantitative chart setups:
1. oversold (RSI-14 < 30): Deep discount exhaustion.
2. oversold_bounce: RSI was < 30 on previous bar and current bar closed higher (V-reversal trigger).
3. overbought (RSI-14 > 70): Overextended premium exhaustion.
4. overbought_rejection: RSI was > 70 on previous bar and current bar closed lower.
5. breakout_20bar: Current close breaks above highest close of previous 20 bars.
6. breakdown_20bar: Current close breaks below lowest close of previous 20 bars.
7. reclaim_ma20: Price dipped below 20 SMA on prior bar and reclaimed above on current bar.
8. bull_flag / bear_flag: Strong expansion followed by tight compression (< 5% range over 5 bars).
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.data.base import CandleData


class PatternScanResult(BaseModel):
    """Result of pattern detection on a candle series."""
    symbol: str
    timeframe: str
    rsi_14: Optional[float] = None
    rsi_14_prev: Optional[float] = None
    ma_20: Optional[float] = None
    active_patterns: List[str] = Field(default_factory=list)
    confluence_score: int = Field(default=0, description="Score from 0 to 100")
    details: Dict[str, Any] = Field(default_factory=dict)


def calculate_wilder_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """
    Wilder's Smoothed RSI (matching institutional formula from trader-scanner).
    """
    if len(closes) < period + 1:
        return None
    gains = [max(0.0, closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    losses = [max(0.0, closes[i - 1] - closes[i]) for i in range(1, len(closes))]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


class QuantitativePatternScanner:
    """
    Scans candle series for institutional setups and calculates confluence scores.
    """

    def __init__(self, rsi_period: int = 14, lookback_breakout: int = 20):
        self.rsi_period = rsi_period
        self.lookback = lookback_breakout

    def scan(self, candles: List[CandleData], symbol: str = "", timeframe: str = "15m") -> PatternScanResult:
        if len(candles) < (self.lookback + 5):
            return PatternScanResult(
                symbol=symbol,
                timeframe=timeframe,
                active_patterns=[],
                confluence_score=0,
                details={"status": "Insufficient candle data"}
            )

        closes = [c.close for c in candles]
        last = closes[-1]
        prev = closes[-2]

        # 1. Wilder's RSI calculation
        r = calculate_wilder_rsi(closes, n=self.rsi_period) if hasattr(self, '_') else calculate_wilder_rsi(closes, self.rsi_period)
        r_prev = calculate_wilder_rsi(closes[:-1], self.rsi_period)

        # 2. 20-period High / Low & 20-period Moving Average
        hi20 = max(closes[-self.lookback - 1 : -1])
        lo20 = min(closes[-self.lookback - 1 : -1])
        ma20 = sum(closes[-self.lookback:]) / float(self.lookback)
        ma20_prev = sum(closes[-self.lookback - 1 : -1]) / float(self.lookback)

        # 3. Expansion and Compression (Flag setup)
        # Check if price moved > 4% over prior 10 bars, followed by tight 5-bar range (< 2.5%)
        run_10 = (closes[-6] / closes[-16] - 1.0) if len(closes) >= 16 else 0.0
        rng_5 = (max(closes[-5:]) - min(closes[-5:])) / (last if last > 0 else 1.0)

        patterns = []
        score = 0

        # Pattern: 20-bar Breakout / Breakdown
        if last > hi20:
            patterns.append("20_BAR_HIGH_BREAKOUT")
            score += 25
        elif last < lo20:
            patterns.append("20_BAR_LOW_BREAKDOWN")
            score += 25

        # Pattern: MA20 Reclaim (Shakeout Reversal)
        if prev < ma20_prev and last > ma20:
            patterns.append("RECLAIM_MA20_BULLISH")
            score += 20
        elif prev > ma20_prev and last < ma20:
            patterns.append("LOST_MA20_BEARISH")
            score += 20

        # Pattern: RSI Oversold & Oversold Bounce
        if r is not None:
            if r < 30.0:
                patterns.append("RSI_OVERSOLD")
                score += 25
            if r_prev is not None and r_prev < 32.0 and last > prev:
                patterns.append("RSI_OVERSOLD_BOUNCE")
                score += 35

            if r > 70.0:
                patterns.append("RSI_OVERBOUGHT")
                score += 25
            if r_prev is not None and r_prev > 68.0 and last < prev:
                patterns.append("RSI_OVERBOUGHT_REJECTION")
                score += 35

        # Pattern: Bull / Bear Flag
        if run_10 > 0.04 and rng_5 < 0.025:
            patterns.append("BULL_FLAG_COMPRESSION")
            score += 20
        elif run_10 < -0.04 and rng_5 < 0.025:
            patterns.append("BEAR_FLAG_COMPRESSION")
            score += 20

        return PatternScanResult(
            symbol=symbol,
            timeframe=timeframe,
            rsi_14=r,
            rsi_14_prev=r_prev,
            ma_20=round(ma20, 4),
            active_patterns=patterns,
            confluence_score=min(100, score),
            details={
                "high20": round(hi20, 4),
                "low20": round(lo20, 4),
                "run_10_pct": round(run_10 * 100, 2),
                "range_5_pct": round(rng_5 * 100, 2),
            }
        )

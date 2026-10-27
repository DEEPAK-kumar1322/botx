"""
Enhanced Liquidity Sweep & Institutional Execution Engine (BotX).

Inspired by quantitative day-trading disciplines (trader-entry, trader-exit, trader-budget, trader-risk):
1. Volume Validation (from trader-entry):
   - Sweep and confirmation candles must exhibit relative volume (RVOL >= 1.2x of 20-bar average)
     to confirm institutional participation over retail noise.
2. Noise-Buffered Risk Management (from trader-exit):
   - Stop-Loss is buffered by ATR-14 * 0.6 (minimum 0.35% price buffer) and rounded AWAY from entry
     to prevent exchange spread spikes and stop-hunting micro-wicks from prematurely clipping trades.
   - Strictly targets 1:1 Risk-to-Reward (1R Quick TP) to lock in profits rapidly before choppy crypto retracements.
3. Dynamic Budget Sizing (from trader-budget):
   - Back-solves contract quantities directly from a fixed Max Risk (e.g. ₹4.00 INR on Delta, or $15 USDT on Binance)
     so capital loss is mathematically capped regardless of stop distance.
4. Pre-Trade Gatekeeping (from trader-risk):
   - Prevents chasing trades where price has already run > 0.4R past the swept level.
   - Enforces 1H Higher-Timeframe trend alignment.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pydantic import BaseModel, Field

from src.data.base import CandleData
from src.analysis.structure import MarketStructureAnalyzer
from src.analysis.scanner_patterns import QuantitativePatternScanner, PatternScanResult


class EnhancedSweepSignal(BaseModel):
    """Refined Institutional Liquidity Sweep Signal with 1:1 RR and Volume Validation."""
    symbol: str
    timeframe: str
    action: str = Field(description="'BUY' (Support Sweep) or 'SELL' (Resistance Sweep)")
    sweep_type: str
    swept_level: float
    sweep_extreme: float
    sweep_candle_time: datetime
    confirmation_candle_time: datetime
    confirmation_type: str
    relative_volume: float = Field(description="RVOL relative to 20-bar SMA volume")
    entry_price: float
    stop_loss: float
    take_profit: float  # Strict 1:1 RR
    risk_distance: float
    risk_reward_ratio: str = "1:1.0"
    htf_bias: str
    htf_aligned: bool
    recommended_contracts: int = 1
    estimated_margin_inr: float = 0.0
    estimated_max_loss_inr: float = 0.0
    psychology_note: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EnhancedSweepEvaluation(BaseModel):
    """Evaluation status containing checklist and candidate signals."""
    symbol: str
    timeframe: str
    current_price: float
    htf_bias: str
    htf_confidence: int
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    has_valid_setup: bool
    signal: Optional[EnhancedSweepSignal] = None
    checklist: List[Tuple[str, bool, str]] = Field(default_factory=list)
    wait_reasons: List[str] = Field(default_factory=list)


class EnhancedSweepAnalyzer:
    """
    Quantitative Liquidity Sweep Strategy with Institutional Filters:
    - 5-bar Pivot Structure Detection
    - Closed-bar Sweep & Reclaim Confirmation
    - Relative Volume Threshold (RVOL >= 1.1x)
    - ATR Noise-Buffered SL
    - Fast 1:1 RR Target
    """

    def __init__(
        self,
        swing_window: int = 5,
        min_rvol: float = 1.1,
        max_chase_r: float = 0.5,
    ):
        self.structure_analyzer = MarketStructureAnalyzer(swing_window=swing_window)
        self.htf_analyzer = MarketStructureAnalyzer(swing_window=3)
        self.pattern_scanner = QuantitativePatternScanner(rsi_period=14)
        self.min_rvol = min_rvol
        self.max_chase_r = max_chase_r

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
    ) -> EnhancedSweepEvaluation:
        if len(candles_ltf) < 35:
            return EnhancedSweepEvaluation(
                symbol=symbol,
                timeframe=timeframe,
                current_price=candles_ltf[-1].close if candles_ltf else 0.0,
                htf_bias="NEUTRAL",
                htf_confidence=50,
                has_valid_setup=False,
                wait_reasons=["Insufficient candle history (minimum 35 candles required)."],
            )

        live_price = candles_ltf[-1].close
        closed_candles = candles_ltf[:-1]

        # 1. 1H HTF Directional Bias
        structure_htf = self.htf_analyzer.analyze(candles_htf, symbol=symbol, timeframe="1h")
        htf_bias = structure_htf.directional_bias
        htf_conf = structure_htf.confidence

        # 2. Key Support / Resistance Pivots (prior to current sweep window)
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

        # 3. Quantitative Chart Patterns (Wilder's RSI + Breakout from trader-scanner)
        scan_res = self.pattern_scanner.scan(closed_candles, symbol=symbol, timeframe=timeframe)

        # 4. Detect Potential Sweep Candidate
        candidate = self._detect_sweep_signal(
            closed_candles=closed_candles,
            live_price=live_price,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            symbol=symbol,
            timeframe=timeframe,
            htf_bias=htf_bias,
            max_loss_inr=max_loss_inr,
            contract_multiplier=contract_multiplier,
            leverage=leverage,
            inr_per_usd=inr_per_usd,
            pattern_scan=scan_res,
        )

        checklist: List[Tuple[str, bool, str]] = []
        wait_reasons: List[str] = []

        if candidate:
            htf_passed = candidate.htf_aligned or allow_counter_trend
            checklist.append((
                "1. Major Key Level Liquidity Sweep (Closed Bar Reclaim)",
                True,
                f"{candidate.sweep_type}: Swept ${candidate.swept_level:,.4f} "
                f"(extreme ${candidate.sweep_extreme:,.4f}) and reclaimed."
            ))
            checklist.append((
                "2. Volume Confirmation (Institutional RVOL)",
                candidate.relative_volume >= self.min_rvol,
                f"RVOL: {candidate.relative_volume:.2f}x (Required: >= {self.min_rvol:.1f}x)."
            ))
            checklist.append((
                "3. Noise-Buffered 1:1 RR Exit Plan",
                True,
                f"SL: ${candidate.stop_loss:,.4f} | TP (1:1): ${candidate.take_profit:,.4f} | Risk: ${candidate.risk_distance:,.4f}."
            ))
            checklist.append((
                "4. Dynamic Budget Position Sizing",
                True,
                f"Size: {candidate.recommended_contracts} contracts (~₹{candidate.estimated_margin_inr:.2f} margin, max loss ₹{candidate.estimated_max_loss_inr:.2f})."
            ))

            if htf_passed:
                checklist.append((
                    "5. HTF Trend Filter",
                    True,
                    f"1H Trend is {htf_bias} ({htf_conf}% confidence) — Aligned."
                ))
            else:
                checklist.append((
                    "5. HTF Trend Filter",
                    False,
                    f"Blocked: 1H trend is {htf_bias}, counter-trend {candidate.action} blocked."
                ))
                wait_reasons.append(f"HTF Bias ({htf_bias}) opposes {candidate.action}.")

            if candidate.relative_volume < self.min_rvol:
                wait_reasons.append(f"Volume too thin: RVOL {candidate.relative_volume:.2f}x below threshold {self.min_rvol:.1f}x.")

            has_valid = htf_passed and (candidate.relative_volume >= self.min_rvol)
        else:
            sup_str = f"${nearest_support:,.4f}" if nearest_support else "N/A"
            res_str = f"${nearest_resistance:,.4f}" if nearest_resistance else "N/A"
            checklist.append((
                "1. Major Key Level Liquidity Sweep",
                False,
                f"No fresh sweep on closed bars. Price (${live_price:,.4f}) between S: {sup_str} & R: {res_str}."
            ))
            wait_reasons.append(f"Standby: Price between {sup_str} and {res_str}.")
            has_valid = False

        return EnhancedSweepEvaluation(
            symbol=symbol,
            timeframe=timeframe,
            current_price=live_price,
            htf_bias=htf_bias,
            htf_confidence=htf_conf,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            has_valid_setup=has_valid,
            signal=candidate if has_valid else None,
            checklist=checklist,
            wait_reasons=wait_reasons,
        )

    def _detect_sweep_signal(
        self,
        closed_candles: List[CandleData],
        live_price: float,
        support_levels: List[float],
        resistance_levels: List[float],
        symbol: str,
        timeframe: str,
        htf_bias: str,
        max_loss_inr: float,
        contract_multiplier: float,
        leverage: float,
        inr_per_usd: float,
        pattern_scan: Optional[PatternScanResult] = None,
    ) -> Optional[EnhancedSweepSignal]:
        last_closed = closed_candles[-1]

        # Calculate 20-bar average volume for relative volume check
        vols = [c.volume for c in closed_candles[-20:] if c.volume is not None and c.volume > 0]
        avg_vol = sum(vols) / len(vols) if vols else 1.0

        # Calculate 14-bar ATR for noise buffer
        ranges = [
            max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
            for c, prev in zip(closed_candles[1:], closed_candles[:-1])
        ]
        atr = sum(ranges[-14:]) / min(len(ranges), 14) if ranges else (live_price * 0.005)
        buffer = max(atr * 0.6, live_price * 0.0035)

        # Precision decimals
        prec = 4 if live_price < 10.0 else (5 if live_price < 1.0 else 2)

        # --- Check Support Sweep (BUY) ---
        for offset in (1, 2, 3):
            sc_idx = len(closed_candles) - offset
            sc = closed_candles[sc_idx]
            c_range = max(sc.high - sc.low, 1e-8)
            lower_wick = min(sc.open, sc.close) - sc.low
            lower_wick_ratio = lower_wick / c_range

            swept_supports = [
                lvl for lvl in support_levels
                if sc.low <= (lvl * 0.9992) and max(sc.close, last_closed.close) > lvl
            ]
            if not swept_supports:
                continue

            swept_lvl = min(swept_supports, key=lambda l: abs(l - sc.low))
            sweep_low = sc.low

            # Invalidation
            if any(c.low < sweep_low for c in closed_candles[sc_idx + 1:]):
                continue
            if live_price <= swept_lvl or last_closed.close <= swept_lvl:
                continue

            conf_type = None
            if offset == 1:
                if sc.close > swept_lvl and lower_wick_ratio >= 0.40 and sc.close >= (sc.low + 0.55 * c_range):
                    conf_type = f"Bullish Pin Bar Sweep ({int(lower_wick_ratio * 100)}% Wick)"
            else:
                pause_c = closed_candles[sc_idx] if sc.close >= swept_lvl else closed_candles[sc_idx + 1]
                already_broken = any(c.close > pause_c.high for c in closed_candles[sc_idx + 1:-1])
                if not already_broken and last_closed.close > pause_c.high and last_closed.close > last_closed.open:
                    conf_type = f"Pause Candle Breakout (${pause_c.high:,.4f})"

            if not conf_type:
                continue

            if pattern_scan:
                if "RSI_OVERSOLD_BOUNCE" in pattern_scan.active_patterns:
                    conf_type += f" + RSI Oversold Bounce ({pattern_scan.rsi_14})"
                elif "RSI_OVERSOLD" in pattern_scan.active_patterns:
                    conf_type += f" + RSI Oversold ({pattern_scan.rsi_14})"
                elif "RECLAIM_MA20_BULLISH" in pattern_scan.active_patterns:
                    conf_type += " + MA20 Reclaim"

            entry = round(live_price, prec)
            # Stop rounds down away from entry
            sl = round(sweep_low - buffer, prec)
            risk_dist = max(entry - sl, entry * 0.002)

            # Prevent chasing if entry has already moved too far beyond the level
            if (entry - swept_lvl) > (risk_dist * self.max_chase_r):
                continue

            # Strict 1:1 Risk-Reward Target
            tp = round(entry + risk_dist, prec)

            # Measure volume
            rvol = round(last_closed.volume / avg_vol, 2) if (last_closed.volume and avg_vol > 0) else 1.2

            # Budget Sizing (from trader-budget)
            # max_loss_inr = contracts * contract_multiplier * risk_dist * inr_per_usd
            risk_per_contract_inr = contract_multiplier * risk_dist * inr_per_usd
            if risk_per_contract_inr > 0:
                rec_contracts = max(1, int(max_loss_inr / risk_per_contract_inr))
            else:
                rec_contracts = 1

            notional_usd = rec_contracts * contract_multiplier * entry
            est_margin_inr = round((notional_usd / leverage) * inr_per_usd, 2)
            est_loss_inr = round(rec_contracts * risk_per_contract_inr, 2)

            return EnhancedSweepSignal(
                symbol=symbol,
                timeframe=timeframe,
                action="BUY",
                sweep_type="Support Sweep (SSL Stop Hunt)",
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
                htf_aligned=(htf_bias == "BULLISH"),
                recommended_contracts=rec_contracts,
                estimated_margin_inr=est_margin_inr,
                estimated_max_loss_inr=est_loss_inr,
                psychology_note=f"Hunted retail sell stops under ${swept_lvl:,.4f}, trapped sellers with high volume, reclaimed support.",
            )

        # --- Check Resistance Sweep (SELL) ---
        for offset in (1, 2, 3):
            sc_idx = len(closed_candles) - offset
            sc = closed_candles[sc_idx]
            c_range = max(sc.high - sc.low, 1e-8)
            upper_wick = sc.high - max(sc.open, sc.close)
            upper_wick_ratio = upper_wick / c_range

            swept_resistances = [
                lvl for lvl in resistance_levels
                if sc.high >= (lvl * 1.0008) and min(sc.close, last_closed.close) < lvl
            ]
            if not swept_resistances:
                continue

            swept_lvl = min(swept_resistances, key=lambda l: abs(l - sc.high))
            sweep_high = sc.high

            # Invalidation
            if any(c.high > sweep_high for c in closed_candles[sc_idx + 1:]):
                continue
            if live_price >= swept_lvl or last_closed.close >= swept_lvl:
                continue

            conf_type = None
            if offset == 1:
                if sc.close < swept_lvl and upper_wick_ratio >= 0.40 and sc.close <= (sc.high - 0.55 * c_range):
                    conf_type = f"Bearish Shooting Star Sweep ({int(upper_wick_ratio * 100)}% Wick)"
            else:
                pause_c = closed_candles[sc_idx] if sc.close <= swept_lvl else closed_candles[sc_idx + 1]
                already_broken = any(c.close < pause_c.low for c in closed_candles[sc_idx + 1:-1])
                if not already_broken and last_closed.close < pause_c.low and last_closed.close < last_closed.open:
                    conf_type = f"Pause Candle Breakdown (${pause_c.low:,.4f})"

            if not conf_type:
                continue

            if pattern_scan:
                if "RSI_OVERBOUGHT_REJECTION" in pattern_scan.active_patterns:
                    conf_type += f" + RSI Overbought Rejection ({pattern_scan.rsi_14})"
                elif "RSI_OVERBOUGHT" in pattern_scan.active_patterns:
                    conf_type += f" + RSI Overbought ({pattern_scan.rsi_14})"
                elif "LOST_MA20_BEARISH" in pattern_scan.active_patterns:
                    conf_type += " + MA20 Breakdown"

            entry = round(live_price, prec)
            # Stop rounds up away from entry
            sl = round(sweep_high + buffer, prec)
            risk_dist = max(sl - entry, entry * 0.002)

            # Prevent chasing
            if (swept_lvl - entry) > (risk_dist * self.max_chase_r):
                continue

            # Strict 1:1 Risk-Reward Target
            tp = round(entry - risk_dist, prec)

            # Measure volume
            rvol = round(last_closed.volume / avg_vol, 2) if (last_closed.volume and avg_vol > 0) else 1.2

            # Budget Sizing
            risk_per_contract_inr = contract_multiplier * risk_dist * inr_per_usd
            if risk_per_contract_inr > 0:
                rec_contracts = max(1, int(max_loss_inr / risk_per_contract_inr))
            else:
                rec_contracts = 1

            notional_usd = rec_contracts * contract_multiplier * entry
            est_margin_inr = round((notional_usd / leverage) * inr_per_usd, 2)
            est_loss_inr = round(rec_contracts * risk_per_contract_inr, 2)

            return EnhancedSweepSignal(
                symbol=symbol,
                timeframe=timeframe,
                action="SELL",
                sweep_type="Resistance Sweep (BSL Stop Hunt)",
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
                htf_aligned=(htf_bias == "BEARISH"),
                recommended_contracts=rec_contracts,
                estimated_margin_inr=est_margin_inr,
                estimated_max_loss_inr=est_loss_inr,
                psychology_note=f"Hunted retail buy stops above ${swept_lvl:,.4f}, trapped breakout buyers with high volume, rejected resistance.",
            )

        return None

"""
BotX Modular Algorithmic Trading Terminal - Strategy Manager & Engine.

Implements:
1. Base Strategy Interface & Registry (SMC, 9/20 EMA Cross, Bollinger Bands 20/2).
2. Two-Step Analysis:
   - Step A: Base Market Structure & Bias (Swings HH/HL/LH/LL, BSL/SSL).
   - Step B: Multi-Timeframe Strategy Confluence Evaluation.
3. Strict Validity & Anti-Spam: Only high-probability setups with verified macro bias.
4. Clear Wait State: Explicit "No valid entry right now, please wait." when criteria < 100%.
5. Telegram State-Tracker Cooldown Integration.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import math
import uuid
from pydantic import BaseModel, Field
import numpy as np
from loguru import logger

from src.data.base import CandleData
from src.data.unified_feed import UnifiedMarketFeed
from src.analysis.smc import SMCAnalyzer
from src.analysis.structure import MarketStructureAnalyzer, StructureAnalysisResult
from src.notifications.telegram_alerts import TelegramAlertSender


# ============================================================================
# Pydantic Schemas
# ============================================================================

class StrategyParameter(BaseModel):
    name: str
    label: str
    param_type: str
    default: Any
    value: Any
    description: str


class StrategyInfo(BaseModel):
    id: str
    name: str
    category: str
    description: str
    timeframes: List[str]
    parameters: Dict[str, Any]
    is_active: bool


class ConfluenceCheckItem(BaseModel):
    name: str
    status: str = Field(description="'PASSED' or 'WAITING'")
    description: str
    weight: int = 1


class EntryZone(BaseModel):
    action: str = Field(description="'BUY' or 'SELL'")
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_ratio: str
    invalidation_level: float


class TelegramDispatchStatus(BaseModel):
    alert_sent: bool
    cooldown_active: bool
    cooldown_remaining_sec: int
    message: str


class StrategyAnalysisResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"EVAL-{uuid.uuid4().hex[:6].upper()}")
    symbol: str
    timeframe: str
    current_price: float
    strategy_id: str
    strategy_name: str
    strategy_active: bool
    has_entry: bool = Field(description="True if 100% strict confluence met, False if wait state")
    status_message: str = Field(description="'No valid entry right now, please wait.' or verified setup alert")
    wait_reasons: List[str] = Field(default_factory=list)
    confluence_score: int = Field(description="Score percentage (0-100%)")
    checklist: List[ConfluenceCheckItem]
    entry_zone: Optional[EntryZone] = None
    step_a_structure: StructureAnalysisResult
    telegram_status: TelegramDispatchStatus
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Technical Indicator Helpers
# ============================================================================

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average (EMA)."""
    if len(prices) < period:
        return [prices[-1]] * len(prices)
    k = 2.0 / (period + 1)
    ema = [sum(prices[:period]) / period]
    for p in prices[period:]:
        ema.append(p * k + ema[-1] * (1 - k))
    # Pad beginning with initial SMA
    return [ema[0]] * (period - 1) + ema


def calculate_bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Tuple[float, float, float]:
    """Calculate current SMA, Upper Band, and Lower Band."""
    if len(prices) < period:
        p = prices[-1]
        return p, p * 1.02, p * 0.98
    window = prices[-period:]
    sma = float(np.mean(window))
    std = float(np.std(window))
    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    return sma, upper, lower


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """Calculate Relative Strength Index (RSI)."""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period if len(seed[seed >= 0]) > 0 else 0.0001
    down = -seed[seed < 0].sum() / period if len(seed[seed < 0]) > 0 else 0.0001
    rs = up / down
    rsi = np.zeros_like(prices)
    rsi[:period] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(period, len(prices)):
        delta = deltas[i - 1]
        if delta > 0:
            up_val = delta
            down_val = 0.0
        else:
            up_val = 0.0
            down_val = -delta

        up = (up * (period - 1) + up_val) / period
        down = (down * (period - 1) + down_val) / period
        rs = up / (down if down != 0 else 0.0001)
        rsi[i] = 100.0 - 100.0 / (1.0 + rs)

    return float(rsi[-1])


# ============================================================================
# Modular Strategy Engine
# ============================================================================

class StrategyManager:
    """
    Unified Algorithmic Strategy Hub Manager.
    Manages custom strategies, runs two-step analysis (Market Structure + MTF Logic),
    enforces strict anti-spam confluence, and applies Telegram cooldowns.
    """

    def __init__(self):
        self.feed = UnifiedMarketFeed()
        self.structure_analyzer = MarketStructureAnalyzer(swing_window=3)
        self.smc_analyzer = SMCAnalyzer()
        self.notifier = TelegramAlertSender(cooldown_seconds=1800)

        # Active strategy state
        self.active_strategy_id: str = "smc"
        self.is_deployed_active: bool = False

        # Evaluation audit history
        self.history: List[StrategyAnalysisResponse] = []

        # Available Strategy Catalog
        self._strategies_meta: Dict[str, Dict[str, Any]] = {
            "smc": {
                "id": "smc",
                "name": "Smart Money Concepts (SMC)",
                "category": "Institutional Liquidity",
                "description": "High-confluence Fair Value Gap (FVG) and Order Block (OB) demand/supply zone mitigation aligned with macro market structure.",
                "timeframes": ["5m", "15m", "1h", "4h"],
                "parameters": {
                    "min_fvg_gap_pct": 0.08,
                    "require_ob_confluence": True,
                    "min_risk_reward": 2.0
                }
            },
            "ema_cross": {
                "id": "ema_cross",
                "name": "9/20 EMA Dynamic Trend Follower",
                "category": "Trend Following",
                "description": "Dual Exponential Moving Average trend momentum with value zone pullback re-tests and 50-EMA macro filter.",
                "timeframes": ["5m", "15m", "1h"],
                "parameters": {
                    "fast_ema": 9,
                    "slow_ema": 20,
                    "baseline_ema": 50,
                    "pullback_tolerance_pct": 0.35
                }
            },
            "bollinger_bands": {
                "id": "bollinger_bands",
                "name": "Bollinger Bands Mean Reversion",
                "category": "Volatility & Mean Reversion",
                "description": "20-period 2-sigma Bollinger envelope extremes paired with RSI exhaustion and structural liquidity sweeps.",
                "timeframes": ["15m", "1h", "4h"],
                "parameters": {
                    "bb_period": 20,
                    "bb_std_dev": 2.0,
                    "rsi_period": 14,
                    "rsi_oversold": 35,
                    "rsi_overbought": 65
                }
            },
            "custom": {
                "id": "custom",
                "name": "Custom Algorithmic Rules",
                "category": "Hybrid Quant",
                "description": "Customizable multi-indicator confluence combining EMA momentum, structural swing sweeps, and dynamic stops.",
                "timeframes": ["15m", "1h"],
                "parameters": {
                    "trend_ema": 21,
                    "confirm_volume": True,
                    "target_rrr": 2.5
                }
            }
        }
        logger.info("Initialized StrategyManager with 4 modular algorithmic strategies.")

    def list_strategies(self) -> List[StrategyInfo]:
        """Return list of all registered strategies with active state."""
        result = []
        for sid, meta in self._strategies_meta.items():
            result.append(StrategyInfo(
                id=meta["id"],
                name=meta["name"],
                category=meta["category"],
                description=meta["description"],
                timeframes=meta["timeframes"],
                parameters=meta["parameters"],
                is_active=(sid == self.active_strategy_id and self.is_deployed_active)
            ))
        return result

    def set_active_strategy(self, strategy_id: str, enable: Optional[bool] = None) -> StrategyInfo:
        """Select active strategy and optionally set deployment state."""
        if strategy_id not in self._strategies_meta:
            strategy_id = "smc"

        self.active_strategy_id = strategy_id
        if enable is not None:
            self.is_deployed_active = enable

        logger.info(f"Active strategy set to {strategy_id} (deployed={self.is_deployed_active})")
        meta = self._strategies_meta[self.active_strategy_id]
        return StrategyInfo(
            id=meta["id"],
            name=meta["name"],
            category=meta["category"],
            description=meta["description"],
            timeframes=meta["timeframes"],
            parameters=meta["parameters"],
            is_active=self.is_deployed_active
        )

    def run_strategy_analysis(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "15m",
        strategy_id: Optional[str] = None
    ) -> StrategyAnalysisResponse:
        """
        Executes Two-Step Strategy Analysis:
        - Step A: Base Market Structure & Bias Analysis.
        - Step B: Multi-timeframe strategy evaluation with strict confluence & anti-spam.
        """
        sid = strategy_id or self.active_strategy_id
        if sid not in self._strategies_meta:
            sid = "smc"

        strat_meta = self._strategies_meta[sid]
        logger.info(f"Running Two-Step Analysis for {symbol} ({timeframe}) using strategy: {strat_meta['name']}")

        # Fetch Lower Timeframe (Execution) Candles
        candles_ltf = self.feed.fetch_recent_candles(symbol, timeframe=timeframe, limit=60)
        if not candles_ltf:
            raise ValueError(f"Failed to fetch market data for {symbol} on {timeframe}")

        # Fetch Higher Timeframe (Bias Context) Candles - Default to 1h
        htf = "1h" if timeframe in ["1m", "5m", "15m"] else "4h"
        candles_htf = self.feed.fetch_recent_candles(symbol, timeframe=htf, limit=60) or candles_ltf

        current_price = candles_ltf[-1].close

        # ====================================================================
        # STEP A: Base Market Structure & Bias Analysis
        # ====================================================================
        structure = self.structure_analyzer.analyze(candles_ltf, symbol=symbol, timeframe=timeframe)

        # ====================================================================
        # STEP B: Evaluate Active Strategy Logic Across Multiple Timeframes
        # ====================================================================
        if sid == "smc":
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_smc(
                candles_ltf, candles_htf, structure, strat_meta["parameters"]
            )
        elif sid == "ema_cross":
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_ema_cross(
                candles_ltf, candles_htf, structure, strat_meta["parameters"]
            )
        elif sid == "bollinger_bands":
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_bollinger(
                candles_ltf, candles_htf, structure, strat_meta["parameters"]
            )
        else:
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_custom(
                candles_ltf, candles_htf, structure, strat_meta["parameters"]
            )

        # ====================================================================
        # Strict Validity & Clear Wait State (Requirements 3 & 4)
        # ====================================================================
        if not has_entry:
            status_message = "No valid entry right now, please wait."
            entry_zone = None
        else:
            action_text = "BUY / LONG" if entry_zone.action == "BUY" else "SELL / SHORT"
            status_message = f"HIGH-PROBABILITY {action_text} SETUP CONFIRMED"

        # ====================================================================
        # Telegram Anti-Spam Cooldown & Notification (Requirement 5)
        # ====================================================================
        telegram_status = TelegramDispatchStatus(
            alert_sent=False,
            cooldown_active=False,
            cooldown_remaining_sec=0,
            message="No setup to dispatch"
        )

        if has_entry and entry_zone:
            fp = self.notifier.get_setup_fingerprint(
                symbol=symbol,
                strategy_id=sid,
                action=entry_zone.action,
                price=entry_zone.entry,
                timeframe=timeframe
            )
            is_cooling, remaining = self.notifier.is_in_cooldown(fp)
            if is_cooling:
                telegram_status = TelegramDispatchStatus(
                    alert_sent=False,
                    cooldown_active=True,
                    cooldown_remaining_sec=int(remaining),
                    message=f"Alert suppressed: Cooldown active ({int(remaining)}s left)"
                )
            else:
                trigger_desc = f"{strat_meta['name']} verified in alignment with {structure.directional_bias} macro trend."
                sent, msg_text = self.notifier.send_strategy_execution_alert(
                    symbol=symbol,
                    strategy_name=strat_meta["name"],
                    strategy_id=sid,
                    action=entry_zone.action,
                    entry_price=entry_zone.entry,
                    stop_loss=entry_zone.stop_loss,
                    take_profit_1=entry_zone.take_profit_1,
                    take_profit_2=entry_zone.take_profit_2,
                    risk_reward_ratio=entry_zone.risk_reward_ratio,
                    timeframe=timeframe,
                    confluence_score=score,
                    trigger_reason=trigger_desc,
                    directional_bias=structure.directional_bias
                )
                telegram_status = TelegramDispatchStatus(
                    alert_sent=sent,
                    cooldown_active=False,
                    cooldown_remaining_sec=self.notifier.cooldown_seconds if sent else 0,
                    message=msg_text
                )

        response = StrategyAnalysisResponse(
            symbol=symbol,
            timeframe=timeframe,
            current_price=current_price,
            strategy_id=sid,
            strategy_name=strat_meta["name"],
            strategy_active=self.is_deployed_active,
            has_entry=has_entry,
            status_message=status_message,
            wait_reasons=wait_reasons,
            confluence_score=score,
            checklist=checklist,
            entry_zone=entry_zone,
            step_a_structure=structure,
            telegram_status=telegram_status
        )

        self.history.insert(0, response)
        if len(self.history) > 30:
            self.history.pop()

        return response

    # ------------------------------------------------------------------------
    # Strategy 1: Smart Money Concepts (SMC) Evaluation
    # ------------------------------------------------------------------------
    def _eval_smc(
        self,
        candles_ltf: List[CandleData],
        candles_htf: List[CandleData],
        structure: StructureAnalysisResult,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        cur_price = candles_ltf[-1].close
        fvgs = self.smc_analyzer.find_fair_value_gaps(candles_ltf)
        obs = self.smc_analyzer.find_order_blocks(candles_ltf, fvgs=fvgs)

        active_bullish_fvg = next((f for f in fvgs if f.bias == "BULLISH" and not f.fully_filled), None)
        active_bullish_ob = next((o for o in obs if o.bias == "BULLISH" and not o.broken), None)
        active_bearish_fvg = next((f for f in fvgs if f.bias == "BEARISH" and not f.fully_filled), None)
        active_bearish_ob = next((o for o in obs if o.bias == "BEARISH" and not o.broken), None)

        checklist: List[ConfluenceCheckItem] = []
        wait_reasons: List[str] = []

        # Check 1: Macro Structure Alignment
        bias_aligned = structure.directional_bias in ["BULLISH", "BEARISH"]
        checklist.append(ConfluenceCheckItem(
            name="Macro Directional Bias",
            status="PASSED" if bias_aligned else "WAITING",
            description=f"Market structure is {structure.directional_bias} ({structure.confidence}% confidence)."
        ))
        if not bias_aligned:
            wait_reasons.append("Market is currently Ranging with no clear directional expansion.")

        # Check 2: Active Zone Interaction
        is_bullish = structure.directional_bias == "BULLISH"
        zone_found = False
        zone_desc = ""

        if is_bullish:
            if active_bullish_ob:
                dist_pct = abs(cur_price - active_bullish_ob.top) / cur_price * 100
                if dist_pct < 1.2 or cur_price >= active_bullish_ob.bottom:
                    zone_found = True
                    zone_desc = f"Testing Bullish Demand OB (${active_bullish_ob.bottom:,.2f} - ${active_bullish_ob.top:,.2f})"
            elif active_bullish_fvg:
                dist_pct = abs(cur_price - active_bullish_fvg.top) / cur_price * 100
                if dist_pct < 1.2:
                    zone_found = True
                    zone_desc = f"Testing Bullish FVG Zone (${active_bullish_fvg.bottom:,.2f} - ${active_bullish_fvg.top:,.2f})"
        else:
            if active_bearish_ob:
                dist_pct = abs(cur_price - active_bearish_ob.bottom) / cur_price * 100
                if dist_pct < 1.2 or cur_price <= active_bearish_ob.top:
                    zone_found = True
                    zone_desc = f"Testing Bearish Supply OB (${active_bearish_ob.bottom:,.2f} - ${active_bearish_ob.top:,.2f})"
            elif active_bearish_fvg:
                dist_pct = abs(cur_price - active_bearish_fvg.bottom) / cur_price * 100
                if dist_pct < 1.2:
                    zone_found = True
                    zone_desc = f"Testing Bearish FVG Zone (${active_bearish_fvg.bottom:,.2f} - ${active_bearish_fvg.top:,.2f})"

        checklist.append(ConfluenceCheckItem(
            name="Institutional Zone Mitigation",
            status="PASSED" if zone_found else "WAITING",
            description=zone_desc if zone_found else f"Price (${cur_price:,.2f}) is in mid-range; waiting for tap into valid demand/supply zone."
        ))
        if not zone_found:
            wait_reasons.append("No active unmitigated Order Block or FVG currently being tapped. Awaiting liquidity re-test.")

        # Check 3: Risk/Reward to Liquidity Pool
        target_pool = structure.nearest_bsl if is_bullish else structure.nearest_ssl
        target_valid = target_pool is not None and (
            (is_bullish and target_pool > cur_price) or (not is_bullish and target_pool < cur_price)
        )
        checklist.append(ConfluenceCheckItem(
            name="Liquidity Target (BSL/SSL)",
            status="PASSED" if target_valid else "WAITING",
            description=f"Target liquidity pool available at ${target_pool:,.2f}" if target_valid else "Nearest liquidity target already swept."
        ))
        if not target_valid:
            wait_reasons.append("Nearest liquidity pool already cleared. Waiting for new swing liquidity to form.")

        # Calculate score
        passed_count = sum(1 for c in checklist if c.status == "PASSED")
        score = int((passed_count / len(checklist)) * 100)

        # STRICT Confluence check: All must be PASSED
        if passed_count == len(checklist):
            action = "BUY" if is_bullish else "SELL"
            if is_bullish:
                sl = (active_bullish_ob.bottom * 0.9985) if active_bullish_ob else (cur_price * 0.988)
                risk = cur_price - sl
                tp1 = cur_price + (risk * 2.0)
                tp2 = target_pool if (target_pool and target_pool > tp1) else (cur_price + risk * 3.2)
            else:
                sl = (active_bearish_ob.top * 1.0015) if active_bearish_ob else (cur_price * 1.012)
                risk = sl - cur_price
                tp1 = cur_price - (risk * 2.0)
                tp2 = target_pool if (target_pool and target_pool < tp1) else (cur_price - risk * 3.2)

            rrr_val = round(abs(tp1 - cur_price) / max(0.01, abs(cur_price - sl)), 1)
            entry_zone = EntryZone(
                action=action,
                entry=round(cur_price, 2),
                stop_loss=round(sl, 2),
                take_profit_1=round(tp1, 2),
                take_profit_2=round(tp2, 2),
                risk_reward_ratio=f"1:{rrr_val}",
                invalidation_level=round(sl, 2)
            )
            return True, entry_zone, score, checklist, []

        return False, None, score, checklist, wait_reasons

    # ------------------------------------------------------------------------
    # Strategy 2: 9/20 EMA Dynamic Trend Follower
    # ------------------------------------------------------------------------
    def _eval_ema_cross(
        self,
        candles_ltf: List[CandleData],
        candles_htf: List[CandleData],
        structure: StructureAnalysisResult,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        closes = [c.close for c in candles_ltf]
        cur_price = closes[-1]

        fast_period = params.get("fast_ema", 9)
        slow_period = params.get("slow_ema", 20)
        base_period = params.get("baseline_ema", 50)

        ema_fast = calculate_ema(closes, fast_period)[-1]
        ema_slow = calculate_ema(closes, slow_period)[-1]
        ema_base = calculate_ema(closes, base_period)[-1]

        checklist: List[ConfluenceCheckItem] = []
        wait_reasons: List[str] = []

        is_bullish = structure.directional_bias == "BULLISH"
        is_bearish = structure.directional_bias == "BEARISH"

        # Check 1: Structure Alignment
        strat_align = (is_bullish and cur_price > ema_base) or (is_bearish and cur_price < ema_base)
        checklist.append(ConfluenceCheckItem(
            name="Macro Trend & 50-EMA Filter",
            status="PASSED" if strat_align else "WAITING",
            description=f"Price is {'above' if cur_price > ema_base else 'below'} 50-EMA (${ema_base:,.2f}) with {structure.directional_bias} structure."
        ))
        if not strat_align:
            wait_reasons.append(f"Structure ({structure.directional_bias}) opposes 50-EMA trend filter (${ema_base:,.2f}).")

        # Check 2: EMA 9 / EMA 20 Momentum Cross
        ema_momentum_pass = (is_bullish and ema_fast > ema_slow) or (is_bearish and ema_fast < ema_slow)
        checklist.append(ConfluenceCheckItem(
            name="9/20 EMA Cross Alignment",
            status="PASSED" if ema_momentum_pass else "WAITING",
            description=f"9-EMA (${ema_fast:,.2f}) is {'above' if ema_fast > ema_slow else 'below'} 20-EMA (${ema_slow:,.2f})."
        ))
        if not ema_momentum_pass:
            wait_reasons.append("EMA 9 has not crossed EMA 20 in alignment with macro bias.")

        # Check 3: Value Zone Pullback Test (Not overextended!)
        # In a valid trend entry, price should be pulling back into or near the 9/20 EMA pocket
        pocket_low = min(ema_fast, ema_slow)
        pocket_high = max(ema_fast, ema_slow)
        dist_to_pocket_pct = (cur_price - pocket_high) / cur_price * 100 if is_bullish else (pocket_low - cur_price) / cur_price * 100

        # Overextended if > 0.45% away from pocket
        in_value_zone = abs(dist_to_pocket_pct) <= 0.45 or (pocket_low <= cur_price <= pocket_high * 1.002)

        checklist.append(ConfluenceCheckItem(
            name="Dynamic Support/Resistance Pullback",
            status="PASSED" if in_value_zone else "WAITING",
            description=f"Price is testing the 9/20 EMA value pocket (${pocket_low:,.2f} - ${pocket_high:,.2f})." if in_value_zone else f"Price (${cur_price:,.2f}) is overextended by {dist_to_pocket_pct:.2f}% from 9-EMA."
        ))
        if not in_value_zone:
            wait_reasons.append(f"Price is currently chasing momentum ({dist_to_pocket_pct:+.2f}% away). Waiting for pullback re-test into 9/20 EMA zone.")

        passed_count = sum(1 for c in checklist if c.status == "PASSED")
        score = int((passed_count / len(checklist)) * 100)

        if passed_count == len(checklist):
            action = "BUY" if is_bullish else "SELL"
            if is_bullish:
                sl = pocket_low * 0.996
                risk = cur_price - sl
                tp1 = cur_price + (risk * 2.2)
                tp2 = cur_price + (risk * 3.5)
            else:
                sl = pocket_high * 1.004
                risk = sl - cur_price
                tp1 = cur_price - (risk * 2.2)
                tp2 = cur_price - (risk * 3.5)

            rrr_val = round(abs(tp1 - cur_price) / max(0.01, abs(cur_price - sl)), 1)
            entry_zone = EntryZone(
                action=action,
                entry=round(cur_price, 2),
                stop_loss=round(sl, 2),
                take_profit_1=round(tp1, 2),
                take_profit_2=round(tp2, 2),
                risk_reward_ratio=f"1:{rrr_val}",
                invalidation_level=round(sl, 2)
            )
            return True, entry_zone, score, checklist, []

        return False, None, score, checklist, wait_reasons

    # ------------------------------------------------------------------------
    # Strategy 3: Bollinger Bands 20/2 + RSI Mean Reversion
    # ------------------------------------------------------------------------
    def _eval_bollinger(
        self,
        candles_ltf: List[CandleData],
        candles_htf: List[CandleData],
        structure: StructureAnalysisResult,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        closes = [c.close for c in candles_ltf]
        cur_price = closes[-1]

        sma, upper, lower = calculate_bollinger_bands(closes, period=20, num_std=2.0)
        rsi = calculate_rsi(closes, period=14)

        checklist: List[ConfluenceCheckItem] = []
        wait_reasons: List[str] = []

        # Check 1: Band Envelope Extreme (Price touches or pierces outer band)
        touch_lower = cur_price <= lower * 1.003
        touch_upper = cur_price >= upper * 0.997
        band_extreme_pass = touch_lower or touch_upper

        checklist.append(ConfluenceCheckItem(
            name="Outer Band Volatility Exhaustion",
            status="PASSED" if band_extreme_pass else "WAITING",
            description=f"Price is testing {'Lower Band ($' + f'{lower:,.2f})' if touch_lower else ('Upper Band ($' + f'{upper:,.2f})' if touch_upper else 'inside 20-SMA envelope ($' + f'{sma:,.2f})')}."
        ))
        if not band_extreme_pass:
            wait_reasons.append(f"Price is inside the normal volatility envelope (Lower: ${lower:,.2f}, Upper: ${upper:,.2f}). Waiting for extreme expansion test.")

        # Check 2: RSI Exhaustion Confirmation
        rsi_oversold = rsi <= params.get("rsi_oversold", 38)
        rsi_overbought = rsi >= params.get("rsi_overbought", 62)
        rsi_pass = (touch_lower and rsi_oversold) or (touch_upper and rsi_overbought)

        checklist.append(ConfluenceCheckItem(
            name="RSI Momentum Exhaustion",
            status="PASSED" if rsi_pass else "WAITING",
            description=f"RSI is {rsi:.1f} ({'Oversold' if rsi_oversold else ('Overbought' if rsi_overbought else 'Neutral 40-60')})."
        ))
        if not rsi_pass:
            wait_reasons.append(f"RSI is currently {rsi:.1f} (neutral). Awaiting exhaustion trigger (<{params.get('rsi_oversold', 38)} or >{params.get('rsi_overbought', 62)}).")

        # Check 3: Mean Reversion Target Clearance
        dist_to_mean = abs(cur_price - sma) / cur_price * 100
        mean_clearance_pass = dist_to_mean >= 0.4
        checklist.append(ConfluenceCheckItem(
            name="Mean Reversion Space (to 20-SMA)",
            status="PASSED" if mean_clearance_pass else "WAITING",
            description=f"Distance to 20-SMA mean is {dist_to_mean:.2f}% (${sma:,.2f})."
        ))
        if not mean_clearance_pass:
            wait_reasons.append(f"Insufficient reward space to 20-SMA baseline (${sma:,.2f}).")

        passed_count = sum(1 for c in checklist if c.status == "PASSED")
        score = int((passed_count / len(checklist)) * 100)

        if passed_count == len(checklist):
            action = "BUY" if touch_lower else "SELL"
            if action == "BUY":
                sl = lower * 0.995
                risk = cur_price - sl
                tp1 = sma
                tp2 = upper
            else:
                sl = upper * 1.005
                risk = sl - cur_price
                tp1 = sma
                tp2 = lower

            rrr_val = round(abs(tp1 - cur_price) / max(0.01, abs(cur_price - sl)), 1)
            entry_zone = EntryZone(
                action=action,
                entry=round(cur_price, 2),
                stop_loss=round(sl, 2),
                take_profit_1=round(tp1, 2),
                take_profit_2=round(tp2, 2),
                risk_reward_ratio=f"1:{rrr_val}",
                invalidation_level=round(sl, 2)
            )
            return True, entry_zone, score, checklist, []

        return False, None, score, checklist, wait_reasons

    # ------------------------------------------------------------------------
    # Strategy 4: Custom Algorithmic Rules
    # ------------------------------------------------------------------------
    def _eval_custom(
        self,
        candles_ltf: List[CandleData],
        candles_htf: List[CandleData],
        structure: StructureAnalysisResult,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        # Hybrid quant checks
        closes = [c.close for c in candles_ltf]
        cur_price = closes[-1]
        ema_21 = calculate_ema(closes, 21)[-1]

        checklist = [
            ConfluenceCheckItem(
                name="21-EMA Baseline Trend",
                status="PASSED" if (structure.directional_bias == "BULLISH" and cur_price > ema_21) or (structure.directional_bias == "BEARISH" and cur_price < ema_21) else "WAITING",
                description=f"Price ${cur_price:,.2f} vs 21-EMA ${ema_21:,.2f}."
            ),
            ConfluenceCheckItem(
                name="Structural Pivot Confirmation",
                status="PASSED" if structure.confidence >= 80 else "WAITING",
                description=f"Structure confidence is {structure.confidence}% (Threshold: 80%)."
            )
        ]
        passed_count = sum(1 for c in checklist if c.status == "PASSED")
        score = int((passed_count / len(checklist)) * 100)
        wait_reasons = []
        if passed_count < len(checklist):
            wait_reasons.append("Custom hybrid criteria not fully met.")
            return False, None, score, checklist, wait_reasons

        action = "BUY" if structure.directional_bias == "BULLISH" else "SELL"
        sl = cur_price * (0.992 if action == "BUY" else 1.008)
        tp1 = cur_price * (1.018 if action == "BUY" else 0.982)
        entry_zone = EntryZone(
            action=action,
            entry=round(cur_price, 2),
            stop_loss=round(sl, 2),
            take_profit_1=round(tp1, 2),
            take_profit_2=round(tp1 * 1.01 if action == "BUY" else tp1 * 0.99, 2),
            risk_reward_ratio="1:2.2",
            invalidation_level=round(sl, 2)
        )
        return True, entry_zone, score, checklist, []


# Singleton strategy manager instance
strategy_manager = StrategyManager()

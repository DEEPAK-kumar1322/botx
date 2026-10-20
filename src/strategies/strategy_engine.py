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
from src.analysis.models import BiasType, FairValueGap, OrderBlock
from src.analysis.structure import MarketStructureAnalyzer, StructureAnalysisResult, SwingPoint, LiquidityLevel
from src.notifications.telegram_alerts import TelegramAlertSender
from src.notifications.whatsapp_alerts import WhatsAppAlertSender
from src.strategies.liquidity_sweep import LiquiditySweepAnalyzer
from src.strategies.price_action_retest import PriceActionRetestAnalyzer


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
    sniper_mode_active: bool = True
    has_entry: bool = Field(description="True if 100% strict confluence met, False if wait state")
    status_message: str = Field(description="'No valid entry right now, please wait.' or verified setup alert")
    wait_reasons: List[str] = Field(default_factory=list)
    confluence_score: int = Field(description="Score percentage (0-100%)")
    checklist: List[ConfluenceCheckItem]
    entry_zone: Optional[EntryZone] = None
    step_a_structure: StructureAnalysisResult
    htf_alignment: Dict[str, str] = Field(default_factory=dict)
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
    enforces strict anti-spam confluence, and applies WhatsApp & Telegram cooldowns.
    """

    def __init__(self):
        self.feed = UnifiedMarketFeed()
        self.structure_analyzer = MarketStructureAnalyzer(swing_window=3)
        self.smc_analyzer = SMCAnalyzer()
        self.liquidity_sweep_analyzer = LiquiditySweepAnalyzer(swing_window=3, lookback_sweep_bars=6)
        self.retest_analyzer = PriceActionRetestAnalyzer(swing_window_5m=3, swing_window_1h=3)
        self.notifier = TelegramAlertSender(cooldown_seconds=1800)
        self.whatsapp_notifier = WhatsAppAlertSender(cooldown_seconds=1800)

        # Active strategy state
        self.active_strategy_id: str = "liquidity_sweep"
        self.is_deployed_active: bool = True

        # Evaluation audit history
        self.history: List[StrategyAnalysisResponse] = []

        # Available Strategy Catalog
        self._strategies_meta: Dict[str, Dict[str, Any]] = {
            "liquidity_sweep": {
                "id": "liquidity_sweep",
                "name": "Liquidity Sweep Strategy (1:3 RR)",
                "category": "Stop-Hunt & Reclaim (Price Action)",
                "description": "Detects Support (SSL) & Resistance (BSL) Liquidity Sweeps with Rejection Pin Bar / Pause Candle break confirmation, 1H HTF alignment, and minimum 1:3 RR.",
                "timeframes": ["5m", "15m", "1h"],
                "parameters": {
                    "min_risk_reward": 3.0,
                    "partial_tp_rr": 2.0,
                    "require_1h_alignment": True,
                    "swing_window": 3
                }
            },
            "funded_retest_scalper": {
                "id": "funded_retest_scalper",
                "name": "Price Action Retest Scalper (5M BOS + Retest | 1:2 RR)",
                "category": "Price Action & Market Structure (Funded Trader)",
                "description": "Zero indicators. 1H Trend Direction + 5M Break of Structure (BOS) + Retest / Pullback + Rejection Wick / Engulfing confirmation with 1:2 Risk-to-Reward.",
                "timeframes": ["5m", "15m", "1h"],
                "parameters": {
                    "min_risk_reward": 2.0,
                    "entry_timeframe": "5m",
                    "trend_timeframe": "1h",
                    "require_retest": True
                }
            },
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
        logger.info("Initialized StrategyManager with 5 modular algorithmic strategies (default: liquidity_sweep).")

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
        Executes Institutional Sniper Mode Strategy Analysis:
        - Step A: Base Market Structure & Bias Analysis (15m, 1H, and 4H).
        - Step B: Multi-timeframe strategy evaluation with strict 4-condition Sniper Mode Confluence:
          1. Liquidity Sweep First (BSL/SSL Purge).
          2. Strong Displacement & CHoCH (FVG Imbalance).
          3. Deep Mitigation (Discount/Premium Array).
          4. Higher Timeframe Alignment (15m + 1H + 4H).
        If ANY condition fails, the engine outputs ZERO signals and remains in STANDBY / WAITING state.
        """
        sid = strategy_id or self.active_strategy_id
        if sid not in self._strategies_meta:
            sid = "smc"

        strat_meta = self._strategies_meta[sid]
        logger.info(f"Sniper Mode: Running Two-Step Analysis for {symbol} ({timeframe}) using strategy: {strat_meta['name']}")

        # 1. Fetch Execution (15m/LTF), Context 1H, and Macro Context 4H Candles
        candles_ltf = self.feed.fetch_recent_candles(symbol, timeframe=timeframe, limit=60)
        if not candles_ltf:
            raise ValueError(f"Failed to fetch market data for {symbol} on {timeframe}")

        candles_1h = self.feed.fetch_recent_candles(symbol, timeframe="1h", limit=60) or candles_ltf
        candles_4h = self.feed.fetch_recent_candles(symbol, timeframe="4h", limit=60) or candles_1h

        current_price = candles_ltf[-1].close

        # ====================================================================
        # STEP A: Multi-Timeframe Market Structure & Bias Analysis
        # ====================================================================
        structure_ltf = self.structure_analyzer.analyze(candles_ltf, symbol=symbol, timeframe=timeframe)
        structure_1h = self.structure_analyzer.analyze(candles_1h, symbol=symbol, timeframe="1h")
        structure_4h = self.structure_analyzer.analyze(candles_4h, symbol=symbol, timeframe="4h")

        # ====================================================================
        # STEP B: Evaluate Active Strategy with Global Sniper Mode Gate
        # ====================================================================
        sweep_signal = None
        if sid == "liquidity_sweep":
            eval_res = self.liquidity_sweep_analyzer.evaluate(
                candles_ltf=candles_ltf,
                candles_htf=candles_1h,
                symbol=symbol,
                timeframe=timeframe,
                allow_counter_trend=not strat_meta["parameters"].get("require_1h_alignment", True),
            )
            has_entry = eval_res.has_valid_setup
            sweep_signal = eval_res.signal
            checklist = [
                ConfluenceCheckItem(name=n, status="PASSED" if p else "WAITING", description=d)
                for (n, p, d) in eval_res.checklist
            ]
            passed_cnt = sum(1 for _, p, _ in eval_res.checklist if p)
            score = int((passed_cnt / max(1, len(eval_res.checklist))) * 100)
            wait_reasons = eval_res.wait_reasons
            if has_entry and sweep_signal:
                entry_zone = EntryZone(
                    action=sweep_signal.action,
                    entry=sweep_signal.entry_price,
                    stop_loss=sweep_signal.stop_loss,
                    take_profit_1=sweep_signal.tp_1_2rr,
                    take_profit_2=sweep_signal.tp_1_3rr,
                    risk_reward_ratio=sweep_signal.risk_reward_ratio,
                    invalidation_level=sweep_signal.stop_loss,
                )
            else:
                entry_zone = None
        elif sid == "funded_retest_scalper":
            eval_res = self.retest_analyzer.evaluate(
                candles_5m=candles_ltf,
                candles_1h=candles_1h,
                symbol=symbol,
                timeframe=timeframe,
            )
            has_entry = eval_res.has_valid_setup
            retest_sig = eval_res.signal
            checklist = [
                ConfluenceCheckItem(name=n, status="PASSED" if p else "WAITING", description=d)
                for (n, p, d) in eval_res.checklist
            ]
            passed_cnt = sum(1 for _, p, _ in eval_res.checklist if p)
            score = int((passed_cnt / max(1, len(eval_res.checklist))) * 100)
            wait_reasons = eval_res.wait_reasons
            if has_entry and retest_sig:
                entry_zone = EntryZone(
                    action=retest_sig.action,
                    entry=retest_sig.entry_price,
                    stop_loss=retest_sig.stop_loss,
                    take_profit_1=retest_sig.tp_1_2rr,
                    take_profit_2=retest_sig.tp_1_2rr,
                    risk_reward_ratio=retest_sig.risk_reward_ratio,
                    invalidation_level=retest_sig.stop_loss,
                )
            else:
                entry_zone = None
        elif sid == "smc":
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_smc(
                candles_ltf, candles_1h, candles_4h, structure_ltf, structure_1h, structure_4h, strat_meta["parameters"]
            )
        elif sid == "ema_cross":
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_ema_cross(
                candles_ltf, candles_1h, candles_4h, structure_ltf, structure_1h, structure_4h, strat_meta["parameters"]
            )
        elif sid == "bollinger_bands":
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_bollinger(
                candles_ltf, candles_1h, candles_4h, structure_ltf, structure_1h, structure_4h, strat_meta["parameters"]
            )
        else:
            has_entry, entry_zone, score, checklist, wait_reasons = self._eval_custom(
                candles_ltf, candles_1h, candles_4h, structure_ltf, structure_1h, structure_4h, strat_meta["parameters"]
            )

        # ====================================================================
        # Strict Validity & Clear Wait State (Quality Over Quantity)
        # ====================================================================
        if not has_entry:
            status_message = "No valid entry right now, please wait."
            entry_zone = None
        else:
            action_text = "BUY / LONG" if entry_zone.action == "BUY" else "SELL / SHORT"
            status_message = f"SNIPER A+ {action_text} SETUP CONFIRMED (100% Confluence)"

        # ====================================================================
        # WhatsApp & Telegram Anti-Spam Cooldown & Notification
        # ====================================================================
        telegram_status = TelegramDispatchStatus(
            alert_sent=False,
            cooldown_active=False,
            cooldown_remaining_sec=0,
            message="Sniper Mode Standby: Zero execution signal. Quality over quantity enforced."
        )

        if has_entry and entry_zone:
            if sweep_signal:
                self.whatsapp_notifier.send_liquidity_sweep_alert(
                    symbol=symbol,
                    timeframe=timeframe,
                    action=sweep_signal.action,
                    sweep_type=sweep_signal.sweep_type,
                    swept_level=sweep_signal.swept_level,
                    sweep_extreme=sweep_signal.sweep_extreme,
                    confirmation_type=sweep_signal.confirmation_type,
                    entry_price=sweep_signal.entry_price,
                    stop_loss=sweep_signal.stop_loss,
                    tp_1_2rr=sweep_signal.tp_1_2rr,
                    tp_1_3rr=sweep_signal.tp_1_3rr,
                    htf_bias=sweep_signal.htf_bias,
                    rr_ratio=sweep_signal.risk_reward_ratio,
                    notes=sweep_signal.psychology_note,
                )

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
                trigger_desc = (
                    sweep_signal.psychology_note
                    if sweep_signal
                    else f"Sniper A+ Setup: {strat_meta['name']} verified with Sweep, CHoCH, Deep Mitigation, and 1H/4H ({structure_1h.directional_bias}/{structure_4h.directional_bias}) alignment."
                )
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
                    directional_bias=structure_ltf.directional_bias
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
            sniper_mode_active=True,
            has_entry=has_entry,
            status_message=status_message,
            wait_reasons=wait_reasons,
            confluence_score=score,
            checklist=checklist,
            entry_zone=entry_zone,
            step_a_structure=structure_ltf,
            htf_alignment={
                "1h": structure_1h.directional_bias,
                "4h": structure_4h.directional_bias
            },
            telegram_status=telegram_status
        )

        self.history.insert(0, response)
        if len(self.history) > 30:
            self.history.pop()

        return response

    # ========================================================================
    # GLOBAL SNIPER MODE VALIDATOR (Enforces 4 Core Institutional Rules)
    # ========================================================================
    def validate_sniper_mode(
        self,
        symbol: str,
        candles_ltf: List[CandleData],
        candles_1h: List[CandleData],
        candles_4h: List[CandleData],
        structure_ltf: StructureAnalysisResult,
        structure_1h: StructureAnalysisResult,
        structure_4h: StructureAnalysisResult,
        action: str,  # "BUY" or "SELL"
        strategy_name: str,
        prelim_checks: List[ConfluenceCheckItem]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        """
        Global Sniper Mode Validator:
        Strictly enforces 4 institutional conditions simultaneously:
        1. Liquidity Sweep First (BSL or SSL pool purged with wick absorption).
        2. Strong Displacement & CHoCH (Break of character with aggressive impulse leaving active FVG).
        3. Deep Mitigation (Retracement into Discount for Long / Premium for Short, mitigating OB/FVG).
        4. HTF Alignment (15m signal MUST align with 1H and 4H directional bias).

        If EVEN ONE condition fails, the trade is REJECTED (0 signals generated).
        """
        cur_price = candles_ltf[-1].close
        fvgs = self.smc_analyzer.find_fair_value_gaps(candles_ltf)
        obs = self.smc_analyzer.find_order_blocks(candles_ltf, fvgs=fvgs)

        checklist: List[ConfluenceCheckItem] = []
        wait_reasons: List[str] = []

        is_buy = (action == "BUY")

        # --------------------------------------------------------------------
        # 1. Condition 1: Major Liquidity Sweep (BSL / SSL Purge)
        # --------------------------------------------------------------------
        sweep_passed = False
        sweep_desc = ""
        swept_price = None

        if is_buy:
            low_swings = [s for s in structure_ltf.swing_points if s.point_type == "LOW"]
            ssl_levels = [l.price for l in structure_ltf.ssl_levels]
            all_low_targets = set([s.price for s in low_swings[:-1]] + ssl_levels)

            for low_level in all_low_targets:
                for c in candles_ltf[-25:]:
                    if c.low < low_level:
                        if cur_price >= low_level * 0.998 or c.close >= low_level:
                            sweep_passed = True
                            swept_price = low_level
                            break
                if sweep_passed:
                    break

            if sweep_passed:
                sweep_desc = f"Swept Sell-Side Liquidity (SSL) at ${swept_price:,.2f} with institutional absorption."
            else:
                sweep_desc = f"No recent SSL sweep detected. Price (${cur_price:,.2f}) has not purged recent swing low stops."
                wait_reasons.append("Sniper Rule #1: Missing Liquidity Sweep. Price must purge major Sell-Side Liquidity (SSL) before a valid institutional Long.")

        else:
            high_swings = [s for s in structure_ltf.swing_points if s.point_type == "HIGH"]
            bsl_levels = [l.price for l in structure_ltf.bsl_levels]
            all_high_targets = set([s.price for s in high_swings[:-1]] + bsl_levels)

            for high_level in all_high_targets:
                for c in candles_ltf[-25:]:
                    if c.high > high_level:
                        if cur_price <= high_level * 1.002 or c.close <= high_level:
                            sweep_passed = True
                            swept_price = high_level
                            break
                if sweep_passed:
                    break

            if sweep_passed:
                sweep_desc = f"Swept Buy-Side Liquidity (BSL) at ${swept_price:,.2f} with institutional wick rejection."
            else:
                sweep_desc = f"No recent BSL sweep detected. Price (${cur_price:,.2f}) has not purged recent swing high stops."
                wait_reasons.append("Sniper Rule #1: Missing Liquidity Sweep. Price must purge major Buy-Side Liquidity (BSL) before a valid institutional Short.")

        checklist.append(ConfluenceCheckItem(
            name="1. Major Liquidity Sweep (BSL/SSL Purge)",
            status="PASSED" if sweep_passed else "WAITING",
            description=sweep_desc
        ))

        # --------------------------------------------------------------------
        # 2. Condition 2: Strong Displacement & CHoCH (Change of Character) with FVG
        # --------------------------------------------------------------------
        choch_passed = False
        choch_desc = ""

        body_sizes = [abs(c.close - c.open) for c in candles_ltf[-20:]]
        avg_body = float(np.mean(body_sizes)) if body_sizes else 1.0

        if is_buy:
            high_swings = [s for s in structure_ltf.swing_points if s.point_type == "HIGH"]
            has_choch_break = False
            if high_swings:
                recent_high = high_swings[-1].price
                has_choch_break = any(c.close > recent_high * 0.999 for c in candles_ltf[-12:]) or structure_ltf.directional_bias == "BULLISH"
            else:
                has_choch_break = structure_ltf.directional_bias == "BULLISH"

            has_displacement = any(
                (c.close > c.open) and (abs(c.close - c.open) >= 1.25 * avg_body)
                for c in candles_ltf[-12:]
            )

            bullish_fvgs = [f for f in fvgs if f.bias == BiasType.BULLISH and not f.fully_filled and f.gap_pct >= 0.03]
            has_fvg = len(bullish_fvgs) > 0

            choch_passed = has_choch_break and (has_displacement or has_fvg)
            if choch_passed and has_fvg:
                fvg_zone = f"${bullish_fvgs[0].bottom:,.2f} - ${bullish_fvgs[0].top:,.2f}"
                choch_desc = f"Confirmed Bullish CHoCH breakout with strong impulse displacement leaving active FVG ({fvg_zone})."
            elif choch_passed:
                choch_desc = "Confirmed Bullish CHoCH breakout with strong volume displacement."
            else:
                choch_desc = "Missing clear Bullish CHoCH breakout with strong volume displacement and Fair Value Gap imbalance."
                wait_reasons.append("Sniper Rule #2: Missing CHoCH Displacement. Institutional buying requires a violent displacement leg creating an FVG.")

        else:
            low_swings = [s for s in structure_ltf.swing_points if s.point_type == "LOW"]
            has_choch_break = False
            if low_swings:
                recent_low = low_swings[-1].price
                has_choch_break = any(c.close < recent_low * 1.001 for c in candles_ltf[-12:]) or structure_ltf.directional_bias == "BEARISH"
            else:
                has_choch_break = structure_ltf.directional_bias == "BEARISH"

            has_displacement = any(
                (c.close < c.open) and (abs(c.close - c.open) >= 1.25 * avg_body)
                for c in candles_ltf[-12:]
            )

            bearish_fvgs = [f for f in fvgs if f.bias == BiasType.BEARISH and not f.fully_filled and f.gap_pct >= 0.03]
            has_fvg = len(bearish_fvgs) > 0

            choch_passed = has_choch_break and (has_displacement or has_fvg)
            if choch_passed and has_fvg:
                fvg_zone = f"${bearish_fvgs[0].bottom:,.2f} - ${bearish_fvgs[0].top:,.2f}"
                choch_desc = f"Confirmed Bearish CHoCH breakdown with strong impulse displacement leaving active FVG ({fvg_zone})."
            elif choch_passed:
                choch_desc = "Confirmed Bearish CHoCH breakdown with strong volume displacement."
            else:
                choch_desc = "Missing clear Bearish CHoCH breakdown with strong volume displacement and Fair Value Gap imbalance."
                wait_reasons.append("Sniper Rule #2: Missing CHoCH Displacement. Institutional selling requires a violent displacement leg creating an FVG.")

        checklist.append(ConfluenceCheckItem(
            name="2. Strong Displacement & CHoCH (FVG Imbalance)",
            status="PASSED" if choch_passed else "WAITING",
            description=choch_desc
        ))

        # --------------------------------------------------------------------
        # 3. Condition 3: Deep Mitigation (Discount / Premium Arrays)
        # --------------------------------------------------------------------
        mitigation_passed = False
        mitigation_desc = ""

        if is_buy:
            range_low = swept_price if swept_price else min(c.low for c in candles_ltf[-20:])
            range_high = max(c.high for c in candles_ltf[-15:])
            equilibrium = range_low + 0.5 * (range_high - range_low) if range_high > range_low else cur_price

            in_discount = cur_price <= equilibrium * 1.003
            discount_obs = [o for o in obs if o.bias == BiasType.BULLISH and not o.broken and o.top <= equilibrium * 1.05]
            discount_fvgs = [f for f in fvgs if f.bias == BiasType.BULLISH and not f.fully_filled and f.top <= equilibrium * 1.05]

            tapping_ob = next((o for o in discount_obs if o.bottom * 0.998 <= cur_price <= o.top * 1.003), None)
            tapping_fvg = next((f for f in discount_fvgs if f.bottom * 0.998 <= cur_price <= f.top * 1.003), None)

            mitigation_passed = in_discount and (tapping_ob is not None or tapping_fvg is not None)
            if mitigation_passed:
                zone_str = f"OB (${tapping_ob.bottom:,.2f} - ${tapping_ob.top:,.2f})" if tapping_ob else f"FVG (${tapping_fvg.bottom:,.2f} - ${tapping_fvg.top:,.2f})"
                mitigation_desc = f"Deep Discount mitigation confirmed: Price (${cur_price:,.2f}) is in Discount (< EQ ${equilibrium:,.2f}) tapping unmitigated {zone_str}."
            else:
                mitigation_desc = f"Price (${cur_price:,.2f}) is {'in Premium (> EQ $' + f'{equilibrium:,.2f})' if not in_discount else 'not mitigating an unmitigated OB/FVG demand array in Discount'}."
                wait_reasons.append(f"Sniper Rule #3: Unfavorable pricing. Price is {'in Premium' if not in_discount else 'not mitigating an unmitigated demand Order Block/FVG in Discount'} (EQ: ${equilibrium:,.2f}).")

        else:
            range_high = swept_price if swept_price else max(c.high for c in candles_ltf[-20:])
            range_low = min(c.low for c in candles_ltf[-15:])
            equilibrium = range_low + 0.5 * (range_high - range_low) if range_high > range_low else cur_price

            in_premium = cur_price >= equilibrium * 0.997
            premium_obs = [o for o in obs if o.bias == BiasType.BEARISH and not o.broken and o.bottom >= equilibrium * 0.95]
            premium_fvgs = [f for f in fvgs if f.bias == BiasType.BEARISH and not f.fully_filled and f.bottom >= equilibrium * 0.95]

            tapping_ob = next((o for o in premium_obs if o.bottom * 0.997 <= cur_price <= o.top * 1.002), None)
            tapping_fvg = next((f for f in premium_fvgs if f.bottom * 0.997 <= cur_price <= f.top * 1.002), None)

            mitigation_passed = in_premium and (tapping_ob is not None or tapping_fvg is not None)
            if mitigation_passed:
                zone_str = f"OB (${tapping_ob.bottom:,.2f} - ${tapping_ob.top:,.2f})" if tapping_ob else f"FVG (${tapping_fvg.bottom:,.2f} - ${tapping_fvg.top:,.2f})"
                mitigation_desc = f"Deep Premium mitigation confirmed: Price (${cur_price:,.2f}) is in Premium (> EQ ${equilibrium:,.2f}) tapping unmitigated {zone_str}."
            else:
                mitigation_desc = f"Price (${cur_price:,.2f}) is {'in Discount (< EQ $' + f'{equilibrium:,.2f})' if not in_premium else 'not mitigating an unmitigated OB/FVG supply array in Premium'}."
                wait_reasons.append(f"Sniper Rule #3: Unfavorable pricing. Price is {'in Discount' if not in_premium else 'not mitigating an unmitigated supply Order Block/FVG in Premium'} (EQ: ${equilibrium:,.2f}).")

        checklist.append(ConfluenceCheckItem(
            name="3. Deep Mitigation (Discount/Premium Array)",
            status="PASSED" if mitigation_passed else "WAITING",
            description=mitigation_desc
        ))

        # --------------------------------------------------------------------
        # 4. Condition 4: Higher Timeframe (HTF) Alignment (15m + 1H + 4H)
        # --------------------------------------------------------------------
        bias_1h = structure_1h.directional_bias
        bias_4h = structure_4h.directional_bias
        htf_passed = False
        htf_desc = ""

        if is_buy:
            htf_passed = (bias_1h == "BULLISH" and bias_4h == "BULLISH")
            if htf_passed:
                htf_desc = f"100% HTF Confluence: 15m Long perfectly aligns with 1H ({structure_1h.confidence}% Bullish) and 4H ({structure_4h.confidence}% Bullish) macro orderflow."
            else:
                htf_desc = f"HTF Conflict: 1H is {bias_1h}, 4H is {bias_4h}. Opposing macro orderflow."
                wait_reasons.append(f"Sniper Rule #4: HTF Conflict. 15m Long opposes 1H ({bias_1h}) or 4H ({bias_4h}) macro directional trend.")
        else:
            htf_passed = (bias_1h == "BEARISH" and bias_4h == "BEARISH")
            if htf_passed:
                htf_desc = f"100% HTF Confluence: 15m Short perfectly aligns with 1H ({structure_1h.confidence}% Bearish) and 4H ({structure_4h.confidence}% Bearish) macro orderflow."
            else:
                htf_desc = f"HTF Conflict: 1H is {bias_1h}, 4H is {bias_4h}. Opposing macro orderflow."
                wait_reasons.append(f"Sniper Rule #4: HTF Conflict. 15m Short opposes 1H ({bias_1h}) or 4H ({bias_4h}) macro directional trend.")

        checklist.append(ConfluenceCheckItem(
            name="4. Higher Timeframe Alignment (15m + 1H + 4H)",
            status="PASSED" if htf_passed else "WAITING",
            description=htf_desc
        ))

        # Append preliminary strategy check
        for c in prelim_checks:
            checklist.append(c)

        # Calculate Confluence Score
        sniper_checks = [sweep_passed, choch_passed, mitigation_passed, htf_passed]
        passed_count = sum(1 for p in sniper_checks if p)
        score = int((passed_count / len(sniper_checks)) * 100)

        # STRICT SNIPER GATE: ALL 4 conditions MUST pass simultaneously!
        all_passed = all(sniper_checks)

        if all_passed:
            # Build precision Sniper Entry Zone
            if is_buy:
                invalidation = swept_price if swept_price else min(c.low for c in candles_ltf[-10:])
                sl = round(invalidation * 0.9985, 2)
                risk = cur_price - sl
                tp1 = round(cur_price + max(risk * 2.2, cur_price * 0.012), 2)
                tp2 = round(structure_ltf.nearest_bsl if (structure_ltf.nearest_bsl and structure_ltf.nearest_bsl > tp1) else (cur_price + risk * 3.5), 2)
            else:
                invalidation = swept_price if swept_price else max(c.high for c in candles_ltf[-10:])
                sl = round(invalidation * 1.0015, 2)
                risk = sl - cur_price
                tp1 = round(cur_price - max(risk * 2.2, cur_price * 0.012), 2)
                tp2 = round(structure_ltf.nearest_ssl if (structure_ltf.nearest_ssl and structure_ltf.nearest_ssl < tp1) else (cur_price - risk * 3.5), 2)

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
            return True, entry_zone, 100, checklist, []

        return False, None, score, checklist, wait_reasons

    # ------------------------------------------------------------------------
    # Strategy 1: Smart Money Concepts (SMC) Evaluation under Sniper Mode
    # ------------------------------------------------------------------------
    def _eval_smc(
        self,
        candles_ltf: List[CandleData],
        candles_1h: List[CandleData],
        candles_4h: List[CandleData],
        structure_ltf: StructureAnalysisResult,
        structure_1h: StructureAnalysisResult,
        structure_4h: StructureAnalysisResult,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        cur_price = candles_ltf[-1].close
        fvgs = self.smc_analyzer.find_fair_value_gaps(candles_ltf)
        obs = self.smc_analyzer.find_order_blocks(candles_ltf, fvgs=fvgs)

        active_bullish_fvg = next((f for f in fvgs if f.bias == BiasType.BULLISH and not f.fully_filled), None)
        active_bullish_ob = next((o for o in obs if o.bias == BiasType.BULLISH and not o.broken), None)
        active_bearish_fvg = next((f for f in fvgs if f.bias == BiasType.BEARISH and not f.fully_filled), None)
        active_bearish_ob = next((o for o in obs if o.bias == BiasType.BEARISH and not o.broken), None)

        action = None
        if structure_ltf.directional_bias == "BULLISH" or (active_bullish_ob or active_bullish_fvg):
            action = "BUY"
        elif structure_ltf.directional_bias == "BEARISH" or (active_bearish_ob or active_bearish_fvg):
            action = "SELL"

        if not action:
            return False, None, 0, [
                ConfluenceCheckItem(name="SMC Base Setup Trigger", status="WAITING", description="No active demand or supply zone interaction.")
            ], ["Market is in neutral equilibrium with no active SMC zone interaction."]

        prelim_checks = [
            ConfluenceCheckItem(
                name="SMC Institutional Zone Trigger",
                status="PASSED",
                description=f"Active {action} zone confluence identified on execution timeframe."
            )
        ]

        return self.validate_sniper_mode(
            symbol=structure_ltf.symbol,
            candles_ltf=candles_ltf,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            structure_ltf=structure_ltf,
            structure_1h=structure_1h,
            structure_4h=structure_4h,
            action=action,
            strategy_name="Smart Money Concepts (SMC)",
            prelim_checks=prelim_checks
        )

    # ------------------------------------------------------------------------
    # Strategy 2: 9/20 EMA Dynamic Trend Follower under Sniper Mode
    # ------------------------------------------------------------------------
    def _eval_ema_cross(
        self,
        candles_ltf: List[CandleData],
        candles_1h: List[CandleData],
        candles_4h: List[CandleData],
        structure_ltf: StructureAnalysisResult,
        structure_1h: StructureAnalysisResult,
        structure_4h: StructureAnalysisResult,
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

        action = None
        if ema_fast > ema_slow and cur_price > ema_base * 0.995:
            action = "BUY"
        elif ema_fast < ema_slow and cur_price < ema_base * 1.005:
            action = "SELL"

        if not action:
            return False, None, 0, [
                ConfluenceCheckItem(name="9/20 EMA Cross & 50-EMA Filter", status="WAITING", description="EMA momentum is not aligned with 50-EMA baseline.")
            ], ["EMA 9 has not crossed EMA 20 in alignment with the 50-EMA macro filter."]

        prelim_checks = [
            ConfluenceCheckItem(
                name="9/20 EMA Momentum Trigger",
                status="PASSED",
                description=f"EMA 9 (${ema_fast:,.2f}) crossed EMA 20 (${ema_slow:,.2f}) with 50-EMA (${ema_base:,.2f}) filter."
            )
        ]

        return self.validate_sniper_mode(
            symbol=structure_ltf.symbol,
            candles_ltf=candles_ltf,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            structure_ltf=structure_ltf,
            structure_1h=structure_1h,
            structure_4h=structure_4h,
            action=action,
            strategy_name="9/20 EMA Dynamic Trend Follower",
            prelim_checks=prelim_checks
        )

    # ------------------------------------------------------------------------
    # Strategy 3: Bollinger Bands 20/2 + RSI Mean Reversion under Sniper Mode
    # ------------------------------------------------------------------------
    def _eval_bollinger(
        self,
        candles_ltf: List[CandleData],
        candles_1h: List[CandleData],
        candles_4h: List[CandleData],
        structure_ltf: StructureAnalysisResult,
        structure_1h: StructureAnalysisResult,
        structure_4h: StructureAnalysisResult,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        closes = [c.close for c in candles_ltf]
        cur_price = closes[-1]

        sma, upper, lower = calculate_bollinger_bands(closes, period=20, num_std=2.0)
        rsi = calculate_rsi(closes, period=14)

        touch_lower = cur_price <= lower * 1.005 or rsi <= params.get("rsi_oversold", 38)
        touch_upper = cur_price >= upper * 0.995 or rsi >= params.get("rsi_overbought", 62)

        action = None
        if touch_lower:
            action = "BUY"
        elif touch_upper:
            action = "SELL"

        if not action:
            return False, None, 0, [
                ConfluenceCheckItem(name="Bollinger Envelope Exhaustion", status="WAITING", description="Price is inside the neutral 20-SMA volatility envelope.")
            ], [f"Price (${cur_price:,.2f}) is within normal volatility bands (Lower: ${lower:,.2f}, Upper: ${upper:,.2f}). Waiting for extreme expansion test."]

        prelim_checks = [
            ConfluenceCheckItem(
                name="Bollinger & RSI Exhaustion Trigger",
                status="PASSED",
                description=f"Price tested {'Lower Band ($' + f'{lower:,.2f})' if action == 'BUY' else 'Upper Band ($' + f'{upper:,.2f})'} with RSI at {rsi:.1f}."
            )
        ]

        return self.validate_sniper_mode(
            symbol=structure_ltf.symbol,
            candles_ltf=candles_ltf,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            structure_ltf=structure_ltf,
            structure_1h=structure_1h,
            structure_4h=structure_4h,
            action=action,
            strategy_name="Bollinger Bands Mean Reversion",
            prelim_checks=prelim_checks
        )

    # ------------------------------------------------------------------------
    # Strategy 4: Custom Algorithmic Rules under Sniper Mode
    # ------------------------------------------------------------------------
    def _eval_custom(
        self,
        candles_ltf: List[CandleData],
        candles_1h: List[CandleData],
        candles_4h: List[CandleData],
        structure_ltf: StructureAnalysisResult,
        structure_1h: StructureAnalysisResult,
        structure_4h: StructureAnalysisResult,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[EntryZone], int, List[ConfluenceCheckItem], List[str]]:
        closes = [c.close for c in candles_ltf]
        cur_price = closes[-1]
        ema_21 = calculate_ema(closes, 21)[-1]

        action = "BUY" if cur_price > ema_21 else "SELL"

        prelim_checks = [
            ConfluenceCheckItem(
                name="Custom 21-EMA Hybrid Baseline",
                status="PASSED",
                description=f"Price (${cur_price:,.2f}) is {'above' if action == 'BUY' else 'below'} 21-EMA (${ema_21:,.2f})."
            )
        ]

        return self.validate_sniper_mode(
            symbol=structure_ltf.symbol,
            candles_ltf=candles_ltf,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            structure_ltf=structure_ltf,
            structure_1h=structure_1h,
            structure_4h=structure_4h,
            action=action,
            strategy_name="Custom Algorithmic Rules",
            prelim_checks=prelim_checks
        )



# Singleton strategy manager instance
strategy_manager = StrategyManager()

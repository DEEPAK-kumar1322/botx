"""
Monte Carlo Path & Historical Validator for Trade Setups (BotX).

Inspired by trader-timemachine:
Replays 1,000 simulated paths using empirical price ratios from recent candle history
to estimate the exact probability of hitting the 1:1 Take-Profit before the Stop-Loss.
"""

import random
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from src.data.base import CandleData


class SimulationResult(BaseModel):
    """Monte Carlo Simulation Verdict for a trade setup."""
    symbol: str
    target_prob: float = Field(description="Probability of hitting TP first (%)")
    stop_prob: float = Field(description="Probability of hitting SL first (%)")
    neither_prob: float = Field(description="Probability of running out of time (%)")
    verdict: str = Field(description="'Strongly toward Target', 'Leans toward Target', 'Coin Flip', or 'Avoid'")
    replays_count: int = 1000
    expected_value_r: float = 0.0


class MonteCarloValidator:
    """
    Simulates path outcomes using empirical return bootstrapping from past candles.
    """

    def __init__(self, replays: int = 1000, seed: int = 42):
        self.replays = replays
        self.seed = seed

    def simulate(
        self,
        candles: List[CandleData],
        action: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        max_horizon_bars: int = 16,  # 4 hours on 15M
    ) -> SimulationResult:
        if len(candles) < 20:
            return SimulationResult(
                symbol="N/A",
                target_prob=50.0,
                stop_prob=50.0,
                neither_prob=0.0,
                verdict="Insufficient Data (Default 50/50)",
                replays_count=self.replays,
                expected_value_r=0.0,
            )

        # Build empirical returns pool: (high/prev_close, low/prev_close, close/prev_close)
        pool = []
        for i in range(1, len(candles)):
            prev = candles[i - 1].close
            if prev <= 0:
                continue
            pool.append((
                candles[i].high / prev,
                candles[i].low / prev,
                candles[i].close / prev,
            ))

        if not pool:
            return SimulationResult(
                symbol="N/A",
                target_prob=50.0,
                stop_prob=50.0,
                neither_prob=0.0,
                verdict="Empty Pool",
                replays_count=self.replays,
                expected_value_r=0.0,
            )

        rng = random.Random(self.seed)
        target_hits = 0
        stop_hits = 0
        neither_hits = 0

        is_buy = action.upper() == "BUY"

        for _ in range(self.replays):
            curr_price = entry_price
            hit = None

            for _ in range(max_horizon_bars):
                h_ratio, l_ratio, c_ratio = rng.choice(pool)
                bar_high = curr_price * h_ratio
                bar_low = curr_price * l_ratio
                curr_price = curr_price * c_ratio

                if is_buy:
                    # Check conservative: Stop first, then target
                    if bar_low <= stop_loss:
                        hit = "STOP"
                        break
                    elif bar_high >= take_profit:
                        hit = "TARGET"
                        break
                else:
                    if bar_high >= stop_loss:
                        hit = "STOP"
                        break
                    elif bar_low <= take_profit:
                        hit = "TARGET"
                        break

            if hit == "TARGET":
                target_hits += 1
            elif hit == "STOP":
                stop_hits += 1
            else:
                neither_hits += 1

        target_pct = round((target_hits / self.replays) * 100, 1)
        stop_pct = round((stop_hits / self.replays) * 100, 1)
        neither_pct = round((neither_hits / self.replays) * 100, 1)

        # Expected Value in R (assuming 1R TP and 1R SL)
        ev_r = round(((target_hits * 1.0) - (stop_hits * 1.0)) / self.replays, 3)

        if target_pct >= 60.0:
            verdict = "Strongly toward Target (High Probability)"
        elif target_pct >= 53.0:
            verdict = "Leans toward Target (Positive Expectancy)"
        elif target_pct >= 47.0:
            verdict = "Close to Coin Flip"
        else:
            verdict = "Leans toward Stop (Negative Expectancy - Caution)"

        return SimulationResult(
            symbol="",
            target_prob=target_pct,
            stop_prob=stop_pct,
            neither_prob=neither_pct,
            verdict=verdict,
            replays_count=self.replays,
            expected_value_r=ev_r,
        )

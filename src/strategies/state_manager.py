"""
BotX Active Strategy State Manager.
Maintains shared state across API server, WhatsApp bridge, and Auto-Trader daemon.
Default strategy is always 'liquidity_sweep'.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "active_strategy.json"

DEFAULT_STRATEGY = "liquidity_sweep"

VALID_STRATEGIES = {
    "liquidity_sweep": "Liquidity Sweep Strategy (1:3 RR)",
    "funded_retest_scalper": "Price Action Retest Scalper (5M BOS + Retest | 1:2 RR)",
    "smc": "Smart Money Concepts (SMC)",
}

def get_active_strategy() -> str:
    """Read currently active strategy ID from disk (default: liquidity_sweep)."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                strat = data.get("active_strategy", DEFAULT_STRATEGY)
                if strat in VALID_STRATEGIES:
                    return strat
    except Exception:
        pass
    return DEFAULT_STRATEGY

def set_active_strategy(strategy_id: str) -> dict:
    """Update active strategy on disk."""
    strat = strategy_id.lower().strip()
    if strat not in VALID_STRATEGIES:
        raise ValueError(f"Invalid strategy '{strategy_id}'. Valid options: {list(VALID_STRATEGIES.keys())}")
    
    payload = {
        "active_strategy": strat,
        "name": VALID_STRATEGIES[strat],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload

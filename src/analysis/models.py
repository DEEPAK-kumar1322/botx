"""
Data models for Smart Money Concepts (SMC): Fair Value Gaps and Order Blocks.
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class BiasType(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class SetupType(str, Enum):
    FAIR_VALUE_GAP = "FAIR_VALUE_GAP"
    ORDER_BLOCK = "ORDER_BLOCK"


class FairValueGap(BaseModel):
    """Fair Value Gap (FVG) / Imbalance zone."""
    bias: BiasType
    top: float = Field(description="Upper boundary of the gap zone")
    bottom: float = Field(description="Lower boundary of the gap zone")
    gap_size: float = Field(description="Absolute gap size in quote currency")
    gap_pct: float = Field(description="Gap size as a percentage of price")
    timestamp: datetime = Field(description="Timestamp of the displacement candle")
    candle_index: int = Field(description="Index of the displacement candle in series")
    mitigated: bool = Field(default=False, description="True if price has revisited the gap")
    fully_filled: bool = Field(default=False, description="True if gap has been entirely traversed")


class OrderBlock(BaseModel):
    """Institutional Order Block (OB) demand/supply zone."""
    bias: BiasType
    top: float = Field(description="High or upper body of the order block candle")
    bottom: float = Field(description="Low or lower body of the order block candle")
    timestamp: datetime = Field(description="Timestamp of the order block candle")
    candle_index: int = Field(description="Index of the order block candle")
    volume: float = Field(description="Volume recorded during order block candle")
    displacement_pct: float = Field(description="Percentage price moved during the subsequent impulse")
    has_confluence_fvg: bool = Field(default=False, description="True if displacement created an FVG")
    mitigated: bool = Field(default=False, description="True if subsequent price tested this zone")
    broken: bool = Field(default=False, description="True if price closed through the zone (invalidated)")


class TechnicalSetup(BaseModel):
    """Consolidated actionable trading setup."""
    symbol: str
    timeframe: str
    setup_type: SetupType
    bias: BiasType
    zone_high: float
    zone_low: float
    current_price: float
    timestamp: datetime
    status: str = Field(description="'ACTIVE_UNTESTED', 'TESTING_ZONE', or 'MITIGATED'")
    details: str

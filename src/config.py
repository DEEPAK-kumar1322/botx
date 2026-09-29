"""
Configuration management for the Botx AI Trading Engine.
"""

from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

load_dotenv()


class EngineConfig(BaseModel):
    """Trading engine environment and execution configuration."""
    trading_mode: str = Field(default_factory=lambda: os.getenv("TRADING_MODE", "paper"))
    exchange_id: str = Field(default_factory=lambda: os.getenv("EXCHANGE_ID", "binance"))
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("EXCHANGE_API_KEY", ""))
    api_secret: Optional[str] = Field(default_factory=lambda: os.getenv("EXCHANGE_API_SECRET", ""))
    default_symbol: str = Field(default_factory=lambda: os.getenv("DEFAULT_SYMBOL", "BTC/USDT"))
    default_timeframe: str = Field(default_factory=lambda: os.getenv("DEFAULT_TIMEFRAME", "1m"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Telegram Notification Settings
    telegram_bot_token: Optional[str] = Field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: Optional[str] = Field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    telegram_enabled: bool = Field(default_factory=lambda: os.getenv("TELEGRAM_ENABLED", "true").lower() in ("true", "1", "yes"))


config = EngineConfig()

"""
FastAPI Backend Server for BotX Trading Terminal.

Provides:
- On-Demand Chart Structure & Liquidity Analysis (/api/analyze)
- Strategy Deployment & Toggle Management (/api/strategy/toggle)
- Live Entry / Exit Execution Signals Feed (/api/strategy/signals, /api/strategy/evaluate)
- Static Dashboard Hosting
"""

import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

from src.data.unified_feed import UnifiedMarketFeed
from src.analysis.structure import MarketStructureAnalyzer, StructureAnalysisResult
from src.strategies.smc_strategy import strategy_engine, ExecutionSignal
from src.strategies.strategy_engine import (
    strategy_manager,
    StrategyInfo,
    StrategyAnalysisResponse
)

# Project Root Directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

app = FastAPI(
    title="BotX AI Trading Terminal API",
    version="1.1.0",
    description="Algorithmic Trading Terminal API with Modular Strategy Hub, On-Demand Structure Analysis, and Anti-Spam Telegram Alerts."
)

# Enable CORS for local cross-origin development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

feed = UnifiedMarketFeed()
structure_analyzer = MarketStructureAnalyzer(swing_window=3)


class StrategyToggleRequest(BaseModel):
    enable: Optional[bool] = None


class StrategyStatusResponse(BaseModel):
    active: bool
    status: str
    signal_count: int
    signals: List[ExecutionSignal]


class StrategyActivateRequest(BaseModel):
    strategy_id: str
    enable: Optional[bool] = None


@app.get("/api/health")
def get_health():
    """Health status, strategy hub state, and supported pairs."""
    return {
        "status": "online",
        "service": "BotX Algorithmic Trading Terminal API",
        "active_strategy_id": strategy_manager.active_strategy_id,
        "strategy_active": strategy_manager.is_deployed_active,
        "available_strategies": [s.id for s in strategy_manager.list_strategies()],
        "supported_pairs": ["BTC/USDT", "ETH/USDT", "XAUUSD", "US100", "XAUJPY", "XAGUSD"]
    }


# ============================================================================
# Strategy Hub Endpoints
# ============================================================================

@app.get("/api/strategies", response_model=List[StrategyInfo])
def get_strategies():
    """Retrieve all available custom trading strategies."""
    return strategy_manager.list_strategies()


@app.post("/api/strategies/activate", response_model=StrategyInfo)
def activate_strategy(req: StrategyActivateRequest):
    """Select active strategy and set deployment state."""
    logger.info(f"API: Activating strategy {req.strategy_id} (enable={req.enable})")
    info = strategy_manager.set_active_strategy(req.strategy_id, enable=req.enable)
    return info


@app.post("/api/strategies/analyze", response_model=StrategyAnalysisResponse)
def run_strategy_analysis_endpoint(
    symbol: str = Query("BTC/USDT", description="Asset symbol (e.g. BTC/USDT, XAUUSD, US100)"),
    timeframe: str = Query("15m", description="Primary execution timeframe"),
    strategy_id: Optional[str] = Query(None, description="Optional strategy override")
):
    """
    Run Strategy Analysis:
    - Step A: Base Market Structure & Bias analysis.
    - Step B: Multi-timeframe strategy evaluation with strict confluence.
    Returns:
    - High-probability entry zones (Entry, SL, TP1, TP2) if 100% confluence met.
    - Clear wait state ('No valid entry right now, please wait.') if criteria < 100%.
    - Anti-spam cooldown Telegram alert dispatch.
    """
    logger.info(f"API: Triggering Strategy Analysis for {symbol} ({timeframe}) with strategy '{strategy_id or strategy_manager.active_strategy_id}'")
    try:
        result = strategy_manager.run_strategy_analysis(
            symbol=symbol,
            timeframe=timeframe,
            strategy_id=strategy_id
        )
        return result
    except Exception as e:
        logger.error(f"Strategy analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Strategy analysis failed: {str(e)}"
        )


@app.get("/api/strategies/history", response_model=List[StrategyAnalysisResponse])
def get_strategy_history():
    """Retrieve audit history of recent strategy evaluations."""
    return strategy_manager.history[:20]



@app.get("/api/analyze", response_model=StructureAnalysisResult)
def analyze_chart_structure(
    symbol: str = Query("BTC/USDT", description="Asset symbol (e.g. BTC/USDT, XAUUSD, US100)"),
    timeframe: str = Query("15m", description="Candle timeframe (e.g. 1m, 15m, 1h)")
):
    """
    On-Demand Market Structure & Liquidity Analysis.
    Returns:
    - Market Structure: Higher Highs (HH), Higher Lows (HL), Lower Highs (LH), Lower Lows (LL)
    - Directional Bias: Bullish, Bearish, or Ranging with confidence & rationale
    - Liquidity Levels: Exact Buy Side Liquidity (BSL) and Sell Side Liquidity (SSL) price levels
    """
    logger.info(f"API: Running On-Demand Structure Analysis for {symbol} ({timeframe})")
    try:
        candles = feed.fetch_recent_candles(symbol, timeframe=timeframe, limit=60)
        if not candles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No candlestick data returned for {symbol} on {timeframe}."
            )

        analysis = structure_analyzer.analyze(candles, symbol=symbol, timeframe=timeframe)
        return analysis

    except Exception as e:
        logger.error(f"Error analyzing structure for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@app.post("/api/strategy/toggle", response_model=StrategyStatusResponse)
def toggle_strategy(req: Optional[StrategyToggleRequest] = None):
    """
    Toggle or explicitly set SMC live strategy activation state.
    When activated, live market data is actively evaluated for execution signals.
    """
    enable = req.enable if req else None
    active = strategy_engine.toggle(enable=enable)
    status_str = "RUNNING" if active else "STANDBY"

    return StrategyStatusResponse(
        active=active,
        status=status_str,
        signal_count=len(strategy_engine.signals),
        signals=strategy_engine.signals[:10]
    )


@app.get("/api/strategy/signals", response_model=StrategyStatusResponse)
def get_strategy_signals():
    """Retrieve current strategy state and generated Entry/Exit signals."""
    return StrategyStatusResponse(
        active=strategy_engine.is_active,
        status="RUNNING" if strategy_engine.is_active else "STANDBY",
        signal_count=len(strategy_engine.signals),
        signals=strategy_engine.signals[:20]
    )


@app.post("/api/strategy/evaluate")
def evaluate_strategy_signal(
    symbol: str = Query("BTC/USDT", description="Symbol to evaluate for entry/exit"),
    timeframe: str = Query("15m", description="Timeframe interval")
):
    """
    Evaluate SMC logic on live data with Global Sniper Mode validation.
    """
    logger.info(f"API: Evaluating live SMC strategy with Sniper Mode for {symbol} ({timeframe})")
    signal = strategy_engine.evaluate(symbol=symbol, timeframe=timeframe)
    if not signal:
        return {
            "status": "no_setup",
            "message": "No valid entry right now, please wait.",
            "sniper_mode_active": True,
            "quality_over_quantity": True
        }

    return {"status": "signal_generated", "signal": signal}


# Serve Frontend Web Dashboard from Root
@app.get("/")
def serve_index():
    return FileResponse(PROJECT_ROOT / "index.html")

@app.get("/index.html")
def serve_index_html():
    return FileResponse(PROJECT_ROOT / "index.html")

@app.get("/style.css")
def serve_style_css():
    return FileResponse(PROJECT_ROOT / "style.css", media_type="text/css")

@app.get("/script.js")
def serve_script_js():
    return FileResponse(PROJECT_ROOT / "script.js", media_type="application/javascript")

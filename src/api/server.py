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

# Project Root Directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

app = FastAPI(
    title="BotX AI Trading Terminal API",
    version="1.0.0",
    description="Lightweight local API connecting BotX terminal frontend with live SMC analysis and strategy execution."
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


@app.get("/api/health")
def get_health():
    """Health status and strategy state."""
    return {
        "status": "online",
        "service": "BotX Trading Terminal API",
        "strategy_active": strategy_engine.is_active,
        "supported_pairs": ["BTC/USDT", "ETH/USDT", "XAUUSD", "US100", "XAUJPY", "XAGUSD"]
    }


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
    Evaluate SMC logic on live data and return an exact Entry/Exit execution signal.
    """
    logger.info(f"API: Evaluating live SMC strategy for {symbol} ({timeframe})")
    signal = strategy_engine.evaluate(symbol=symbol, timeframe=timeframe)
    if not signal:
        return {"status": "no_setup", "message": f"No high-probability SMC entry trigger for {symbol} on {timeframe} currently."}

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

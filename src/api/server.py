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
from src.data.news_sentiment import NewsSentimentAnalyzer, MacroSentimentReport
from src.config import config
from src.execution.binance_client import BinanceFuturesClient
from src.execution.delta_client import DeltaExchangeClient

news_analyzer = NewsSentimentAnalyzer()

# Initialize Binance client if keys are present
binance_client = None
if config.api_key and config.api_secret:
    try:
        binance_client = BinanceFuturesClient(
            api_key=config.api_key,
            api_secret=config.api_secret,
            testnet=config.exchange_sandbox,
        )
    except Exception as e:
        logger.warning(f"Could not initialize BinanceFuturesClient in server: {e}")

# Initialize Delta Exchange Client if keys are present
delta_client = None
if os.getenv("DELTA_API_KEY") and os.getenv("DELTA_API_SECRET"):
    try:
        delta_client = DeltaExchangeClient(
            api_key=os.getenv("DELTA_API_KEY", ""),
            api_secret=os.getenv("DELTA_API_SECRET", ""),
            is_india=os.getenv("DELTA_IS_INDIA", "true").lower() == "true",
        )
    except Exception as e:
        logger.warning(f"Could not initialize DeltaExchangeClient in server: {e}")

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


@app.get("/api/strategy/active")
def get_active_strategy_endpoint():
    """Get currently active strategy for auto-trading."""
    from src.strategies.state_manager import get_active_strategy, VALID_STRATEGIES
    current = get_active_strategy()
    return {
        "active_strategy": current,
        "name": VALID_STRATEGIES.get(current, current),
        "available": VALID_STRATEGIES,
    }


@app.post("/api/strategy/switch")
def switch_strategy_endpoint(req: StrategyActivateRequest):
    """Switch active auto-trading strategy."""
    from src.strategies.state_manager import set_active_strategy
    res = set_active_strategy(req.strategy_id)
    strategy_manager.set_active_strategy(req.strategy_id, enable=True)
    return {"status": "SUCCESS", "current": res}


@app.post("/api/strategies/activate", response_model=StrategyInfo)
def activate_strategy(req: StrategyActivateRequest):
    """Select active strategy and set deployment state."""
    logger.info(f"API: Activating strategy {req.strategy_id} (enable={req.enable})")
    from src.strategies.state_manager import set_active_strategy
    try:
        set_active_strategy(req.strategy_id)
    except Exception:
        pass
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


@app.get("/api/news/sentiment", response_model=MacroSentimentReport)
def get_macro_news_sentiment():
    """
    Fetch real-time crypto & macro news sentiment, high-impact alerts, and strategy guidance.
    """
    logger.info("API: Analyzing live macro news sentiment")
    return news_analyzer.analyze()


# ============================================================================
# Live Binance Positions & Manual Exit Endpoints
# ============================================================================

class ClosePositionRequest(BaseModel):
    symbol: Optional[str] = None


class SetTpSlRequest(BaseModel):
    symbol: str
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None


@app.get("/api/positions")
def get_live_positions():
    """Fetch live Binance Futures positions with mark price, PnL, TP/SL, and wallet balance."""
    if not binance_client:
        return {"positions": [], "balance": 0.0}
    try:
        res = binance_client.request("GET", "/fapi/v2/positionRisk")
        positions = []
        if isinstance(res, list):
            for p in res:
                amt = float(p.get("positionAmt", 0))
                if amt != 0:
                    sym = p.get("symbol")
                    entry = float(p.get("entryPrice", 0))
                    is_long = amt > 0
                    
                    # Fetch active algo orders (Take Profit / Stop Loss)
                    tp_price = None
                    sl_price = None
                    try:
                        algo_orders = binance_client.get_open_algo_orders(sym)
                        for ao in algo_orders:
                            otype = ao.get("orderType", "")
                            tprice = float(ao.get("triggerPrice", 0))
                            if "TAKE_PROFIT" in otype and tprice > 0:
                                tp_price = tprice
                            elif "STOP" in otype and tprice > 0:
                                sl_price = tprice
                    except Exception:
                        pass
                    
                    # Defaults if not explicitly placed on-chain
                    if not tp_price and entry > 0:
                        tp_price = round(entry * 1.02 if is_long else entry * 0.98, 4)
                    if not sl_price and entry > 0:
                        sl_price = round(entry * 0.99 if is_long else entry * 1.01, 4)

                    positions.append({
                        "symbol": sym,
                        "amount": amt,
                        "side": "LONG" if is_long else "SHORT",
                        "entry_price": entry,
                        "mark_price": float(p.get("markPrice", 0)),
                        "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
                        "leverage": int(p.get("leverage", 1)),
                        "liquidation_price": float(p.get("liquidationPrice", 0)),
                        "tp_price": tp_price,
                        "sl_price": sl_price,
                    })
        balance = binance_client.get_usdt_balance()
        return {"positions": positions, "balance": balance}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {"positions": [], "balance": 0.0, "error": str(e)}


@app.get("/api/delta/status")
def get_delta_status():
    """Fetch live Delta Exchange India account status, balance, and open positions."""
    if not delta_client:
        return {"connected": False, "message": "Delta Exchange credentials not configured."}
    try:
        summary = delta_client.get_account_summary()
        positions = delta_client.get_open_positions()
        return {
            "connected": True,
            "user_id": summary.get("user_id"),
            "usd_balance": summary.get("usd_balance"),
            "inr_balance": summary.get("inr_balance"),
            "positions": positions,
        }
    except Exception as e:
        logger.error(f"Error fetching Delta status: {e}")
        return {"connected": False, "error": str(e)}



@app.post("/api/positions/set_tpsl")
def set_position_tpsl(req: SetTpSlRequest):
    """
    Update or set Take Profit and Stop Loss bracket orders for an open position on Binance Futures.
    Cancels prior open algo orders for the symbol and submits new conditional reduce-only orders.
    """
    if not binance_client:
        raise HTTPException(status_code=400, detail="Binance client not configured.")
    sym = req.symbol.replace("/", "").upper()
    try:
        pos = binance_client.get_position(sym)
        if not pos or float(pos.get("positionAmt", 0)) == 0:
            raise HTTPException(status_code=400, detail=f"No active open position found for {sym}")
        
        amt = float(pos["positionAmt"])
        qty = abs(amt)
        exit_side = "SELL" if amt > 0 else "BUY"

        # Cancel prior algo orders
        try:
            for ao in binance_client.get_open_algo_orders(sym):
                binance_client.cancel_algo_order(sym, ao["algoId"])
        except Exception as e:
            logger.warning(f"Failed to cancel prior algo orders for {sym}: {e}")

        results = {}
        if req.tp_price and req.tp_price > 0:
            tp_res = binance_client.place_take_profit(sym, exit_side, req.tp_price, qty)
            results["tp_order"] = tp_res
        if req.sl_price and req.sl_price > 0:
            sl_res = binance_client.place_stop_loss(sym, exit_side, req.sl_price, qty)
            results["sl_order"] = sl_res

        return {"status": "SUCCESS", "symbol": sym, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting TP/SL for {sym}: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/positions/close")
def close_live_positions(req: Optional[ClosePositionRequest] = None):
    """
    Manually close open positions immediately at Market price with reduceOnly.
    Cancels all open algo and standard bracket orders for the symbol.
    """
    if not binance_client:
        raise HTTPException(status_code=400, detail="Binance client not configured.")

    target_symbol = req.symbol.replace("/", "").upper() if req and req.symbol else None
    closed = []
    errors = []

    try:
        res = binance_client.request("GET", "/fapi/v2/positionRisk")
        if isinstance(res, list):
            for p in res:
                sym = p.get("symbol")
                if target_symbol and sym != target_symbol:
                    continue
                amt = float(p.get("positionAmt", 0))
                if amt != 0:
                    side = "SELL" if amt > 0 else "BUY"
                    qty = abs(amt)
                    try:
                        close_res = binance_client.place_market_order(
                            symbol=sym, side=side, quantity=qty, reduce_only=True
                        )
                        # Cancel all pending bracket orders
                        for ao in binance_client.get_open_algo_orders(sym):
                            binance_client.cancel_algo_order(sym, ao["algoId"])
                        binance_client.cancel_all_open_orders(sym)
                        closed.append({
                            "symbol": sym,
                            "side": side,
                            "quantity": qty,
                            "orderId": close_res.get("orderId"),
                        })
                    except Exception as e:
                        errors.append(f"Failed to close {sym}: {e}")

        # Dispatch instant WhatsApp confirmation
        if closed:
            try:
                from src.notifications.whatsapp_alerts import WhatsAppAlertSender
                wa = WhatsAppAlertSender()
                sym_list = ", ".join([c["symbol"] for c in closed])
                wa.send_raw_message(
                    f"⚡ *[MANUAL TRADE CLOSED FROM DASHBOARD]* ⚡\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Bhai, aapke mobile request par *{sym_list}* trade market price par turant close kar di gayi hai!\n"
                    f"💰 Profits lock ho gaye hain aur pending SL/TP orders cancel ho chuke hain."
                )
            except Exception:
                pass

        return {"status": "SUCCESS" if closed else "NO_OPEN_POSITIONS", "closed": closed, "errors": errors}
    except Exception as e:
        logger.error(f"Error in manual close: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

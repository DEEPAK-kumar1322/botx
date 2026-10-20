import pandas as pd
import numpy as np
from src.data.unified_feed import UnifiedMarketFeed
from src.strategies.liquidity_sweep import LiquiditySweepAnalyzer

feed = UnifiedMarketFeed()
analyzer = LiquiditySweepAnalyzer(swing_window=5, lookback_sweep_bars=3)

pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ZEC/USDT', 'XRP/USDT', 'AVAX/USDT']
print("=== COMPREHENSIVE SCAN FOR BEST TRADE SETUP (2026-10-16 MORNING) ===")

setups = []

for sym in pairs:
    try:
        c_15m = feed.fetch_recent_candles(sym, timeframe='15m', limit=60)
        c_1h = feed.fetch_recent_candles(sym, timeframe='1h', limit=60)

        closes = [c.close for c in c_15m]
        diffs = np.diff(closes)
        gains = np.maximum(diffs, 0)
        losses = np.maximum(-diffs, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))

        eval_res = analyzer.evaluate(c_15m, c_1h, symbol=sym, timeframe='15m')

        curr = eval_res.current_price
        sup = eval_res.nearest_support or 0
        res = eval_res.nearest_resistance or 0
        dist_sup = (curr - sup) / curr * 100 if sup else 999
        dist_res = (res - curr) / curr * 100 if res else 999

        last_c = c_15m[-2]
        c_rng = max(last_c.high - last_c.low, 1e-6)
        upper_wick = (last_c.high - max(last_c.open, last_c.close)) / c_rng * 100
        lower_wick = (min(last_c.open, last_c.close) - last_c.low) / c_rng * 100

        setups.append({
            'symbol': sym,
            'price': curr,
            '1h_bias': eval_res.htf_bias,
            '1h_conf': eval_res.htf_confidence,
            'rsi': round(rsi, 1),
            'sup': sup,
            'res': res,
            'dist_sup_pct': round(dist_sup, 2),
            'dist_res_pct': round(dist_res, 2),
            'lower_wick': round(lower_wick, 1),
            'upper_wick': round(upper_wick, 1),
            'has_signal': eval_res.has_valid_setup,
            'signal': eval_res.signal,
            'wait_reason': eval_res.wait_reasons[0] if eval_res.wait_reasons else 'None'
        })
    except Exception as e:
        print(f"Error on {sym}: {e}")

for s in setups:
    print(f"{s['symbol']:<10} | Price: ${s['price']:<9} | 1H: {s['1h_bias']:<7} ({s['1h_conf']}%) | RSI: {s['rsi']:<4} | Dist Sup: {s['dist_sup_pct']}% | Dist Res: {s['dist_res_pct']}% | Valid: {s['has_signal']}")
    if s['signal']:
        print(f"   >>> SIGNAL: {s['signal'].action} @ ${s['signal'].entry_price} | SL: ${s['signal'].stop_loss} | TP: ${s['signal'].tp_1_3rr}")
    else:
        print(f"   Reason: {s['wait_reason']}")

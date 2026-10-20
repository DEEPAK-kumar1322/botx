"""
Execute High-Conviction Overnight Swing Trade on Binance Futures.

Target: $200+ Profit by tomorrow 17:00 IST
Asset: ETH/USDT SHORT
Thesis:
- 1D, 4H, 1H Multi-Timeframe Bearish Market Structure
- Rejection at 1H EMA20/50 resistance ($2416.82)
- Target: $2345 (Oct 18 liquidity sweep pool)
- Stop Loss: $2419.50 (above 1H pivot)
- Trailing CTC: Auto-moves to breakeven when price reaches $2373.50
"""

import math
from loguru import logger
from src.execution.binance_client import BinanceFuturesClient
from src.execution.order_manager import OrderManager
from src.execution.position_monitor import PositionMonitor
from src.notifications.whatsapp_alerts import WhatsAppAlertSender

def execute_swing():
    client = BinanceFuturesClient(
        'lfZVP4IAsiT7f4CKEmG5BwxX87N5d6HpttQZcp2c2T86upFhhAg1L0w5c0b3MHnc',
        '9N610nQD0LLAfuja6MJ3OORn1sf75jhqEIfZNhnkadCRGh2RQA3XtyJlCbCc5SBC',
        testnet=True
    )
    whatsapp = WhatsAppAlertSender()
    monitor = PositionMonitor(client=client, whatsapp_sender=whatsapp)

    symbol = "ETHUSDT"
    side = "SELL"
    leverage = 10
    qty = 7.0  # 7 ETH = ~$16,750 notional = ~$1,675 margin at 10x

    # 1. Fetch live price
    ticker = client.request('GET', '/fapi/v1/ticker/price', {'symbol': symbol})
    live_price = float(ticker.get('price', 2392.5))
    logger.info(f"Current live {symbol} price: ${live_price:.2f}")

    entry_price = live_price
    stop_loss = 2419.50   # Above 1H pivot ($2416.82)
    take_profit = 2345.00 # Major 4H swing support / liquidity pool

    sl_dist = stop_loss - entry_price
    tp_dist = entry_price - take_profit
    risk_usdt = qty * sl_dist
    reward_usdt = qty * tp_dist

    logger.info(f"Swing Plan: SHORT {qty} {symbol} @ ~${entry_price:.2f}")
    logger.info(f"  SL: ${stop_loss:.2f} (Risk: -${risk_usdt:.2f} USDT | -{sl_dist/entry_price*100:.2f}%)")
    logger.info(f"  TP: ${take_profit:.2f} (Target Reward: +${reward_usdt:.2f} USDT | +{tp_dist/entry_price*100:.2f}%)")
    logger.info(f"  Mid-Target ($2364): +${qty * (entry_price - 2364.0):.2f} USDT (Target $200 Achieved!)")

    # 2. Set Leverage
    try:
        client.set_leverage(symbol, leverage)
        logger.info(f"Leverage set to {leverage}x")
    except Exception as e:
        logger.warning(f"Set leverage exception: {e}")

    # 3. Clean stale orders
    try:
        client.cancel_all_open_orders(symbol)
        logger.info("Cleared prior open orders on " + symbol)
    except Exception as e:
        logger.warning(f"Cancel orders exception: {e}")

    # 4. Market Entry Order
    entry_res = client.place_market_order(symbol, side=side, quantity=qty)
    if "orderId" not in entry_res:
        logger.error(f"Entry order failed: {entry_res}")
        return

    order_id = entry_res["orderId"]
    fill_price = float(entry_res.get("avgPrice", 0.0) or entry_price)
    if fill_price <= 0:
        fill_price = entry_price
    logger.info(f"SHORT Order FILLED! OrderId={order_id}, FillPrice=${fill_price:.2f}")

    # 5. Place STOP_MARKET
    exit_side = "BUY"
    sl_res = client.place_stop_loss(
        symbol=symbol,
        side=exit_side,
        stop_price=stop_loss,
        quantity=qty
    )
    sl_id = sl_res.get("algoId", sl_res.get("orderId", "N/A"))
    logger.info(f"Stop-Loss Placed! Price=${stop_loss:.2f}, ID={sl_id}")

    # 6. Place TAKE_PROFIT_MARKET
    tp_res = client.place_take_profit(
        symbol=symbol,
        side=exit_side,
        tp_price=take_profit,
        quantity=qty
    )
    tp_id = tp_res.get("algoId", tp_res.get("orderId", "N/A"))
    logger.info(f"Take-Profit Placed! Price=${take_profit:.2f}, ID={tp_id}")

    # 7. Register with PositionMonitor for auto-CTC and WhatsApp tracking
    monitor.register_trade(
        symbol=symbol,
        side=side,
        entry_price=fill_price,
        initial_sl=stop_loss,
        tp_price=take_profit,
        qty=qty,
        sl_order_id=sl_id,
        tp_order_id=tp_id
    )
    logger.info("Trade successfully registered in .position_state.json for 24/7 CTC auto-trailing!")

    # 8. WhatsApp notification
    try:
        msg = (
            f"🎯 *NEW OVERNIGHT SWING TRADE EXECUTED (TARGET: $200+)*\n\n"
            f"📊 *Pair:* {symbol} (SHORT / SELL)\n"
            f"💰 *Position Size:* {qty} ETH (~${qty*fill_price:.2f} notional)\n"
            f"⚡ *Leverage:* {leverage}x (Margin: ~${(qty*fill_price)/leverage:.2f} USDT)\n"
            f"📍 *Entry Fill:* ${fill_price:.2f}\n"
            f"🛑 *Hard Stop-Loss:* ${stop_loss:.2f} (-${qty*(stop_loss-fill_price):.2f} USDT max risk)\n"
            f"🎯 *Full Swing Target (TP):* ${take_profit:.2f} (+${qty*(fill_price-take_profit):.2f} USDT reward)\n"
            f"🚀 *Mid-Target ($2364):* +$200.00 USDT Goal!\n\n"
            f"🛡️ *Risk Management:* Auto-Breakeven (CTC) will trigger at $2373.50 to make trade 100% risk-free!\n"
            f"⏰ *Holding Window:* Active till tomorrow 17:00 IST."
        )
        whatsapp.send_message(msg)
        logger.info("WhatsApp swing alert dispatched successfully.")
    except Exception as e:
        logger.warning(f"WhatsApp notification exception: {e}")

    print("\n" + "="*60)
    print("SUCCESSFULLY EXECUTED ETHUSDT SHORT SWING TRADE!")
    print(f"Fill: ${fill_price:.2f} | Size: {qty} ETH | SL: ${stop_loss:.2f} | TP: ${take_profit:.2f}")
    print("="*60)

if __name__ == "__main__":
    execute_swing()

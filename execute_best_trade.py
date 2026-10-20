from src.execution.binance_client import BinanceFuturesClient
from src.execution.order_manager import OrderManager
from src.execution.position_monitor import PositionMonitor
from src.notifications.whatsapp_alerts import WhatsAppAlertSender

print("=== EXECUTING BEST TRADE ON BINANCE (AVAX/USDT LONG) ===")

client = BinanceFuturesClient(
    'lfZVP4IAsiT7f4CKEmG5BwxX87N5d6HpttQZcp2c2T86upFhhAg1L0w5c0b3MHnc',
    '9N610nQD0LLAfuja6MJ3OORn1sf75jhqEIfZNhnkadCRGh2RQA3XtyJlCbCc5SBC',
    testnet=True
)

whatsapp = WhatsAppAlertSender()
order_manager = OrderManager(
    client=client,
    default_leverage=14,
    default_position_margin_usdt=150.0,
    whatsapp_sender=whatsapp
)
monitor = PositionMonitor(client=client, whatsapp_sender=whatsapp)

# Live Ticker for AVAXUSDT
t = client.request('GET', '/fapi/v1/ticker/price', {'symbol': 'AVAXUSDT'})
live_price = float(t.get('price', 10.03))
print(f"Live AVAXUSDT Price: ${live_price}")

entry_price = live_price
stop_loss = 9.97
take_profit = 10.17

print(f"Placing Trade: BUY AVAXUSDT @ ${entry_price} | Margin: $150 | Lev: 14x | SL: ${stop_loss} | TP: ${take_profit}")

res = order_manager.execute_trade(
    symbol='AVAXUSDT',
    side='BUY',
    entry_price=entry_price,
    stop_loss=stop_loss,
    take_profit=take_profit,
    margin_usdt=150.0,
    leverage=14,
    reason='Support Sweep Reclaim ($10.01 SSL Hunt) + 1H Bullish Momentum'
)

print("Execution Result:", res)

if res.get('status') == 'SUCCESS':
    monitor.register_trade(
        symbol='AVAXUSDT',
        side='BUY',
        entry_price=res['fill_price'],
        initial_sl=stop_loss,
        tp_price=take_profit,
        qty=res['quantity'],
        sl_order_id=res.get('sl_order_id'),
        tp_order_id=res.get('tp_order_id'),
    )
    print("AVAXUSDT trade registered with PositionMonitor for CTC auto-trailing!")

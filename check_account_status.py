from src.execution.binance_client import BinanceFuturesClient

client = BinanceFuturesClient(
    'lfZVP4IAsiT7f4CKEmG5BwxX87N5d6HpttQZcp2c2T86upFhhAg1L0w5c0b3MHnc',
    '9N610nQD0LLAfuja6MJ3OORn1sf75jhqEIfZNhnkadCRGh2RQA3XtyJlCbCc5SBC',
    testnet=True
)

# 1. Check open positions
positions = client.request('GET', '/fapi/v2/positionRisk')
active_pos = [p for p in positions if abs(float(p.get('positionAmt', 0))) > 0]
print(f"=== ACTIVE POSITIONS ({len(active_pos)}) ===")
for p in active_pos:
    s = p['symbol']
    amt = p['positionAmt']
    entry = float(p['entryPrice'])
    mark = float(p['markPrice'])
    pnl = float(p['unRealizedProfit'])
    lev = p['leverage']
    print(f"Symbol: {s} | Side: {p['positionSide']} | Amt: {amt} | Entry: ${entry:.4f} | Mark: ${mark:.4f} | PnL: ${pnl:+.2f} USDT | Lev: {lev}x")

# 2. Check recent trades
trades = client.request('GET', '/fapi/v1/userTrades', {'limit': 10})
print("\n=== RECENT TRADES (LAST 10) ===")
if isinstance(trades, list):
    for t in trades:
        s = t['symbol']
        side = t['side']
        qty = t['qty']
        price = float(t['price'])
        rpnl = float(t.get('realizedPnl', 0))
        t_time = t['time']
        print(f"Symbol: {s:<8} | Side: {side:<4} | Qty: {qty:<6} | Price: ${price:<10.4f} | Realized PnL: ${rpnl:+.2f} USDT | Time: {t_time}")
else:
    print("Trades response:", trades)

# 3. Check wallet balance
bal = client.request('GET', '/fapi/v2/balance')
if isinstance(bal, list):
    for b in bal:
        if b.get('asset') == 'USDT':
            print(f"\nUSDT Total Balance: ${float(b['balance']):.2f} | Available: ${float(b['availableBalance']):.2f}")

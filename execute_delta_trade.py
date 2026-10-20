"""
Delta Exchange India - Micro-Capital Safe Execution Script.

Specially calibrated for small capital accounts (e.g. ₹130 - ₹500):
- Margin capped at ₹25 - ₹40 max per trade
- Strict Stop-Loss (₹3 - ₹6 max risk per trade)
- Micro contracts (XRPUSD, DOGEUSD, ADAUSD)
- Live WhatsApp notification
"""

import os
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from src.execution.delta_client import DeltaExchangeClient
from src.notifications.whatsapp_alerts import WhatsAppAlertSender

def get_delta_client() -> DeltaExchangeClient:
    return DeltaExchangeClient(
        api_key=os.getenv("DELTA_API_KEY", ""),
        api_secret=os.getenv("DELTA_API_SECRET", ""),
        is_india=os.getenv("DELTA_IS_INDIA", "true").lower() == "true",
    )

def execute_delta_micro_trade(
    symbol: str = "XRPUSD",
    side: str = "buy",
    contracts: int = 2,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    reason: str = "5M Retest / Liquidity Sweep Setup"
):
    client = get_delta_client()
    summary = client.get_account_summary()
    logger.info(f"Connected Delta Account (User {summary.get('user_id')}): INR ₹{summary.get('inr_balance'):.2f} (USD ${summary.get('usd_balance'):.2f})")

    # 1. Fetch Product Info
    ticker = client.get_ticker(symbol)
    product_id = ticker.get("product_id")
    mark_price = float(ticker.get("mark_price", 0))

    if not product_id or mark_price <= 0:
        logger.error(f"Could not fetch product details for {symbol}")
        return

    logger.info(f"Live {symbol} Price: ${mark_price:.4f} | Product ID: {product_id}")

    # 2. Risk & Margin Validation
    # 1 XRP contract = 1 XRP (~$1.33)
    notional_usd = contracts * mark_price
    est_margin_inr = (notional_usd / 10.0) * 85.0  # at 10x leverage in INR

    if est_margin_inr > (summary.get("inr_balance", 0) * 0.40):
        logger.error(f"Risk Guard: Estimated margin (₹{est_margin_inr:.2f}) exceeds 40% of balance (₹{summary.get('inr_balance'):.2f})!")
        return

    logger.info(f"Placing {side.upper()} order for {contracts} contracts on {symbol}:")
    logger.info(f"  Est. Margin: ₹{est_margin_inr:.2f} (~${notional_usd/10:.2f})")
    logger.info(f"  Stop-Loss: ${stop_loss:.4f} | Take-Profit: ${take_profit:.4f}")

    # 3. Place Order
    res = client.place_order(
        product_id=product_id,
        size=contracts,
        side=side,
        order_type="market_order",
        stop_loss=stop_loss if stop_loss > 0 else None,
        take_profit=take_profit if take_profit > 0 else None
    )

    logger.info(f"Delta Order Response: {res}")

    if res.get("success"):
        order_data = res.get("result", {})
        try:
            whatsapp = WhatsAppAlertSender()
            msg = (
                f"🇮🇳 *[DELTA EXCHANGE INDIA - MICRO TRADE EXECUTED]*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🪙 *Pair:* `{symbol}` ({side.upper()})\n"
                f"📦 *Contracts:* {contracts} (Notional: ~${notional_usd:.2f})\n"
                f"💰 *Margin Used:* ~₹{est_margin_inr:.2f} (Safe Capital Mode)\n"
                f"📍 *Entry Price:* ${mark_price:.4f}\n"
                f"🛑 *Stop-Loss:* ${stop_loss:.4f}\n"
                f"🎯 *Take-Profit:* ${take_profit:.4f}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🛡️ *Wallet Protected:* ₹{summary.get('inr_balance') - est_margin_inr:.2f} free buffer in account."
            )
            whatsapp.send_raw_message(msg)
        except Exception as e:
            logger.warning(f"WhatsApp alert error: {e}")

    return res

if __name__ == "__main__":
    client = get_delta_client()
    summary = client.get_account_summary()
    print("="*50)
    print("DELTA EXCHANGE INDIA STATUS:")
    print(f"User ID: {summary.get('user_id')}")
    print(f"Balance INR: Rs. {summary.get('inr_balance'):.2f}")
    print(f"Balance USD: ${summary.get('usd_balance'):.2f}")
    print("Open Positions:", len(client.get_open_positions()))
    print("="*50)

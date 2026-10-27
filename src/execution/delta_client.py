"""
Delta Exchange API Execution Client (Global & India).

Supports:
- Delta Exchange India (api.india.delta.exchange) & Global (api.delta.exchange)
- Account Balance & Margin queries
- Position tracking & liquidation monitoring
- Market & Limit order execution
- Stop-Loss & Take-Profit bracket placement
"""

import os
import time
import hmac
import hashlib
import json
import urllib.parse
import socket
import urllib3.util.connection as urllib3_conn
from typing import Dict, Any, List, Optional
import requests
from loguru import logger
import ccxt
from dotenv import load_dotenv

# Force IPv4 across all HTTP/HTTPS requests to Delta Exchange
# to ensure IP-whitelisted IPv4 matches consistently regardless of ISP dual-stack IPv6
def _force_ipv4():
    return socket.AF_INET

urllib3_conn.allowed_gai_family = _force_ipv4

load_dotenv()

class DeltaExchangeClient:
    """Production client for Delta Exchange Futures & Options trading."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        is_india: Optional[bool] = None,
        testnet: Optional[bool] = None,
    ):
        if not api_key:
            api_key = os.getenv("DELTA_API_KEY", "")
        if not api_secret:
            api_secret = os.getenv("DELTA_API_SECRET", "")
        if is_india is None:
            is_india = os.getenv("DELTA_IS_INDIA", "true").lower() == "true"
        if testnet is None:
            testnet = os.getenv("DELTA_TESTNET", "false").lower() == "true"

        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.is_india = is_india
        self.testnet = testnet

        if testnet:
            self.base_url = "https://testnet-api.delta.exchange"
        elif is_india:
            self.base_url = "https://api.india.delta.exchange"
        else:
            self.base_url = "https://api.delta.exchange"

        # Initialize ccxt client as well for unified helpers
        config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
        }
        self.exchange = ccxt.delta(config)
        if not testnet and is_india:
            self.exchange.urls["api"]["public"] = "https://api.india.delta.exchange"
            self.exchange.urls["api"]["private"] = "https://api.india.delta.exchange"

        self.time_offset = 0
        logger.info(f"Initialized DeltaExchangeClient (Region: {'INDIA' if is_india else 'GLOBAL'}, Testnet: {testnet})")

    def _generate_signature(self, method: str, path: str, query_str: str, payload_str: str, timestamp: str) -> str:
        """Create HMAC-SHA256 signature required by Delta Exchange API."""
        msg = method.upper() + timestamp + path + query_str + payload_str
        return hmac.new(
            self.api_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send authenticated REST request to Delta Exchange with automatic time-offset sync."""
        url = self.base_url + path
        timestamp = str(int(time.time() + self.time_offset))
        query_str = ("?" + urllib.parse.urlencode(params)) if params else ""
        payload_str = json.dumps(data) if data else ""

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BotX-DeltaClient/1.0",
        }

        if self.api_key and self.api_secret:
            signature = self._generate_signature(method, path, query_str, payload_str, timestamp)
            headers["api-key"] = self.api_key
            headers["timestamp"] = timestamp
            headers["signature"] = signature

        full_url = url + query_str
        try:
            res = requests.request(
                method=method,
                url=full_url,
                headers=headers,
                data=payload_str if data else None,
                timeout=10
            )
            # Auto-handle clock drift if signature expired
            if res.status_code == 401 and "expired_signature" in res.text:
                try:
                    err_json = res.json()
                    srv_time = err_json.get("error", {}).get("context", {}).get("server_time")
                    if srv_time:
                        srv_val = float(srv_time)
                        if srv_val > 1e14:      # microseconds
                            srv_sec = srv_val / 1e6
                        elif srv_val > 1e11:    # milliseconds
                            srv_sec = srv_val / 1e3
                        else:                   # seconds
                            srv_sec = srv_val
                        self.time_offset = int(srv_sec - time.time())
                        logger.info(f"Auto-synchronized Delta server time offset to {self.time_offset}s. Retrying {path}...")
                        new_ts = str(int(time.time() + self.time_offset))
                        new_sig = self._generate_signature(method, path, query_str, payload_str, new_ts)
                        headers["timestamp"] = new_ts
                        headers["signature"] = new_sig
                        res = requests.request(method=method, url=full_url, headers=headers, data=payload_str if data else None, timeout=10)
                except Exception as sync_err:
                    logger.warning(f"Signature retry warning: {sync_err}")

            if res.status_code >= 400:
                logger.error(f"Delta API error ({path}) HTTP {res.status_code}: {res.text}")
                return {"success": False, "error": res.text, "status_code": res.status_code}
            return res.json()
        except Exception as e:
            logger.error(f"Delta Request failed ({path}): {e}")
            return {"success": False, "error": str(e)}

    def get_wallet_balances(self) -> List[Dict[str, Any]]:
        """Fetch all wallet balances (USDT, INR, BTC, etc.)."""
        res = self.request("GET", "/v2/wallet/balances")
        if isinstance(res, dict) and res.get("success"):
            return res.get("result", [])
        return []

    def get_account_summary(self) -> Dict[str, Any]:
        """Get summary of account balance in USD and INR."""
        balances = self.get_wallet_balances()
        usd_bal = 0.0
        inr_bal = 0.0
        user_id = None
        for b in balances:
            if b.get("asset_symbol") == "USD":
                usd_bal = float(b.get("available_balance", 0.0))
                inr_bal = float(b.get("available_balance_inr", 0.0))
                user_id = b.get("user_id")
                break
        return {
            "usd_balance": usd_bal,
            "inr_balance": inr_bal,
            "user_id": user_id,
        }

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Fetch active open positions."""
        res = self.request("GET", "/v2/positions/margined")
        if isinstance(res, dict) and res.get("success"):
            return res.get("result", [])
        return []

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker for symbol (e.g. BTCUSD or BTCUSDT)."""
        sym = symbol.replace("/", "").upper()
        res = self.request("GET", f"/v2/tickers/{sym}")
        if isinstance(res, dict) and res.get("success"):
            return res.get("result", {})
        return {}

    def set_leverage(self, product_id: int, leverage: int = 10) -> Dict[str, Any]:
        """Set isolated product leverage on Delta Exchange (e.g. 10x for safe margin buffer)."""
        res = self.request("POST", f"/v2/products/{product_id}/orders/leverage", data={"leverage": str(leverage)})
        if res.get("success"):
            logger.info(f"Leverage successfully set to {leverage}x for product {product_id}")
        else:
            logger.warning(f"Could not set leverage to {leverage}x for product {product_id}: {res}")
        return res

    def place_order(
        self,
        product_id: int,
        size: int,
        side: str,
        order_type: str = "market_order",
        limit_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        leverage: int = 10,
    ) -> Dict[str, Any]:
        """
        Place an order on Delta Exchange with automated SL/TP brackets.
        side: 'buy' or 'sell'
        order_type: 'market_order' or 'limit_order'
        """
        # Ensure safe leverage before entering so liquidation buffer is wide (8-10%)
        try:
            self.set_leverage(product_id, leverage=leverage)
        except Exception as e:
            logger.warning(f"Leverage adjustment error: {e}")

        body = {
            "product_id": product_id,
            "size": size,
            "side": side.lower(),
            "order_type": order_type,
        }
        if limit_price and order_type == "limit_order":
            body["limit_price"] = str(limit_price)

        logger.info(f"Placing Delta order: ProductID={product_id}, Side={side}, Size={size}")
        entry_res = self.request("POST", "/v2/orders", data=body)

        if not entry_res.get("success"):
            return entry_res

        exit_side = "sell" if side.lower() == "buy" else "buy"

        # Place Stop-Loss (reduce_only)
        if stop_loss:
            try:
                sl_price_str = f"{float(stop_loss):.4f}" if isinstance(stop_loss, (int, float)) else str(stop_loss)
                sl_body = {
                    "product_id": product_id,
                    "size": size,
                    "side": exit_side,
                    "order_type": "market_order",
                    "stop_order_type": "stop_loss_order",
                    "stop_price": sl_price_str,
                    "reduce_only": True,
                }
                sl_res = self.request("POST", "/v2/orders", data=sl_body)
                logger.info(f"Stop-Loss Placed on Delta: {sl_res.get('success')}")
            except Exception as e:
                logger.warning(f"Could not place Delta SL order: {e}")

        # Place Take-Profit (reduce_only)
        if take_profit:
            try:
                tp_price_str = f"{float(take_profit):.4f}" if isinstance(take_profit, (int, float)) else str(take_profit)
                tp_body = {
                    "product_id": product_id,
                    "size": size,
                    "side": exit_side,
                    "order_type": "limit_order",
                    "limit_price": tp_price_str,
                    "reduce_only": True,
                }
                tp_res = self.request("POST", "/v2/orders", data=tp_body)
                logger.info(f"Take-Profit Placed on Delta: {tp_res.get('success')}")
            except Exception as e:
                logger.warning(f"Could not place Delta TP order: {e}")

        return entry_res

    def get_live_orders(self, product_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all currently open/active orders."""
        params = {"state": "open"}
        if product_id:
            params["product_id"] = str(product_id)
        res = self.request("GET", "/v2/orders", params=params)
        if isinstance(res, dict) and res.get("success"):
            return res.get("result", [])
        return []

    def cancel_order(self, order_id: int, product_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        body = {"id": order_id, "product_id": product_id}
        return self.request("DELETE", "/v2/orders", data=body)

    def cancel_all_orders(self, product_id: Optional[int] = None) -> Dict[str, Any]:
        """Cancel all open orders."""
        body = {"product_id": product_id} if product_id else {}
        return self.request("POST", "/v2/orders/cancel_all", data=body)

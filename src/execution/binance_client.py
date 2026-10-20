"""
Unified Binance Trading Client (Spot & USDT-M Futures, Live & Testnet).

Supports:
- Binance Futures Testnet (https://testnet.binancefuture.com)
- Binance Futures Live (https://fapi.binance.com)
- Standard Market & Limit Orders (/fapi/v1/order)
- Conditional SL & TP Orders via Algo Order API (/fapi/v1/algoOrder)
"""

import hmac
import hashlib
import time
import urllib.request
import urllib.parse
import json
from typing import Dict, Any, List, Optional
from loguru import logger


class BinanceFuturesClient:
    """Production-grade client for Binance USDT-M Futures (Testnet & Live)."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        recv_window: int = 10000,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.recv_window = recv_window
        self.time_offset = 0
        self.base_url = (
            "https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com"
        )
        self._sync_time()
        logger.info(
            f"Initialized BinanceFuturesClient (Mode: {'TESTNET (DEMO)' if testnet else 'LIVE PRODUCTION'}, TimeOffset: {self.time_offset}ms)"
        )

    def _sync_time(self) -> None:
        """Synchronize client time offset with Binance server time."""
        try:
            url = f"{self.base_url}/fapi/v1/time"
            req = urllib.request.Request(url, headers={"User-Agent": "BotX/2.0"}, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                server_time = int(data.get("serverTime", 0))
                if server_time > 0:
                    local_time = int(time.time() * 1000)
                    # Subtract 500ms safety buffer so request timestamp is never ahead of server time
                    self.time_offset = (server_time - local_time) - 500
                    logger.info(f"Binance time synchronized. Offset: {self.time_offset}ms (Server: {server_time}, Local: {local_time})")
        except Exception as e:
            logger.warning(f"Failed to sync time with Binance server: {e}")
            self.time_offset = -1500

    def _sign(self, params: Dict[str, Any]) -> str:
        """Create HMAC-SHA256 signature for parameters."""
        query = urllib.parse.urlencode(params)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = True,
        retry_on_drift: bool = True,
    ) -> Dict[str, Any]:
        """Execute HTTP request to Binance Futures API with drift handling."""
        orig_params = params.copy() if params else {}
        params = orig_params.copy()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "BotX/2.0",
        }

        if signed:
            headers["X-MBX-APIKEY"] = self.api_key
            params["timestamp"] = int(time.time() * 1000) + getattr(self, "time_offset", 0)
            params["recvWindow"] = self.recv_window
            params["signature"] = self._sign(params)

        query = urllib.parse.urlencode(params) if params else ""
        if method.upper() in ["GET", "DELETE"]:
            url = f"{self.base_url}{path}?{query}" if query else f"{self.base_url}{path}"
            req = urllib.request.Request(url, headers=headers, method=method.upper())
        else:
            url = f"{self.base_url}{path}"
            req = urllib.request.Request(
                url,
                data=query.encode("utf-8"),
                headers=headers,
                method=method.upper(),
            )

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"Binance Futures API Error ({path}) HTTP {e.code}: {err_body}")
            try:
                res = json.loads(err_body)
                if signed and retry_on_drift and res.get("code") == -1021:
                    logger.warning("Timestamp error -1021 encountered. Re-syncing clock and retrying...")
                    self._sync_time()
                    return self.request(method, path, orig_params, signed=signed, retry_on_drift=False)
                return res
            except Exception:
                return {"code": e.code, "msg": err_body}
        except Exception as e:
            logger.error(f"Binance Futures Request Exception: {e}")
            return {"code": -1, "msg": str(e)}

    # ─────────────────────────────────────────────────────────────
    # Account & Balances
    # ─────────────────────────────────────────────────────────────
    def get_account_info(self) -> Dict[str, Any]:
        """Fetch account overview and total balances."""
        return self.request("GET", "/fapi/v2/account")

    def get_usdt_balance(self) -> float:
        """Fetch available USDT balance."""
        res = self.request("GET", "/fapi/v2/balance")
        if isinstance(res, list):
            for item in res:
                if item.get("asset") == "USDT":
                    return float(item.get("availableBalance", 0.0))
        return 0.0

    # ─────────────────────────────────────────────────────────────
    # Leverage & Position Settings
    # ─────────────────────────────────────────────────────────────
    def set_leverage(self, symbol: str, leverage: int = 7) -> Dict[str, Any]:
        """Set symbol leverage (e.g. 7x)."""
        sym = symbol.replace("/", "").upper()
        return self.request("POST", "/fapi/v1/leverage", {"symbol": sym, "leverage": leverage})

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get open position risk for symbol."""
        sym = symbol.replace("/", "").upper()
        res = self.request("GET", "/fapi/v2/positionRisk", {"symbol": sym})
        if isinstance(res, list) and len(res) > 0:
            return res[0]
        return None

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Fetch all currently open positions with non-zero positionAmt."""
        res = self.request("GET", "/fapi/v2/positionRisk")
        if isinstance(res, list):
            return [p for p in res if abs(float(p.get("positionAmt", 0))) > 0]
        return []

    # ─────────────────────────────────────────────────────────────
    # Order Placement (Market Entry & Algo Conditional SL/TP)
    # ─────────────────────────────────────────────────────────────
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """Place Market Entry Order."""
        sym = symbol.replace("/", "").upper()
        params = {
            "symbol": sym,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(quantity),
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        return self.request("POST", "/fapi/v1/order", params)

    def _format_price(self, symbol: str, price: float) -> str:
        sym = symbol.replace("/", "").upper()
        if "XRP" in sym:
            return f"{price:.4f}"
        elif "AVAX" in sym:
            return f"{price:.3f}"
        else:
            return f"{price:.2f}"

    def place_stop_loss(
        self,
        symbol: str,
        side: str,
        stop_price: float,
        quantity: float,
    ) -> Dict[str, Any]:
        """
        Place STOP_MARKET conditional order via Algo Order API.
        """
        sym = symbol.replace("/", "").upper()
        params = {
            "symbol": sym,
            "side": side.upper(),
            "algoType": "CONDITIONAL",
            "type": "STOP_MARKET",
            "triggerPrice": self._format_price(sym, stop_price),
            "quantity": str(quantity),
            "reduceOnly": "true",
        }
        return self.request("POST", "/fapi/v1/algoOrder", params)

    def place_take_profit(
        self,
        symbol: str,
        side: str,
        tp_price: float,
        quantity: float,
    ) -> Dict[str, Any]:
        """
        Place TAKE_PROFIT_MARKET conditional order via Algo Order API.
        """
        sym = symbol.replace("/", "").upper()
        params = {
            "symbol": sym,
            "side": side.upper(),
            "algoType": "CONDITIONAL",
            "type": "TAKE_PROFIT_MARKET",
            "triggerPrice": self._format_price(sym, tp_price),
            "quantity": str(quantity),
            "reduceOnly": "true",
        }
        return self.request("POST", "/fapi/v1/algoOrder", params)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open standard orders."""
        params = {"symbol": symbol.replace("/", "").upper()} if symbol else {}
        res = self.request("GET", "/fapi/v1/openOrders", params)
        return res if isinstance(res, list) else []

    def get_open_algo_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open algo/conditional orders."""
        params = {"symbol": symbol.replace("/", "").upper()} if symbol else {}
        res = self.request("GET", "/fapi/v1/openAlgoOrders", params)
        return res if isinstance(res, list) else []

    def cancel_algo_order(self, symbol: str, algo_id: Any) -> Dict[str, Any]:
        """Cancel an algorithmic conditional order."""
        sym = symbol.replace("/", "").upper()
        return self.request("DELETE", "/fapi/v1/algoOrder", {"symbol": sym, "algoId": algo_id})

    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel standard open orders for a symbol."""
        sym = symbol.replace("/", "").upper()
        return self.request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": sym})

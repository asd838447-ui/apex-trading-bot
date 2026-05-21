"""
APEX Trading Bot — Exchange REST Client
REST API клиент для Binance Futures с HMAC SHA256 подписью.
"""

import hashlib
import hmac
import time
import logging
from typing import Optional
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)

# Binance Futures API endpoints
FUTURES_BASE_URL = "https://fapi.binance.com"
FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"


class BinanceClient:
    """
    Асинхронный REST клиент для Binance Futures.
    Поддерживает testnet и production.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = FUTURES_TESTNET_URL if testnet else FUTURES_BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self.recv_window = 5000

    async def _ensure_session(self):
        """Создаёт aiohttp сессию если не создана."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"X-MBX-APIKEY": self.api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            )

    def _sign(self, params: dict) -> dict:
        """Добавляет timestamp и HMAC SHA256 подпись к параметрам."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        signed: bool = False,
    ) -> dict:
        """Выполняет HTTP запрос к API."""
        await self._ensure_session()

        if params is None:
            params = {}

        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError(
                    "API key и secret необходимы для подписанных запросов"
                )
            params = self._sign(params)

        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                async with self.session.get(url, params=params) as response:
                    data = await response.json()
                    if response.status != 200:
                        logger.error(f"Binance API error: {data}")
                        raise Exception(f"API error: {data.get('msg', 'Unknown')}")
                    return data
            elif method == "POST":
                async with self.session.post(url, data=params) as response:
                    data = await response.json()
                    if response.status != 200:
                        logger.error(f"Binance API error: {data}")
                        raise Exception(f"API error: {data.get('msg', 'Unknown')}")
                    return data
            elif method == "DELETE":
                async with self.session.delete(url, params=params) as response:
                    data = await response.json()
                    if response.status != 200:
                        logger.error(f"Binance API error: {data}")
                        raise Exception(f"API error: {data.get('msg', 'Unknown')}")
                    return data

        except aiohttp.ClientError as e:
            logger.error(f"HTTP ошибка: {e}")
            raise

    # === Public endpoints ===

    async def get_price(self, symbol: str = "BTCUSDT") -> float:
        """Получает текущую цену символа."""
        data = await self._request(
            "GET", "/fapi/v1/ticker/price", {"symbol": symbol}
        )
        return float(data.get("price", 0))

    async def get_orderbook(
        self, symbol: str = "BTCUSDT", limit: int = 20
    ) -> dict:
        """Получает стакан ордеров."""
        data = await self._request(
            "GET", "/fapi/v1/depth", {"symbol": symbol, "limit": limit}
        )
        return data

    async def get_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "15m",
        limit: int = 500,
    ) -> list:
        """Получает исторические свечи."""
        data = await self._request(
            "GET",
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        return data

    # === Authenticated endpoints ===

    async def place_limit(
        self,
        side: str,
        price: float,
        qty: float,
        symbol: str = "BTCUSDT",
    ) -> str:
        """
        Выставляет лимитный ордер.

        Args:
            side: 'BUY' или 'SELL'
            price: цена
            qty: количество
            symbol: торговая пара

        Returns:
            order_id
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": f"{qty:.3f}",
            "price": f"{price:.2f}",
        }

        data = await self._request("POST", "/fapi/v1/order", params, signed=True)
        order_id = str(data.get("orderId", ""))
        logger.info(
            f"Ордер выставлен: {side} {qty} {symbol} @ {price}, id={order_id}"
        )
        return order_id

    async def place_market(
        self,
        side: str,
        qty: float,
        symbol: str = "BTCUSDT",
    ) -> str:
        """Выставляет маркет-ордер."""
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": f"{qty:.3f}",
        }

        data = await self._request("POST", "/fapi/v1/order", params, signed=True)
        return str(data.get("orderId", ""))

    async def cancel_order(
        self, order_id: str, symbol: str = "BTCUSDT"
    ) -> dict:
        """Отменяет ордер по ID."""
        params = {"symbol": symbol, "orderId": int(order_id)}
        data = await self._request("DELETE", "/fapi/v1/order", params, signed=True)
        logger.info(f"Ордер отменён: {order_id}")
        return data

    async def cancel_all_orders(self, symbol: str = "BTCUSDT") -> dict:
        """Отменяет все открытые ордера по символу."""
        params = {"symbol": symbol}
        data = await self._request(
            "DELETE", "/fapi/v1/allOpenOrders", params, signed=True
        )
        logger.info(f"Все ордера отменены для {symbol}")
        return data

    async def get_position(self, symbol: str = "BTCUSDT") -> dict:
        """Получает текущую позицию."""
        data = await self._request(
            "GET", "/fapi/v2/positionRisk", {"symbol": symbol}, signed=True
        )
        if isinstance(data, list) and data:
            pos = data[0]
            return {
                "symbol": pos.get("symbol"),
                "side": "LONG" if float(pos.get("positionAmt", 0)) > 0 else "SHORT",
                "size": abs(float(pos.get("positionAmt", 0))),
                "entry_price": float(pos.get("entryPrice", 0)),
                "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
                "leverage": int(pos.get("leverage", 1)),
                "margin_type": pos.get("marginType", "cross"),
            }
        return {}

    async def get_balance(self) -> float:
        """Получает баланс USDT."""
        data = await self._request(
            "GET", "/fapi/v2/balance", {}, signed=True
        )
        if isinstance(data, list):
            for asset in data:
                if asset.get("asset") == "USDT":
                    return float(asset.get("balance", 0))
        return 0.0

    async def set_leverage(
        self, leverage: int, symbol: str = "BTCUSDT"
    ) -> dict:
        """Устанавливает плечо."""
        params = {"symbol": symbol, "leverage": leverage}
        data = await self._request(
            "POST", "/fapi/v1/leverage", params, signed=True
        )
        logger.info(f"Плечо установлено: {symbol} x{leverage}")
        return data

    async def get_open_orders(self, symbol: str = "BTCUSDT") -> list:
        """Получает список открытых ордеров."""
        data = await self._request(
            "GET", "/fapi/v1/openOrders", {"symbol": symbol}, signed=True
        )
        return data if isinstance(data, list) else []

    async def close(self):
        """Закрывает HTTP сессию."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Exchange client: сессия закрыта")

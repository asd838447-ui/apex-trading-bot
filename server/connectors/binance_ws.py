"""
APEX Trading Bot — Binance WebSocket Connector
Подключение к Binance Futures WebSocket для получения реальных рыночных данных.
"""

import asyncio
import json
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Стримы для BTC/USDT Futures
STREAMS = [
    "btcusdt@aggTrade",    # Тиковые сделки (для CVD)
    "btcusdt@kline_15m",   # Свечи 15M
    "btcusdt@kline_4h",    # Свечи 4H
    "btcusdt@kline_1d",    # Свечи 1D
]

BASE_URL = "wss://fstream.binance.com/market/stream?streams="


class BinanceWSConnector:
    """
    WebSocket коннектор к биржевым котировкам с автоматическим переключением источников
    (Binance Futures, Binance Spot, Bybit Futures) и exponential backoff.
    """

    def __init__(self):
        self.ws = None
        self.running = False
        self.reconnect_delay = 1  # Начальная задержка (секунды)
        self.max_reconnect_delay = 60
        self.last_message_time = 0
        self.message_count = 0

        # Callbacks для обработки данных
        self._on_tick: Optional[Callable] = None
        self._on_orderbook: Optional[Callable] = None
        self._on_candle: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        # Кеш текущих данных
        self.current_price: float = 0.0
        self.orderbook: dict = {"bids": [], "asks": []}
        self.latest_candles: dict = {}

        # Резервные эндпоинты
        self.endpoints = [
            {
                "name": "Binance Futures WS",
                "type": "binance",
                "url": BASE_URL + "/".join(STREAMS)
            },
            {
                "name": "Binance Spot WS",
                "type": "binance",
                "url": "wss://stream.binance.com:9443/stream?streams=" + "/".join(STREAMS)
            },
            {
                "name": "Bybit Public WS",
                "type": "bybit",
                "url": "wss://stream.bybit.com/v5/public/linear",
                "subscribe": {
                    "op": "subscribe",
                    "args": ["publicTrade.BTCUSDT", "kline.15.BTCUSDT", "kline.240.BTCUSDT", "kline.D.BTCUSDT"]
                }
            }
        ]
        self.current_endpoint_idx = 0

    def on_tick(self, callback: Callable):
        """Регистрирует callback для тиковых данных."""
        self._on_tick = callback

    def on_orderbook(self, callback: Callable):
        """Регистрирует callback для обновлений стакана."""
        self._on_orderbook = callback

    def on_candle(self, callback: Callable):
        """Регистрирует callback для свечных данных."""
        self._on_candle = callback

    async def connect(self):
        """Основной цикл подключения с автоматическим переподключением по списку источников."""
        self.running = True

        while self.running:
            endpoint = self.endpoints[self.current_endpoint_idx]
            try:
                # Динамический импорт websockets
                import websockets
                import ssl

                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                logger.info(f"Подключение к бэкенд цене ({endpoint['name']}): {endpoint['url'][:80]}...")
                async with websockets.connect(
                    endpoint["url"],
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    ssl=ssl_context,
                ) as ws:
                    self.ws = ws
                    self.reconnect_delay = 1  # Сброс задержки при успешном подключении
                    logger.info(f"Бэкенд WS: подключено успешно к {endpoint['name']}")

                    if "subscribe" in endpoint:
                        await ws.send(json.dumps(endpoint["subscribe"]))

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if endpoint["type"] == "binance":
                                stream = data.get("stream", "")
                                payload = data.get("data", {})
                                await self._process(payload, stream)
                            elif endpoint["type"] == "bybit":
                                await self._process_bybit(data)
                            
                            self.last_message_time = time.time()
                            self.message_count += 1
                        except json.JSONDecodeError:
                            logger.warning("Невалидный JSON от WS")
                        except Exception as e:
                            logger.error(f"Ошибка обработки сообщения WS: {e}")

            except ImportError:
                logger.error(
                    "Библиотека websockets не установлена. "
                    "Установите: pip install websockets"
                )
                self.running = False
                return

            except Exception as e:
                if not self.running:
                    break
                logger.warning(
                    f"Бэкенд WS ({endpoint['name']}): отключено ({e}), "
                    f"переключение на следующий источник..."
                )
                if self._on_error:
                    await self._on_error(str(e))
                
                # Switch to the next fallback endpoint
                self.current_endpoint_idx = (self.current_endpoint_idx + 1) % len(self.endpoints)
                
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(
                    self.reconnect_delay * 2, self.max_reconnect_delay
                )

    async def _process_bybit(self, raw: dict):
        """Обработка Bybit public trade и kline данных."""
        topic = raw.get("topic", "")
        payload = raw.get("data", [])
        if not payload:
            return

        if "publicTrade" in topic:
            for t in payload:
                tick = {
                    "time": int(t.get("T", time.time() * 1000)),
                    "symbol": "BTCUSDT",
                    "price": float(t.get("p", 0)),
                    "qty": float(t.get("v", 0)),
                    "is_buyer": t.get("S", "Buy") == "Buy",
                }
                self.current_price = tick["price"]
                if self._on_tick:
                    try:
                        await self._on_tick(tick)
                    except Exception as e:
                        logger.error(f"Ошибка в tick callback (Bybit): {e}")
        elif "kline" in topic:
            for k in payload:
                bybit_tf = k.get("interval", "15")
                tf_map = {"15": "15m", "240": "4h", "D": "1d"}
                tf = tf_map.get(bybit_tf, "15m")
                
                candle = {
                    "time": int(k.get("start", 0)),
                    "symbol": "BTCUSDT",
                    "tf": tf,
                    "open": float(k.get("open", 0)),
                    "high": float(k.get("high", 0)),
                    "low": float(k.get("low", 0)),
                    "close": float(k.get("close", 0)),
                    "volume": float(k.get("volume", 0)),
                    "is_closed": k.get("confirm", False),
                }
                self.latest_candles[tf] = candle
                if self._on_candle:
                    try:
                        await self._on_candle(candle)
                    except Exception as e:
                        logger.error(f"Ошибка в candle callback (Bybit): {e}")

    async def _process(self, data: dict, stream: str):
        """Диспетчер: направляет данные в соответствующий обработчик."""
        if "aggTrade" in stream:
            await self._handle_tick(data)
        elif "depth" in stream:
            await self._handle_orderbook(data)
        elif "kline" in stream:
            await self._handle_candle(data)

    async def _handle_tick(self, data: dict):
        """Обработка агрегированных сделок."""
        tick = {
            "time": data.get("T", 0),  # Trade time
            "symbol": data.get("s", "BTCUSDT"),
            "price": float(data.get("p", 0)),
            "qty": float(data.get("q", 0)),
            "is_buyer": data.get("m", False) is False,  # m=true значит seller
        }
        self.current_price = tick["price"]

        if self._on_tick:
            try:
                await self._on_tick(tick)
            except Exception as e:
                logger.error(f"Ошибка в tick callback: {e}")

    async def _handle_orderbook(self, data: dict):
        """Обработка снимка стакана."""
        self.orderbook = {
            "bids": [
                (float(price), float(qty))
                for price, qty in data.get("bids", [])[:20]
            ],
            "asks": [
                (float(price), float(qty))
                for price, qty in data.get("asks", [])[:20]
            ],
            "time": data.get("T", time.time() * 1000),
        }

        if self._on_orderbook:
            try:
                await self._on_orderbook(self.orderbook)
            except Exception as e:
                logger.error(f"Ошибка в orderbook callback: {e}")

    async def _handle_candle(self, data: dict):
        """Обработка свечных данных."""
        kline = data.get("k", {})
        candle = {
            "time": kline.get("t", 0),  # Kline start time
            "symbol": kline.get("s", "BTCUSDT"),
            "tf": kline.get("i", ""),  # Interval
            "open": float(kline.get("o", 0)),
            "high": float(kline.get("h", 0)),
            "low": float(kline.get("l", 0)),
            "close": float(kline.get("c", 0)),
            "volume": float(kline.get("v", 0)),
            "is_closed": kline.get("x", False),
        }
        self.latest_candles[candle["tf"]] = candle

        if self._on_candle:
            try:
                await self._on_candle(candle)
            except Exception as e:
                logger.error(f"Ошибка в candle callback: {e}")

    async def disconnect(self):
        """Отключение от WebSocket."""
        self.running = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        logger.info("Binance WS: отключено")

    def get_status(self) -> dict:
        """Возвращает статус подключения."""
        return {
            "connected": self.ws is not None and self.running,
            "current_price": self.current_price,
            "message_count": self.message_count,
            "last_message_age": (
                time.time() - self.last_message_time
                if self.last_message_time > 0
                else None
            ),
            "streams": STREAMS,
        }

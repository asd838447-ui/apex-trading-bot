"""
APEX Trading Bot — WebSocket Handler
WebSocket endpoint для real-time обновлений дашборда.
"""

import json
import asyncio
import logging
import time
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from server.api.routes import _generate_demo_signals, _generate_demo_regime
from server.tasks.state import market_state

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Менеджер WebSocket подключений."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Принимает новое WebSocket подключение."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(
            f"WS клиент подключен. Всего: {len(self.active_connections)}"
        )

    async def disconnect(self, websocket: WebSocket):
        """Отключает WebSocket клиента."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(
            f"WS клиент отключен. Всего: {len(self.active_connections)}"
        )

    async def broadcast(self, message: dict):
        """Отправляет сообщение всем подключённым клиентам."""
        if not self.active_connections:
            return

        data = json.dumps(message, default=str)
        disconnected = []

        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(data)
                except Exception:
                    disconnected.append(connection)

        # Удаляем отключённых
        for conn in disconnected:
            async with self._lock:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Отправляет персональное сообщение клиенту."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Ошибка отправки персонального сообщения: {e}")

    @property
    def count(self) -> int:
        return len(self.active_connections)


# Глобальный менеджер
manager = ConnectionManager()


async def ws_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для дашборда.
    Отправляет периодические обновления: сигналы, цена, equity, trades.
    """
    await manager.connect(websocket)

    # Отправляем начальное состояние
    await manager.send_personal(websocket, {
        "type": "init",
        "data": {
            "status": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_version": "1.0.0",
        },
    })

    try:
        # Запускаем фоновую задачу для отправки обновлений
        update_task = asyncio.create_task(
            _send_periodic_updates(websocket)
        )

        # Слушаем входящие сообщения от клиента
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await _handle_client_message(websocket, message)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.warning("Невалидный JSON от WS клиента")
            except Exception as e:
                logger.error(f"Ошибка WS: {e}")
                break

    finally:
        update_task.cancel()
        await manager.disconnect(websocket)


async def _send_periodic_updates(websocket: WebSocket):
    """Отправляет периодические обновления клиенту."""
    try:
        await market_state.initialize_if_needed()
        
        while True:
            # 1. Отправка реальной цены (каждые 2 секунды)
            await manager.send_personal(websocket, {
                "type": "price_update",
                "data": {
                    "symbol": "BTCUSDT",
                    "price": round(market_state.btc_price, 2),
                    "change_24h": round(market_state.price_change_24h, 2),
                    "volume_24h": round(market_state.volume_24h, 0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            })

            await asyncio.sleep(2)

            # 2. Обновление сигналов (каждые 8 секунд)
            if int(time.time()) % 8 < 2:
                signals = market_state.signals if market_state.signals else _generate_demo_signals()
                await manager.send_personal(websocket, {
                    "type": "signal_update",
                    "data": signals,
                })

            # 3. Обновление режима рынка (каждые 15 секунд)
            if int(time.time()) % 15 < 2:
                await manager.send_personal(websocket, {
                    "type": "regime_update",
                    "data": {
                        "current": market_state.regime,
                        "confidence": market_state.regime_confidence,
                        "history": _generate_demo_regime()["history"]
                    },
                })

            # 4. Обновление параметров риска (каждые 12 секунд)
            if int(time.time()) % 12 < 2:
                risk_data = market_state.get_risk_metrics()
                await manager.send_personal(websocket, {
                    "type": "risk_update",
                    "data": risk_data,
                })

            # 5. Обновление equity (каждые 20 секунд)
            if int(time.time()) % 20 < 2:
                daily_pnl = round(sum(t["pnl"] for t in market_state.trades if t["time"][:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d")), 2)
                await manager.send_personal(websocket, {
                    "type": "equity_update",
                    "data": {
                        "equity": market_state.current_equity,
                        "daily_pnl": daily_pnl,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "drawdown": "0.00",
                    },
                })

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Ошибка в periodic updates: {e}")


async def _handle_client_message(websocket: WebSocket, message: dict):
    """Обрабатывает входящие сообщения от клиента."""
    msg_type = message.get("type", "")

    if msg_type == "ping":
        await manager.send_personal(websocket, {
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    elif msg_type == "subscribe":
        channel = message.get("channel", "")
        logger.info(f"Клиент подписался на канал: {channel}")
        await manager.send_personal(websocket, {
            "type": "subscribed",
            "channel": channel,
        })

    elif msg_type == "request_signals":
        signals = _generate_demo_signals()
        await manager.send_personal(websocket, {
            "type": "signal_update",
            "data": signals,
        })

    else:
        logger.debug(f"Неизвестный тип WS сообщения: {msg_type}")

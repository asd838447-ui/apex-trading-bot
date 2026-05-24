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
from server.tasks.state import market_state

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Менеджер WebSocket подключений с безопасной сериализацией записи."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._write_locks: dict[WebSocket, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Принимает новое WebSocket подключение."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
            self._write_locks[websocket] = asyncio.Lock()
        logger.info(
            f"WS клиент подключен. Всего: {len(self.active_connections)}"
        )

    async def disconnect(self, websocket: WebSocket):
        """Отключает WebSocket клиента."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            if websocket in self._write_locks:
                del self._write_locks[websocket]
        logger.info(
            f"WS клиент отключен. Всего: {len(self.active_connections)}"
        )

    async def broadcast(self, message: dict):
        """Отправляет сообщение всем подключённым клиентам с блокировкой на запись."""
        if not self.active_connections:
            return

        data = json.dumps(message, default=str)
        disconnected = []

        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            lock = self._write_locks.get(connection)
            if not lock:
                continue
            async with lock:
                try:
                    await connection.send_text(data)
                except Exception:
                    disconnected.append(connection)

        # Удаляем отключённых
        if disconnected:
            for conn in disconnected:
                await self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Отправляет персональное сообщение клиенту с блокировкой на запись."""
        lock = self._write_locks.get(websocket)
        if not lock:
            return
        async with lock:
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

    # Immediate state synchronization upon connection
    try:
        from server.config import settings
        await market_state.initialize_if_needed()
        
        # Send price_update for all supported symbols
        for symbol in settings.SUPPORTED_SYMBOLS:
            price = market_state.prices.get(symbol, 93250.0 if symbol == "BTCUSDT" else 3500.0 if symbol == "ETHUSDT" else 150.0)
            change_24h = market_state.price_changes_24h.get(symbol, 0.0)
            volume_24h = market_state.volumes_24h.get(symbol, 0.0)
            await manager.send_personal(websocket, {
                "type": "price_update",
                "data": {
                    "symbol": symbol,
                    "price": round(price, 2 if symbol != "SOLUSDT" else 3),
                    "change_24h": round(change_24h, 2),
                    "volume_24h": round(volume_24h, 0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            })

        # Send signal_update for all supported symbols
        for symbol in settings.SUPPORTED_SYMBOLS:
            signals = market_state.multi_signals.get(symbol)
            if signals:
                await manager.send_personal(websocket, {
                    "type": "signal_update",
                    "data": {
                        "symbol": symbol,
                        "signals": signals
                    },
                })

        # Send regime_update for all supported symbols
        for symbol in settings.SUPPORTED_SYMBOLS:
            await manager.send_personal(websocket, {
                "type": "regime_update",
                "data": {
                    "symbol": symbol,
                    "current": market_state.regimes.get(symbol, "TREND"),
                    "confidence": market_state.regime_confidences.get(symbol, 85.0),
                    "history": market_state.regime_histories.get(symbol, [])
                },
            })

        # Send risk_update for all supported symbols
        for symbol in settings.SUPPORTED_SYMBOLS:
            await manager.send_personal(websocket, {
                "type": "risk_update",
                "data": {
                    "symbol": symbol,
                    "metrics": market_state.get_risk_metrics(symbol=symbol)
                },
            })

        # Send quant_alphas for all supported symbols
        from server.skills.skill_03_onchain import get_quant_alphas
        for symbol in settings.SUPPORTED_SYMBOLS:
            await manager.send_personal(websocket, {
                "type": "quant_alphas_update",
                "data": {
                    "symbol": symbol,
                    "metrics": get_quant_alphas(symbol)
                },
            })

        # Send equity_update (shared/portfolio level)
        daily_pnl = round(sum(t.get("pnl", 0) or 0 for t in market_state.trades if t.get("time", "")[:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d")), 2)
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
    except Exception as e:
        logger.error(f"Error during WS initial state sync: {e}")

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
        from server.config import settings
        await market_state.initialize_if_needed()
        
        while True:
            now_sec = int(time.time())
            
            # 1. Обновление сигналов (каждые 8 секунд)
            if now_sec % 8 < 2:
                for symbol in settings.SUPPORTED_SYMBOLS:
                    signals = market_state.multi_signals.get(symbol)
                    if signals:
                        await manager.send_personal(websocket, {
                            "type": "signal_update",
                            "data": {
                                "symbol": symbol,
                                "signals": signals
                            },
                        })

            # 2. Обновление режима рынка (каждые 15 секунд)
            if now_sec % 15 < 2:
                for symbol in settings.SUPPORTED_SYMBOLS:
                    await manager.send_personal(websocket, {
                        "type": "regime_update",
                        "data": {
                            "symbol": symbol,
                            "current": market_state.regimes.get(symbol, "TREND"),
                            "confidence": market_state.regime_confidences.get(symbol, 85.0),
                            "history": market_state.regime_histories.get(symbol, [])
                        },
                    })

            # 3. Обновление параметров риска (каждые 12 секунд)
            if now_sec % 12 < 2:
                for symbol in settings.SUPPORTED_SYMBOLS:
                    risk_data = market_state.get_risk_metrics(symbol=symbol)
                    await manager.send_personal(websocket, {
                        "type": "risk_update",
                        "data": {
                            "symbol": symbol,
                            "metrics": risk_data
                        },
                    })

            # 3.5 Обновление количественных метрик (каждые 10 секунд)
            if now_sec % 10 < 2:
                from server.skills.skill_03_onchain import get_quant_alphas
                for symbol in settings.SUPPORTED_SYMBOLS:
                    await manager.send_personal(websocket, {
                        "type": "quant_alphas_update",
                        "data": {
                            "symbol": symbol,
                            "metrics": get_quant_alphas(symbol)
                        },
                    })

            # 4. Обновление equity (каждые 20 секунд)
            if now_sec % 20 < 2:
                daily_pnl = round(sum(t.get("pnl", 0) or 0 for t in market_state.trades if t.get("time", "")[:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d")), 2)
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

            await asyncio.sleep(2)

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
        from server.config import settings
        for symbol in settings.SUPPORTED_SYMBOLS:
            signals = market_state.multi_signals.get(symbol)
            if signals:
                await manager.send_personal(websocket, {
                    "type": "signal_update",
                    "data": {
                        "symbol": symbol,
                        "signals": signals
                    },
                })

    else:
        logger.debug(f"Неизвестный тип WS сообщения: {msg_type}")

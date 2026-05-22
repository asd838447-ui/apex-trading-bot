"""
APEX Trading Bot — Order Executor
Исполнение ордеров: сетка лимитных ордеров, расчёт слиппеджа, управление позициями.
"""

import json
import time
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class OrderExecutor:
    """
    Управляет выставлением и закрытием ордеров.
    Вход дробится на 3 части: 40/35/25%.
    """

    def __init__(self, exchange_client=None, redis_client=None):
        self.exchange = exchange_client
        self.redis = redis_client
        self.active_orders: list[dict] = []
        self.positions: list[dict] = []

    async def open_position(
        self,
        signal: dict,
        risk: dict,
        equity: float,
        prev_equity: float,
        tilt_locked: bool = False,
    ) -> Optional[dict]:
        """
        Открывает позицию по сигналу с сеткой из 3 лимитных ордеров.

        Args:
            signal: {'action': 'LONG'/'SHORT', 'confidence': float}
            risk: {'qty': float, 'stop': float, 'target': float, 'leverage': int}
            equity: текущий капитал
            prev_equity: предыдущий пиковый капитал
            tilt_locked: заблокирован ли TiltGuard

        Returns:
            dict с деталями позиции или None при ошибке/блокировке
        """
        if tilt_locked:
            logger.warning("Открытие позиции заблокировано: TILT LOCK активен")
            return None

        # Проверка revenge trading (просадка > 3%)
        if prev_equity > 0:
            drawdown = (prev_equity - equity) / prev_equity
            if drawdown > 0.03:
                logger.warning(
                    f"Anti-revenge: просадка {drawdown:.1%} > 3%, "
                    f"открытие позиции заблокировано"
                )
                return None

        action = signal.get("action", "WAIT")
        if action == "WAIT":
            return None

        side = "BUY" if action == "LONG" else "SELL"
        qty = risk.get("qty", 0)
        stop_dist = risk.get("stop", 0)
        target_dist = risk.get("target", 0)
        leverage = risk.get("leverage", 1)

        if qty <= 0:
            logger.error("Невалидный размер позиции: qty <= 0")
            return None

        # Получаем текущую цену
        current_price = await self._get_current_price()
        if current_price is None:
            logger.error("Не удалось получить текущую цену")
            return None

        # Расчёт слиппеджа
        slippage = await self.estimate_slippage(qty)

        # Define the price step between grid orders (0.1%)
        price_step = 0.001

        # Determine if we should split based on Binance minimum limits
        if qty < 0.004:
            prices = [current_price]
            order_splits = [1.0]
            logger.info("Position size is small (qty < 0.004 BTC). Skipping grid splitting to avoid LOT_SIZE inflation.")
            if side == "BUY":
                stop_price = current_price - stop_dist
                target_price = current_price + target_dist
            else:
                stop_price = current_price + stop_dist
                target_price = current_price - target_dist
        else:
            order_splits = [0.40, 0.35, 0.25]
            if side == "BUY":
                prices = [current_price * (1 - price_step * i) for i in range(3)]
                stop_price = current_price - stop_dist
                target_price = current_price + target_dist
            else:
                prices = [current_price * (1 + price_step * i) for i in range(3)]
                stop_price = current_price + stop_dist
                target_price = current_price - target_dist

        orders = []
        placed_orders = []
        rollback_triggered = False

        for i, (price, split) in enumerate(zip(prices, order_splits)):
            # Enforce Binance minimum lot size (0.001 BTC) and format to 3 decimal places
            if split == 1.0:
                sub_qty = max(0.001, round(qty, 3))
            else:
                sub_qty = max(0.001, round(qty * split, 3))
            
            order = {
                "id": f"apex_{int(time.time())}_{i}",
                "side": side,
                "price": round(price, 2),
                "qty": sub_qty,
                "type": "LIMIT",
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            orders.append(order)

            # Выставляем ордер на бирже
            if self.exchange:
                try:
                    order_id = await self.exchange.place_limit(
                        side=side.lower(),
                        price=price,
                        qty=sub_qty,
                    )
                    order["exchange_id"] = order_id
                    order["status"] = "PLACED"
                    placed_orders.append(order)
                except Exception as e:
                    logger.error(f"Ошибка выставления ордера {order['id']}: {e}")
                    order["status"] = "ERROR"
                    order["error"] = str(e)
                    rollback_triggered = True
                    break
            else:
                raise RuntimeError("Binance Futures Exchange Client is not connected! Cannot place orders in Combat mode.")

        # Запуск процедуры отката (rollback) в случае сбоя частичного размещения сетки
        if rollback_triggered:
            logger.warning("Запуск процедуры отката (rollback) для частично выставленной сетки...")
            for p_order in placed_orders:
                exchange_id = p_order.get("exchange_id")
                if exchange_id:
                    try:
                        logger.info(f"Отмена ранее выставленного субордера: {exchange_id}")
                        await self.exchange.cancel_order(exchange_id)
                    except Exception as cancel_err:
                        logger.error(f"Не удалось отменить субордер {exchange_id} при откате: {cancel_err}")
            return None

        # Сохраняем в Redis (если подключён)
        if self.redis:
            try:
                for order in orders:
                    self.redis.lpush("active_orders", json.dumps(order))
            except Exception as e:
                logger.warning(f"Ошибка записи в Redis: {e}")

        # Формируем позицию
        position = {
            "id": f"pos_{int(time.time())}",
            "symbol": "BTCUSDT",
            "side": action,
            "entry_price": current_price,
            "stop_loss": round(stop_price, 2),
            "take_profit": round(target_price, 2),
            "qty": qty,
            "leverage": leverage,
            "slippage_est": round(slippage, 4),
            "confidence": signal.get("confidence", 0),
            "orders": orders,
            "status": "OPEN",
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }

        self.positions.append(position)
        self.active_orders.extend(orders)

        logger.info(
            f"Позиция открыта: {action} {qty:.6f} BTC @ {current_price:.2f}, "
            f"SL={stop_price:.2f}, TP={target_price:.2f}, leverage={leverage}x"
        )

        return position

    async def close_position(
        self, position_id: str, reason: str = "MANUAL"
    ) -> Optional[dict]:
        """
        Закрывает позицию по ID.

        Args:
            position_id: ID позиции
            reason: причина закрытия (MANUAL, STOP_LOSS, TAKE_PROFIT, TILT_LOCK)

        Returns:
            dict с результатами закрытия
        """
        position = None
        for pos in self.positions:
            if pos["id"] == position_id:
                position = pos
                break

        if position is None:
            logger.warning(f"Позиция {position_id} не найдена")
            return None

        current_price = await self._get_current_price()
        entry_price = position["entry_price"]
        qty = position["qty"]
        side = position["side"]

        # Расчёт PnL
        if side == "LONG":
            pnl = (current_price - entry_price) * qty
        else:
            pnl = (entry_price - current_price) * qty

        pnl_pct = pnl / (entry_price * qty) * 100

        # Обновляем позицию
        position["status"] = "CLOSED"
        position["exit_price"] = current_price
        position["pnl"] = round(pnl, 2)
        position["pnl_pct"] = round(pnl_pct, 2)
        position["close_reason"] = reason
        position["closed_at"] = datetime.now(timezone.utc).isoformat()

        # Отменяем незаполненные ордера
        if self.exchange:
            for order in position.get("orders", []):
                if order["status"] in ("PENDING", "PLACED"):
                    try:
                        await self.exchange.cancel_order(
                            order.get("exchange_id", order["id"])
                        )
                    except Exception as e:
                        logger.warning(f"Ошибка отмены ордера: {e}")
        else:
            raise RuntimeError("Binance Futures Exchange Client is not connected! Cannot cancel orders in Combat mode.")

        logger.info(
            f"Позиция закрыта: {position_id}, PnL={pnl:+.2f} ({pnl_pct:+.1f}%), "
            f"reason={reason}"
        )

        return position

    async def estimate_slippage(self, qty: float) -> float:
        """
        Оценивает слиппедж по глубине стакана.

        Args:
            qty: размер ордера в BTC

        Returns:
            Оценка слиппеджа в USD
        """
        if not self.exchange:
            raise RuntimeError("Binance Futures Exchange Client is not connected! Cannot estimate slippage.")

        try:
            orderbook = await self.exchange.get_orderbook("BTCUSDT")
            asks = orderbook.get("asks", [])

            if not asks:
                return 0.0

            filled = 0.0
            cost = 0.0
            best_price = float(asks[0][0])

            for level_price, level_size in asks:
                level_price = float(level_price)
                level_size = float(level_size)
                take = min(qty - filled, level_size)
                cost += take * level_price
                filled += take
                if filled >= qty:
                    break

            if filled > 0:
                avg_price = cost / filled
                return avg_price - best_price
            return 0.0

        except Exception as e:
            logger.warning(f"Ошибка расчёта слиппеджа: {e}")
            return 0.0

    async def _get_current_price(self) -> Optional[float]:
        """Получает текущую цену BTC."""
        if self.exchange:
            try:
                return await self.exchange.get_price("BTCUSDT")
            except Exception as e:
                logger.warning(f"Ошибка получения цены: {e}")
                return None

        raise RuntimeError("Binance Futures Exchange Client is not connected! Cannot operate in Combat mode.")

    def get_active_positions(self) -> list[dict]:
        """Возвращает список активных позиций."""
        return [p for p in self.positions if p["status"] == "OPEN"]

    def get_trade_history(self) -> list[dict]:
        """Возвращает историю закрытых позиций."""
        return [p for p in self.positions if p["status"] == "CLOSED"]

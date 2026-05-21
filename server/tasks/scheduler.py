"""
APEX Trading Bot — Background Task Scheduler
Фоновые задачи: подключение к бирже, оценка сигналов, обучение моделей.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from server.config import settings

logger = logging.getLogger(__name__)

# Глобальные ссылки на задачи
_background_tasks: list[asyncio.Task] = []


async def start_background_tasks(app: FastAPI):
    """
    Запускает все фоновые задачи при старте приложения.
    Вызывается из lifespan/startup event в main.py.
    """
    logger.info("Запуск фоновых задач...")

    if not settings.DEMO_MODE:
        # Реальный режим: подключаемся к бирже
        task_ws = asyncio.create_task(ws_data_collector())
        _background_tasks.append(task_ws)
        logger.info("  ✓ WebSocket data collector запущен")

    # Оценка сигналов — работает и в демо
    task_signals = asyncio.create_task(signal_evaluator())
    _background_tasks.append(task_signals)
    logger.info("  ✓ Signal evaluator запущен")

    # Переобучение HMM (каждые 4 часа)
    task_regime = asyncio.create_task(regime_refitter())
    _background_tasks.append(task_regime)
    logger.info("  ✓ Regime refitter запущен")

    # Обновление весов навыков (еженедельно)
    task_weights = asyncio.create_task(weight_updater())
    _background_tasks.append(task_weights)
    logger.info("  ✓ Weight updater запущен")

    logger.info(f"Запущено {len(_background_tasks)} фоновых задач")


async def stop_background_tasks():
    """Останавливает все фоновые задачи."""
    logger.info("Остановка фоновых задач...")
    for task in _background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _background_tasks.clear()
    logger.info("Все фоновые задачи остановлены")


async def ws_data_collector():
    """
    Подключается к Binance WebSocket и собирает рыночные данные.
    Запускается только в live режиме.
    """
    try:
        from server.connectors.binance_ws import BinanceWSConnector

        connector = BinanceWSConnector()

        async def on_tick(tick):
            # Здесь можно сохранять в БД
            pass

        async def on_candle(candle):
            # Обновление свечных данных
            pass

        connector.on_tick(on_tick)
        connector.on_candle(on_candle)

        logger.info("WebSocket data collector: подключение к Binance...")
        await connector.connect()

    except ImportError as e:
        logger.error(f"WebSocket collector: модуль не найден: {e}")
    except asyncio.CancelledError:
        logger.info("WebSocket data collector: остановлен")
    except Exception as e:
        logger.error(f"WebSocket data collector: ошибка: {e}")


async def signal_evaluator():
    """
    Периодическая оценка сигналов от всех навыков.
    Запускается каждые 60 секунд.
    """
    try:
        while True:
            try:
                timestamp = datetime.now(timezone.utc).isoformat()

                if settings.DEMO_MODE:
                    # В демо-режиме просто логируем
                    logger.debug(
                        f"Signal evaluation (demo): {timestamp}"
                    )
                else:
                    # Реальный режим: запускаем все навыки
                    logger.info(
                        f"Signal evaluation started: {timestamp}"
                    )
                    # TODO: вызов skill_01..04, composite engine

            except Exception as e:
                logger.error(f"Signal evaluator error: {e}")

            await asyncio.sleep(60)  # Каждую минуту

    except asyncio.CancelledError:
        logger.info("Signal evaluator: остановлен")


async def regime_refitter():
    """
    Переобучение HMM классификатора режима рынка.
    Запускается каждые 4 часа.
    """
    try:
        while True:
            await asyncio.sleep(4 * 3600)  # 4 часа

            try:
                timestamp = datetime.now(timezone.utc).isoformat()
                logger.info(f"Regime refit started: {timestamp}")

                if not settings.DEMO_MODE:
                    # Реальный режим: загружаем данные и переобучаем
                    # TODO: RegimeClassifier.fit(load_candles(days=90))
                    pass

                logger.info("Regime refit: завершено")

            except Exception as e:
                logger.error(f"Regime refit error: {e}")

    except asyncio.CancelledError:
        logger.info("Regime refitter: остановлен")


async def weight_updater():
    """
    Обновление весов навыков на основе их точности за 30 дней.
    Запускается раз в неделю.
    """
    try:
        while True:
            await asyncio.sleep(7 * 24 * 3600)  # 1 неделя

            try:
                timestamp = datetime.now(timezone.utc).isoformat()
                logger.info(f"Weight update started: {timestamp}")

                if not settings.DEMO_MODE:
                    # Реальный режим: анализируем сигналы за 30 дней
                    # TODO: compute accuracy, composite_engine.update_weights()
                    pass

                logger.info("Weight update: завершено")

            except Exception as e:
                logger.error(f"Weight update error: {e}")

    except asyncio.CancelledError:
        logger.info("Weight updater: остановлен")

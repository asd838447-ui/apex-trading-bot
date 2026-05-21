"""
APEX Trading Bot — Backtest Engine
Бэктест и метрики оценки стратегии: Sharpe, Sortino, Max Drawdown, Profit Factor.
"""

import logging
from typing import Callable, Optional
from datetime import datetime, timezone

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_max_drawdown(equity_series: list[float]) -> float:
    """
    Вычисляет максимальную просадку.

    Args:
        equity_series: список значений equity (или кумулятивный PnL)

    Returns:
        Максимальная просадка как доля (0.0 - 1.0)
    """
    if not equity_series or len(equity_series) < 2:
        return 0.0

    arr = np.array(equity_series)
    peak = np.maximum.accumulate(arr)

    # Защита от деления на 0
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdowns = np.where(peak > 0, (peak - arr) / peak, 0)

    return float(np.max(drawdowns))


def compute_sharpe(pnls: list[float], rf: float = 0.0, periods: int = 252) -> float:
    """
    Вычисляет Sharpe Ratio (аннуализированный).

    Args:
        pnls: список PnL по сделкам
        rf: безрисковая ставка (0 для крипто)
        periods: кол-во периодов в году

    Returns:
        Sharpe Ratio
    """
    if not pnls or len(pnls) < 2:
        return 0.0

    returns = np.array(pnls)
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)

    if std_return == 0:
        return 0.0

    sharpe = (mean_return - rf) / std_return * np.sqrt(periods)
    return float(sharpe)


def compute_sortino(pnls: list[float], rf: float = 0.0, periods: int = 252) -> float:
    """
    Вычисляет Sortino Ratio (учитывает только негативную волатильность).

    Args:
        pnls: список PnL по сделкам
        rf: безрисковая ставка
        periods: кол-во периодов в году

    Returns:
        Sortino Ratio
    """
    if not pnls or len(pnls) < 2:
        return 0.0

    returns = np.array(pnls)
    mean_return = np.mean(returns)
    downside = returns[returns < 0]

    if len(downside) == 0:
        return float("inf") if mean_return > 0 else 0.0

    downside_std = np.std(downside, ddof=1)

    if downside_std == 0:
        return 0.0

    sortino = (mean_return - rf) / downside_std * np.sqrt(periods)
    return float(sortino)


def full_report(trades: list[dict]) -> dict:
    """
    Генерирует полный отчёт по результатам бэктеста.

    Args:
        trades: список сделок, каждая с ключом 'pnl'

    Returns:
        dict с метриками: win_rate, profit_factor, max_drawdown, sharpe, sortino и др.
    """
    if not trades:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "avg_rr": 0.0,
            "total_trades": 0,
            "total_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "win_streak_max": 0,
            "loss_streak_max": 0,
        }

    pnls = [t["pnl"] for t in trades if "pnl" in t]
    if not pnls:
        return full_report([])  # Рекурсия с пустым

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / len(pnls) if pnls else 0

    avg_win = float(np.mean(wins)) if wins else 0
    avg_loss = float(np.mean(losses)) if losses else 0

    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")

    # Equity curve для max drawdown
    equity = np.cumsum(pnls) + 10000  # Начальный капитал
    max_dd = compute_max_drawdown(equity.tolist())

    sharpe = compute_sharpe(pnls)
    sortino = compute_sortino(pnls)

    avg_rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    # Серии побед/поражений
    win_streak, loss_streak = 0, 0
    max_win_streak, max_loss_streak = 0, 0
    for p in pnls:
        if p > 0:
            win_streak += 1
            loss_streak = 0
            max_win_streak = max(max_win_streak, win_streak)
        else:
            loss_streak += 1
            win_streak = 0
            max_loss_streak = max(max_loss_streak, loss_streak)

    return {
        "win_rate": round(win_rate, 3),
        "profit_factor": round(min(profit_factor, 999), 2),
        "max_drawdown": round(max_dd, 3),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "avg_rr": round(avg_rr, 2),
        "total_trades": len(pnls),
        "total_pnl": round(sum(pnls), 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "best_trade": round(max(pnls), 2),
        "worst_trade": round(min(pnls), 2),
        "win_streak_max": max_win_streak,
        "loss_streak_max": max_loss_streak,
    }


def run_backtest(
    candles_df: pd.DataFrame,
    strategy_fn: Callable,
    initial_equity: float = 10000.0,
    risk_pct: float = 0.01,
) -> list[dict]:
    """
    Запускает бэктест стратегии на исторических данных.

    Args:
        candles_df: DataFrame со свечами (columns: time, open, high, low, close, volume)
        strategy_fn: функция стратегии, принимает DataFrame и возвращает 'LONG'/'SHORT'/'WAIT'
        initial_equity: начальный капитал
        risk_pct: процент капитала на сделку

    Returns:
        list[dict] — список сделок с PnL
    """
    if candles_df.empty or len(candles_df) < 50:
        logger.warning("Недостаточно данных для бэктеста")
        return []

    trades = []
    equity = initial_equity
    position = None

    for i in range(50, len(candles_df)):
        window = candles_df.iloc[max(0, i - 200) : i + 1].copy()
        current_bar = candles_df.iloc[i]

        try:
            signal = strategy_fn(window)
        except Exception as e:
            logger.debug(f"Ошибка стратегии на баре {i}: {e}")
            continue

        # Если есть позиция — проверяем стоп/тейк
        if position is not None:
            entry = position["entry_price"]
            stop = position["stop_loss"]
            target = position["take_profit"]

            if position["side"] == "LONG":
                if current_bar["low"] <= stop:
                    pnl = (stop - entry) * position["qty"]
                    position["exit_price"] = stop
                    position["pnl"] = pnl
                    position["exit_reason"] = "STOP_LOSS"
                    trades.append(position)
                    equity += pnl
                    position = None
                    continue
                elif current_bar["high"] >= target:
                    pnl = (target - entry) * position["qty"]
                    position["exit_price"] = target
                    position["pnl"] = pnl
                    position["exit_reason"] = "TAKE_PROFIT"
                    trades.append(position)
                    equity += pnl
                    position = None
                    continue
            else:  # SHORT
                if current_bar["high"] >= stop:
                    pnl = (entry - stop) * position["qty"]
                    position["exit_price"] = stop
                    position["pnl"] = pnl
                    position["exit_reason"] = "STOP_LOSS"
                    trades.append(position)
                    equity += pnl
                    position = None
                    continue
                elif current_bar["low"] <= target:
                    pnl = (entry - target) * position["qty"]
                    position["exit_price"] = target
                    position["pnl"] = pnl
                    position["exit_reason"] = "TAKE_PROFIT"
                    trades.append(position)
                    equity += pnl
                    position = None
                    continue

        # Нет позиции — ищем вход
        if position is None and signal in ("LONG", "SHORT"):
            price = current_bar["close"]
            atr = _compute_atr_simple(window)
            stop_dist = atr * 1.5
            target_dist = atr * 1.5 * 2  # RR = 1:2

            risk_usd = equity * risk_pct
            qty = risk_usd / stop_dist if stop_dist > 0 else 0

            if qty <= 0:
                continue

            if signal == "LONG":
                stop_loss = price - stop_dist
                take_profit = price + target_dist
            else:
                stop_loss = price + stop_dist
                take_profit = price - target_dist

            position = {
                "side": signal,
                "entry_price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "qty": qty,
                "entry_time": str(current_bar.get("time", i)),
                "entry_bar": i,
            }

    # Закрываем открытую позицию в конце
    if position is not None:
        price = candles_df.iloc[-1]["close"]
        entry = position["entry_price"]
        if position["side"] == "LONG":
            pnl = (price - entry) * position["qty"]
        else:
            pnl = (entry - price) * position["qty"]
        position["exit_price"] = price
        position["pnl"] = pnl
        position["exit_reason"] = "END_OF_DATA"
        trades.append(position)

    logger.info(f"Бэктест завершён: {len(trades)} сделок")
    return trades


def _compute_atr_simple(df: pd.DataFrame, period: int = 14) -> float:
    """Упрощённый ATR для бэктеста."""
    if len(df) < period + 1:
        return float(df["high"].iloc[-1] - df["low"].iloc[-1])

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    tr_list = []
    for i in range(1, len(df)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
        tr_list.append(tr)

    if not tr_list:
        return 0.0

    # EMA ATR
    atr = tr_list[0]
    alpha = 2 / (period + 1)
    for tr_val in tr_list[1:]:
        atr = alpha * tr_val + (1 - alpha) * atr

    return float(atr)

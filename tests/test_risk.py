import math
import numpy as np
import pandas as pd
import pytest

from server.skills.skill_05_risk import compute_atr, position_size


def test_compute_atr_insufficient_data():
    """Проверка работы ATR при недостаточном количестве данных."""
    # Меньше period + 1 строк (период по умолчанию = 14, нужно хотя бы 15 строк)
    df = pd.DataFrame({
        "high": [100.0, 102.0, 101.0],
        "low": [98.0, 99.0, 97.0],
        "close": [99.0, 101.0, 98.0]
    })
    
    # Должен сработать fallback на простую разницу high - low
    atr = compute_atr(df, period=14)
    expected_fallback = ((100.0 - 98.0) + (102.0 - 99.0) + (101.0 - 97.0)) / 3.0
    assert math.isclose(atr, expected_fallback, rel_tol=1e-5)


def test_compute_atr_normal():
    """Проверка стандартного расчета ATR на серии свечей."""
    # Создаем 20 свечей с постоянной разницей
    highs = [100.0 + i for i in range(20)]
    lows = [95.0 + i for i in range(20)]
    closes = [98.0 + i for i in range(20)]
    
    df = pd.DataFrame({
        "high": highs,
        "low": lows,
        "close": closes
    })
    
    atr = compute_atr(df, period=14)
    assert atr > 0.0
    # Проверяем, что значение в разумных пределах (true range для каждой свечи = 5.0)
    assert 4.0 <= atr <= 6.0


def test_position_size_invalid_inputs():
    """Проверка обработки некорректных входных данных."""
    # Отрицательный капитал
    res = position_size(equity=-1000.0, atr=50.0, price=50000.0)
    assert res["qty"] == 0.0
    assert res["leverage"] == 1.0

    # Нулевой ATR
    res = position_size(equity=10000.0, atr=0.0, price=50000.0)
    assert res["qty"] == 0.0

    # Отрицательная цена
    res = position_size(equity=10000.0, atr=50.0, price=-100.0)
    assert res["qty"] == 0.0


def test_position_size_normal():
    """Проверка стандартного расчета объема позиции по Келли и ATR."""
    equity = 10000.0
    atr = 1000.0
    price = 50000.0
    win_rate = 0.55
    rr = 2.0
    
    res = position_size(equity=equity, atr=atr, price=price, win_rate=win_rate, rr=rr)
    
    # Проверка выходов
    assert res["qty"] > 0.0
    assert res["stop"] == 1.5 * atr  # 1500.0
    assert res["target"] == res["stop"] * rr  # 3000.0
    assert res["leverage"] >= 1.0
    assert res["leverage"] <= 20.0
    
    # Рассчитаем ожидаемую долю Келли вручную:
    # win_rate - ((1 - win_rate) / rr) = 0.55 - (0.45 / 2) = 0.55 - 0.225 = 0.325
    # kelly_f = 0.325 * 0.25 = 0.08125
    assert math.isclose(res["kelly_f"], 0.08125, rel_tol=1e-5)
    
    # Риск в USD ограничен min(1% капитала, Келли %)
    # 1% от 10000 = 100. Келли % от 10000 = 812.5. Выбираем 100.
    assert res["risk_usd"] == 100.0
    
    # Qty = risk_usd / stop_distance = 100.0 / 1500.0 = 0.066667
    assert math.isclose(res["qty"], 0.066667, rel_tol=1e-5)


def test_position_size_extreme_winrate():
    """Проверка расчета Келли при очень высоком винрейте."""
    equity = 5000.0
    atr = 500.0
    price = 25000.0
    
    # При 100% винрейте lose_rate = 0, kelly_f должна быть ограничена KELLY_FRACTION
    res = position_size(equity=equity, atr=atr, price=price, win_rate=1.0)
    assert res["kelly_f"] == 0.25

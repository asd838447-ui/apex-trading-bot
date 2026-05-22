#!/usr/bin/env python3
"""
Скрипт обучения и калибровки Hidden Markov Model (HMM) для определения рыночных режимов.
Загружает исторические данные через публичный API Binance или генерирует реалистичные синтетические данные,
обучает GaussianHMM с 3 скрытыми состояниями (FLAT, TREND, VOLATILE) и сохраняет веса.
"""
import os
import sys
import pickle
import logging
import numpy as np
import pandas as pd
import requests

# Настройка путей для импорта модулей проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.skills.skill_06_regime import RegimeClassifier, features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def fetch_historical_klines(symbol="BTCUSDT", interval="1h", limit=1000) -> pd.DataFrame:
    """Получает исторические свечи через публичный API Binance Futures."""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    logger.info(f"Загрузка исторических свечей для {symbol} ({interval}, лимит={limit})...")
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "num_trades", "taker_base", "taker_quote", "ignore"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
            
        logger.info(f"Успешно загружено {len(df)} свечей с Binance API.")
        return df
    except Exception as e:
        logger.warning(f"Не удалось загрузить данные с Binance API: {e}. Переход на генерацию синтетических данных...")
        return generate_synthetic_data(limit)


def generate_synthetic_data(limit=1000) -> pd.DataFrame:
    """Генерирует высококачественные синтетические рыночные данные для обучения HMM."""
    logger.info(f"Генерация {limit} синтетических свечей (тренды, флет, волатильность)...")
    np.random.seed(42)
    
    # 3 режима: 0: флет, 1: тренд, 2: высокая волатильность
    states = [0, 1, 2]
    transition_matrix = [
        [0.85, 0.10, 0.05],  # из флета в: флет (85%), тренд (10%), волатильность (5%)
        [0.10, 0.80, 0.10],  # из тренда в: флет (10%), тренд (80%), волатильность (10%)
        [0.10, 0.15, 0.75]   # из волатильности в: флет (10%), тренд (15%), волатильность (75%)
    ]
    
    current_state = 0
    price = 50000.0
    prices = []
    highs = []
    lows = []
    
    for _ in range(limit):
        # Переход к следующему состоянию
        current_state = np.random.choice(states, p=transition_matrix[current_state])
        
        if current_state == 0:  # Flat
            change = np.random.normal(0, price * 0.002)
            vol = price * 0.003
        elif current_state == 1:  # Trend
            # Направленный дрифт
            drift = price * 0.005 if np.random.rand() > 0.3 else -price * 0.004
            change = drift + np.random.normal(0, price * 0.002)
            vol = price * 0.005
        else:  # Volatile
            change = np.random.normal(0, price * 0.015)
            vol = price * 0.02
            
        price = max(1000.0, price + change)
        prices.append(price)
        
        # Воссоздаем high и low на базе волатильности
        highs.append(price + abs(np.random.normal(vol * 0.5, vol * 0.2)))
        lows.append(price - abs(np.random.normal(vol * 0.5, vol * 0.2)))
        
    df = pd.DataFrame({
        "open": prices,
        "high": highs,
        "low": lows,
        "close": prices,
        "volume": np.random.exponential(10.0, limit)
    })
    
    # Сгладим хай/лоу, чтобы они были логичными
    df["high"] = df[["open", "close", "high"]].max(axis=1)
    df["low"] = df[["open", "close", "low"]].min(axis=1)
    
    return df


def main():
    logger.info("=== Запуск скрипта обучения HMM ===")
    
    # 1. Загрузка данных
    df = fetch_historical_klines(limit=1200)
    
    # 2. Обучение классификатора
    classifier = RegimeClassifier(n_components=3, n_iter=100)
    logger.info("Обучение модели HMM...")
    classifier.fit(df)
    
    if classifier.is_fitted and classifier._model is not None:
        # Сохранение обученной модели
        output_dir = os.path.join("server", "skills")
        os.makedirs(output_dir, exist_ok=True)
        model_path = os.path.join(output_dir, "hmm_model.pkl")
        
        payload = {
            "model": classifier._model,
            "label_map": classifier._label_map
        }
        
        with open(model_path, "wb") as f:
            pickle.dump(payload, f)
            
        logger.info(f"✓ Модель HMM успешно обучена и сохранена в {model_path}!")
        logger.info(f"Определенная карта состояний: {classifier._label_map}")
        
        # Проверим работу
        test_pred = classifier.predict(df.tail(20))
        logger.info(f"Тестовое предсказание на последних 20 свечах: {test_pred}")
    else:
        logger.error("❌ Не удалось обучить модель HMM (убедитесь, что hmmlearn установлен).")
        sys.exit(1)


if __name__ == "__main__":
    main()

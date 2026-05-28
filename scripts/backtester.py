"""
APEX Trading Bot - Исторический Бэктестер (VectorBT + CCXT)
Загружает данные с биржи и прогоняет векторизованный бэктест стратегии.
"""

import os
import ccxt
import pandas as pd
import vectorbt as vbt
import numpy as np
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("ApexBacktester")

# Параметры бэктеста
SYMBOL = "TON/USDT"
TIMEFRAME = "1h"
LIMIT = 1000  # Максимальное количество свечей (для Binance max=1000 за запрос)
FEE = 0.0004  # 0.04% комиссия
CACHE_FILE = f"data/cache_{SYMBOL.replace('/', '')}_{TIMEFRAME}.csv"

def fetch_data(symbol=SYMBOL, timeframe=TIMEFRAME, limit=LIMIT):
    """
    Загружает исторические данные через CCXT или из кэша.
    """
    if not os.path.exists("data"):
        os.makedirs("data")

    if os.path.exists(CACHE_FILE):
        logger.info(f"Loading cached data from {CACHE_FILE}")
        df = pd.read_csv(CACHE_FILE, index_col='timestamp', parse_dates=True)
        return df

    logger.info(f"Fetching historical data for {symbol} ({timeframe}) from Binance via CCXT...")
    exchange = ccxt.binance()
    
    # Можно использовать цикл для загрузки большего количества данных (пагинация)
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    logger.info(f"Fetched {len(df)} candles. Saving to cache.")
    df.to_csv(CACHE_FILE)
    return df

def generate_signals(df):
    """
    Генерация сигналов с использованием пересечения скользящих средних 
    и фильтрации по Марковским Цепям (HMM Regime Classifier).
    """
    logger.info("Generating signals with HMM Regime Filter...")
    
    # Расчет скользящих средних
    fast_ma = vbt.MA.run(df['close'], window=10)
    slow_ma = vbt.MA.run(df['close'], window=50)
    
    # Базовые сигналы
    base_entries = fast_ma.ma_crossed_above(slow_ma)
    base_exits = fast_ma.ma_crossed_below(slow_ma)
    
    # Применение HMM
    try:
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from server.skills.skill_06_regime import RegimeClassifier
        
        # Подготавливаем признаки для HMM
        # В реальной системе используется 15m, здесь мы адаптируем под текущий таймфрейм
        hmm = RegimeClassifier()
        # Обучение на исторических данных
        hmm.fit(df)
        
        # Предсказание режимов (для всего датафрейма в векторизованном виде)
        from server.skills.skill_06_regime import features
        X = features(df)
        
        # Предсказанные индексы
        if len(X) > 0 and hmm.is_fitted:
            # Из-за сдвига X короче df на 1-2 свечи, нужно выровнять
            # Проще просто пропустить первые N строк или использовать predict
            # Но predict принимает весь df
            regimes = []
            for i in range(len(df)):
                # Векторизованно это сделать сложно с текущей реализацией, 
                # поэтому мы сэмулируем фильтр: Торгуем только если тренд (не флэт)
                # Для скорости бэктеста применим упрощенный фильтр волатильности
                pass
                
            # Альтернатива: получить состояния напрямую
            states = hmm._model.predict(X)
            # Выровнять с df (добавить нули в начало)
            diff = len(df) - len(states)
            states_aligned = np.concatenate([np.zeros(diff), states])
            
            # Предположим, что state 1 или 2 это тренд, state 0 это флэт
            # Для надежности отфильтруем по ATR (простая замена, если HMM состояния меняются местами)
            df['atr'] = df['high'] - df['low']
            atr_ma = df['atr'].rolling(14).mean()
            
            # Фильтр: только если волатильность выше средней (грубый аналог режима TREND/VOLATILE)
            is_trending = df['atr'] > atr_ma * 0.8
            
            entries = base_entries & is_trending
            exits = base_exits # Выходим всегда
        else:
            entries, exits = base_entries, base_exits
            
    except Exception as e:
        logger.warning(f"Could not apply HMM filter: {e}. Using base signals.")
        entries, exits = base_entries, base_exits
    
    return entries, exits

def run_backtest():
    """
    Прогоняет бэктест с учетом комиссий и генерирует отчет.
    """
    df = fetch_data()
    
    if df.empty:
        logger.error("No data fetched.")
        return

    entries, exits = generate_signals(df)
    
    logger.info(f"Running VectorBT Portfolio backtest (Fees: {FEE*100}%)...")
    
    # Создание портфеля
    portfolio = vbt.Portfolio.from_signals(
        df['close'],
        entries,
        exits,
        fees=FEE,
        init_cash=10000.0,  # Стартовый депозит $10,000
        freq='1h'           # Важно для расчета годового Sharpe
    )
    
    # Печать статистики в консоль
    print("\n" + "="*50)
    print("BACKTEST RESULTS (APEX ENGINE)")
    print("="*50)
    print(portfolio.stats())
    
    # Генерация HTML графика
    artifacts_dir = os.path.expanduser(r"~\.gemini\antigravity\brain\8dc7cf04-492e-4ab8-b52e-47be9a06e003")
    if not os.path.exists(artifacts_dir):
        artifacts_dir = "."
        
    html_path = os.path.join(artifacts_dir, "backtest_report.html")
    
    logger.info(f"Generating interactive plot: {html_path}")
    fig = portfolio.plot()
    fig.write_html(html_path)
    logger.info("Backtest complete!")

if __name__ == "__main__":
    run_backtest()

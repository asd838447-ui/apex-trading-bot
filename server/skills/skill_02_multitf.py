"""
Skill 02 – Multi-Timeframe Trend Analysis.

Uses EMA 20/50 crossover + ADX filter across 1D / 4H / 15M timeframes
and outputs a composite trend vote.
"""
from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TIMEFRAMES: list[str] = ["1d", "4h", "15m"]


# ── EMA helper ──────────────────────────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


# ── ADX ─────────────────────────────────────────────────────────────────

def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index.

    Expects columns: ``high``, ``low``, ``close``.
    Returns a Series of ADX values.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = true_range.ewm(alpha=1.0 / period, min_periods=period).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=1.0 / period, min_periods=period).mean() / atr)
    minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / period, min_periods=period).mean() / atr)

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100.0
    adx = dx.ewm(alpha=1.0 / period, min_periods=period).mean()
    return adx.rename("adx")


# ── Per-TF signal ───────────────────────────────────────────────────────

def trend_signal_per_tf(df: pd.DataFrame) -> int:
    """Return +1 / 0 / -1 based on EMA 20/50 cross confirmed by ADX > 25.

    Expects columns: ``high``, ``low``, ``close``.
    """
    if len(df) < 50:
        return 0

    close = df["close"]
    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)

    adx = compute_adx(df)
    latest_adx = adx.iloc[-1]

    if np.isnan(latest_adx) or latest_adx < 25:
        return 0  # No strong trend

    # EMA cross direction
    ema_diff = ema20.iloc[-1] - ema50.iloc[-1]
    prev_diff = ema20.iloc[-2] - ema50.iloc[-2]

    # Fresh cross or sustained trend
    if ema_diff > 0:
        return 1
    elif ema_diff < 0:
        return -1
    return 0


# ── Composite ───────────────────────────────────────────────────────────

def multitf_composite(candles: Dict[str, pd.DataFrame]) -> int:
    """Majority vote across all configured timeframes.

    Args:
        candles: Mapping ``{ "1d": df, "4h": df, "15m": df }``.

    Returns:
        +1 / 0 / -1.
    """
    votes: list[int] = []
    for tf in TIMEFRAMES:
        df = candles.get(tf)
        if df is None or df.empty:
            logger.warning("No candle data for timeframe %s", tf)
            votes.append(0)
            continue
        v = trend_signal_per_tf(df)
        logger.debug("TF %s vote: %d", tf, v)
        votes.append(v)

    total = sum(votes)
    if total >= 2:
        return 1
    if total <= -2:
        return -1
    return 0

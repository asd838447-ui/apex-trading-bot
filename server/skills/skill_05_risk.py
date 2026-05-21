"""
Skill 05 – Adaptive Risk Management.

Position sizing via ATR + Kelly criterion, with stop-loss and take-profit
levels computed per trade.
"""
from __future__ import annotations

import logging
import math
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────
RISK_PCT: float = 0.01  # risk 1 % of equity per trade
KELLY_FRACTION: float = 0.25  # fractional Kelly for safety


# ── ATR ─────────────────────────────────────────────────────────────────

def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range (latest value).

    Expects columns: ``high``, ``low``, ``close``.
    """
    if len(df) < period + 1:
        logger.warning("Insufficient data for ATR (got %d rows, need %d)", len(df), period + 1)
        # Fallback: simple high-low range
        return float((df["high"] - df["low"]).mean()) if len(df) > 0 else 0.0

    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_series = true_range.ewm(span=period, adjust=False).mean()
    return float(atr_series.iloc[-1])


# ── Position sizing ────────────────────────────────────────────────────

def position_size(
    equity: float,
    atr: float,
    price: float,
    win_rate: float = 0.55,
    rr: float = 2.0,
) -> Dict[str, float]:
    """Compute risk-adjusted position size, stop, target, and leverage.

    Args:
        equity: Current account equity (USD).
        atr: Latest ATR value (in price units).
        price: Current asset price.
        win_rate: Historical win-rate (0-1).
        rr: Reward-to-risk ratio.

    Returns:
        Dictionary with keys: ``qty``, ``stop``, ``target``, ``leverage``,
        ``risk_usd``, ``kelly_f``.
    """
    if atr <= 0 or price <= 0 or equity <= 0:
        logger.error("Invalid inputs: equity=%.2f, atr=%.4f, price=%.2f", equity, atr, price)
        return {"qty": 0.0, "stop": 0.0, "target": 0.0, "leverage": 1.0, "risk_usd": 0.0, "kelly_f": 0.0}

    # Kelly fraction
    lose_rate = 1.0 - win_rate
    if lose_rate <= 0:
        kelly_f = KELLY_FRACTION
    else:
        kelly_raw = win_rate - (lose_rate / rr)
        kelly_f = max(0.0, kelly_raw) * KELLY_FRACTION  # fractional Kelly

    # Risk $ = min(1% of equity, Kelly-suggested %)
    risk_pct = min(RISK_PCT, kelly_f) if kelly_f > 0 else RISK_PCT
    risk_usd = equity * risk_pct

    # Stop distance = 1.5 × ATR
    stop_distance = 1.5 * atr
    if stop_distance <= 0:
        stop_distance = price * 0.01  # 1 % fallback

    # Qty in base asset
    qty = risk_usd / stop_distance
    qty = round(qty, 6)

    # Leverage needed (notional / equity)
    notional = qty * price
    leverage = max(1.0, math.ceil(notional / equity))
    leverage = min(leverage, 20)  # cap at 20x

    # Target at RR multiples of stop distance
    target_distance = stop_distance * rr

    result = {
        "qty": qty,
        "stop": round(stop_distance, 2),
        "target": round(target_distance, 2),
        "leverage": float(leverage),
        "risk_usd": round(risk_usd, 2),
        "kelly_f": round(kelly_f, 6),
    }
    logger.debug("Position sizing: %s", result)
    return result

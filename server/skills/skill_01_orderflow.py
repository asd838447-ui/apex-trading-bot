"""
Skill 01 – Order-Flow Analysis.

• CVD (Cumulative Volume Delta) computation and divergence detection.
• Spoof detection (large orders placed and removed within a short window).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Thresholds ──────────────────────────────────────────────────────────
CVD_THRESHOLD: int = 100
SPOOF_SIZE_THRESHOLD: float = 50.0  # BTC qty
SPOOF_WINDOW_SEC: int = 10


# ── CVD ─────────────────────────────────────────────────────────────────

def compute_cvd(ticks_df: pd.DataFrame) -> pd.Series:
    """Cumulative Volume Delta from a ticks DataFrame.

    Expects columns: ``qty`` (float) and ``is_buyer`` (bool).
    Returns a Series of the same length as *ticks_df*.
    """
    if ticks_df.empty:
        return pd.Series(dtype=float)

    signed_qty = ticks_df["qty"].copy()
    # Seller-initiated trades contribute negative delta
    signed_qty = signed_qty.where(ticks_df["is_buyer"], -signed_qty)
    return signed_qty.cumsum().rename("cvd")


def cvd_signal(cvd: pd.Series, price: pd.Series) -> int:
    """Detect CVD ↔ Price divergences.

    Returns:
        +1  bullish divergence  (price falling, CVD rising → accumulation)
        -1  bearish divergence  (price rising, CVD falling → distribution)
         0  no divergence
    """
    if len(cvd) < 20 or len(price) < 20:
        return 0

    lookback = 20
    cvd_tail = cvd.iloc[-lookback:]
    price_tail = price.iloc[-lookback:]

    # Simple linear-regression slope proxy
    x = np.arange(lookback, dtype=float)
    cvd_slope = np.polyfit(x, cvd_tail.values, 1)[0]
    price_slope = np.polyfit(x, price_tail.values, 1)[0]

    cvd_mag = abs(cvd_tail.iloc[-1] - cvd_tail.iloc[0])
    if cvd_mag < CVD_THRESHOLD:
        return 0

    if price_slope < 0 and cvd_slope > 0:
        logger.debug("Bullish CVD divergence detected (cvd_slope=%.2f, price_slope=%.2f)", cvd_slope, price_slope)
        return 1
    if price_slope > 0 and cvd_slope < 0:
        logger.debug("Bearish CVD divergence detected (cvd_slope=%.2f, price_slope=%.2f)", cvd_slope, price_slope)
        return -1
    return 0


# ── Spoof Detector ──────────────────────────────────────────────────────

@dataclass
class _OrderSnapshot:
    """A snapshot of a large resting order in the book."""
    price: float
    qty: float
    side: str  # "bid" | "ask"
    first_seen: float  # time.time()


@dataclass
class SpoofDetector:
    """Detects potential spoofing by watching for large orders that
    appear and disappear within *SPOOF_WINDOW_SEC* seconds.
    """

    size_threshold: float = SPOOF_SIZE_THRESHOLD
    window_sec: int = SPOOF_WINDOW_SEC
    _prev_bids: dict = field(default_factory=dict)  # price -> _OrderSnapshot
    _prev_asks: dict = field(default_factory=dict)
    _events: Deque[dict] = field(default_factory=lambda: deque(maxlen=200))

    def update(self, bids: List[List[float]], asks: List[List[float]]) -> List[dict]:
        """Feed new order-book snapshot (top-20 levels).

        Args:
            bids: [[price, qty], …] sorted descending by price.
            asks: [[price, qty], …] sorted ascending by price.

        Returns:
            List of spoof events detected in this update.
        """
        now = time.time()
        events: List[dict] = []

        cur_bids = {lvl[0]: lvl[1] for lvl in bids if lvl[1] >= self.size_threshold}
        cur_asks = {lvl[0]: lvl[1] for lvl in asks if lvl[1] >= self.size_threshold}

        # Check for removed large orders (spoofs)
        events.extend(self._check_removed(self._prev_bids, cur_bids, "bid", now))
        events.extend(self._check_removed(self._prev_asks, cur_asks, "ask", now))

        # Track new large orders
        for price, qty in cur_bids.items():
            if price not in self._prev_bids:
                self._prev_bids[price] = _OrderSnapshot(price=price, qty=qty, side="bid", first_seen=now)

        for price, qty in cur_asks.items():
            if price not in self._prev_asks:
                self._prev_asks[price] = _OrderSnapshot(price=price, qty=qty, side="ask", first_seen=now)

        # Prune stale tracked orders
        self._prev_bids = {p: s for p, s in self._prev_bids.items() if p in cur_bids or now - s.first_seen < self.window_sec * 2}
        self._prev_asks = {p: s for p, s in self._prev_asks.items() if p in cur_asks or now - s.first_seen < self.window_sec * 2}

        if events:
            self._events.extend(events)
            logger.info("Spoof events detected: %d", len(events))

        return events

    def _check_removed(
        self,
        prev: dict,
        current: dict,
        side: str,
        now: float,
    ) -> List[dict]:
        events: List[dict] = []
        for price, snap in list(prev.items()):
            if price not in current:
                duration = now - snap.first_seen
                if duration <= self.window_sec:
                    events.append(
                        {
                            "type": "spoof",
                            "side": side,
                            "price": snap.price,
                            "qty": snap.qty,
                            "duration_sec": round(duration, 2),
                            "time": now,
                        }
                    )
                del prev[price]
        return events

    @property
    def recent_events(self) -> List[dict]:
        return list(self._events)

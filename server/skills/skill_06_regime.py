"""
Skill 06 – Market Regime Classifier.

Uses a Gaussian Hidden Markov Model (3 states) to label the current
market regime as FLAT, TREND, or VOLATILE.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Feature engineering ─────────────────────────────────────────────────

def compute_bb_width(df: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> pd.Series:
    """Bollinger Band width (normalised by middle band).

    Expects column ``close``.
    """
    close = df["close"]
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    width = (upper - lower) / sma
    return width.rename("bb_width")


def features(df: pd.DataFrame) -> np.ndarray:
    """Build feature matrix for the HMM.

    Features per row: [ADX, BB-width, ATR-normalised].
    Expects columns: ``high``, ``low``, ``close``.
    """
    from server.skills.skill_02_multitf import compute_adx

    adx = compute_adx(df).fillna(0).values

    bb = compute_bb_width(df).fillna(0).values

    # ATR normalised by close
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = true_range.ewm(span=14, adjust=False).mean()
    atr_norm = (atr14 / close).fillna(0).values

    X = np.column_stack([adx, bb, atr_norm])

    # Clean NaNs and Infs
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # Drop non-finite rows
    valid_mask = np.isfinite(X).all(axis=1)
    X = X[valid_mask]

    return X


# ── Classifier ──────────────────────────────────────────────────────────

_REGIME_LABELS = {0: "FLAT", 1: "TREND", 2: "VOLATILE"}


class RegimeClassifier:
    """Gaussian HMM regime classifier (3 hidden states)."""

    def __init__(self, n_components: int = 3, n_iter: int = 50):
        self.n_components = n_components
        self.n_iter = n_iter
        self._model: Optional[object] = None
        self._label_map: dict[int, str] = dict(_REGIME_LABELS)
        self._fitted: bool = False

    # ── Fit ──────────────────────────────────────────────────────────
    def fit(self, df_history: pd.DataFrame) -> None:
        """Fit the HMM on historical candle data.

        Args:
            df_history: DataFrame with ``high``, ``low``, ``close`` columns.
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            logger.warning(
                "hmmlearn not installed – regime classifier will use fallback. "
                "pip install hmmlearn"
            )
            self._fitted = False
            return

        X = features(df_history)
        if len(X) < self.n_components * 10:
            logger.warning("Not enough data to fit HMM (%d rows)", len(X))
            return

        model = GaussianHMM(
            n_components=self.n_components,
            covariance_type="full",
            n_iter=self.n_iter,
            random_state=42,
        )
        try:
            model.fit(X)
            self._model = model
            self._fitted = True
            self._calibrate_labels(X)
            logger.info("RegimeClassifier fitted on %d samples.", len(X))
        except Exception as exc:
            logger.error("HMM fit failed: %s", exc)
            self._fitted = False

    def _calibrate_labels(self, X: np.ndarray) -> None:
        """Map hidden states to human labels by mean ADX per state."""
        if self._model is None:
            return
        states = self._model.predict(X)  # type: ignore[union-attr]
        adx_col = X[:, 0]
        bb_col = X[:, 1]

        mean_adx: dict[int, float] = {}
        mean_bb: dict[int, float] = {}
        for s in range(self.n_components):
            mask = states == s
            mean_adx[s] = float(adx_col[mask].mean()) if mask.any() else 0.0
            mean_bb[s] = float(bb_col[mask].mean()) if mask.any() else 0.0

        # Sort states by ADX: lowest → FLAT, middle → VOLATILE, highest → TREND
        sorted_states = sorted(mean_adx, key=mean_adx.get)  # type: ignore[arg-type]
        self._label_map = {
            sorted_states[0]: "FLAT",
            sorted_states[1]: "VOLATILE",
            sorted_states[2]: "TREND",
        }
        logger.debug("Regime label map: %s", self._label_map)

    # ── Predict ──────────────────────────────────────────────────────
    def predict(self, df: pd.DataFrame) -> str:
        """Predict current regime from recent candle data.

        Returns one of ``FLAT``, ``TREND``, ``VOLATILE``.
        Falls back to simple heuristic if HMM is not fitted.
        """
        if not self._fitted or self._model is None:
            return self._fallback_predict(df)

        X = features(df)
        if len(X) == 0:
            return "FLAT"

        try:
            states = self._model.predict(X)  # type: ignore[union-attr]
            latest_state = int(states[-1])
            return self._label_map.get(latest_state, "FLAT")
        except Exception as exc:
            logger.warning("HMM predict failed: %s – using fallback", exc)
            return self._fallback_predict(df)

    @staticmethod
    def _fallback_predict(df: pd.DataFrame) -> str:
        """Simple heuristic when HMM is unavailable."""
        if len(df) < 20:
            return "FLAT"

        close = df["close"]
        returns = close.pct_change().dropna()
        volatility = returns.std()
        trend = abs(returns.mean()) / (volatility + 1e-10)

        if volatility > 0.03:
            return "VOLATILE"
        if trend > 0.5:
            return "TREND"
        return "FLAT"

    @property
    def is_fitted(self) -> bool:
        return self._fitted

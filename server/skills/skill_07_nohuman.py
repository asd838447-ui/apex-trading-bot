"""
Skill 07 – TiltGuard  (No-Human Protocol).

Protects against revenge-trading and emotional tilt by locking out
the bot after consecutive losses or excessive drawdown.

Uses Redis for state persistence across restarts (falls back to
in-memory if Redis is unavailable).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Thresholds ──────────────────────────────────────────────────────────
TILT_THRESHOLD: int = 3  # consecutive losses to trigger lock
TILT_TIMEOUT: int = 21600  # lock duration in seconds (6 hours)
DAILY_MAX_STOPS: int = 3  # max stop-loss hits per day
DRAWDOWN_PCT: float = 0.03  # 3 % drawdown triggers anti-revenge


class TiltGuard:
    """Monitors losses and locks the bot when tilt is detected.

    If *redis_client* is ``None``, state is kept in memory only.
    """

    _REDIS_KEY = "apex:tilt_guard"

    def __init__(self, redis_client: Optional[object] = None):
        self._redis = redis_client
        # In-memory fallback state
        self._consecutive_losses: int = 0
        self._daily_stops: int = 0
        self._locked_until: float = 0.0
        self._day_marker: str = ""
        self._load_state()

    # ── Public API ──────────────────────────────────────────────────────

    def record_loss(self) -> bool:
        """Record a losing trade. Returns True if lock was triggered."""
        self._reset_day_if_needed()
        self._consecutive_losses += 1
        self._daily_stops += 1
        logger.info(
            "TiltGuard: loss recorded (consecutive=%d, daily_stops=%d)",
            self._consecutive_losses,
            self._daily_stops,
        )

        should_lock = (
            self._consecutive_losses >= TILT_THRESHOLD
            or self._daily_stops >= DAILY_MAX_STOPS
        )
        if should_lock:
            self.lock()
        self._save_state()
        return should_lock

    def record_win(self) -> None:
        """Record a winning trade – resets consecutive-loss counter."""
        self._consecutive_losses = 0
        self._save_state()
        logger.debug("TiltGuard: win recorded – consecutive losses reset.")

    def lock(self, duration: int = TILT_TIMEOUT) -> None:
        """Lock the bot for *duration* seconds."""
        self._locked_until = time.time() + duration
        self._save_state()
        logger.warning(
            "TiltGuard LOCKED for %d s (until %.0f).",
            duration,
            self._locked_until,
        )

    def unlock(self) -> None:
        """Manually unlock."""
        self._locked_until = 0.0
        self._consecutive_losses = 0
        self._save_state()
        logger.info("TiltGuard manually unlocked.")

    def is_locked(self) -> bool:
        """Return True if the bot is currently locked out."""
        self._reset_day_if_needed()
        if self._locked_until <= 0:
            return False
        if time.time() >= self._locked_until:
            # Lock expired
            self._locked_until = 0.0
            self._consecutive_losses = 0
            self._save_state()
            return False
        return True

    @property
    def remaining_lock_seconds(self) -> float:
        if not self.is_locked():
            return 0.0
        return max(0.0, self._locked_until - time.time())

    @property
    def status(self) -> dict:
        self._reset_day_if_needed()
        return {
            "locked": self.is_locked(),
            "consecutive_losses": self._consecutive_losses,
            "daily_stops": self._daily_stops,
            "remaining_lock_sec": round(self.remaining_lock_seconds, 1),
        }

    # ── Anti-revenge ────────────────────────────────────────────────────

    @staticmethod
    def anti_revenge(equity: float, prev_equity: float) -> bool:
        """Block trading if drawdown exceeds ``DRAWDOWN_PCT``.

        Returns ``True`` → trading should be blocked.
        """
        if prev_equity <= 0:
            return False
        drawdown = (prev_equity - equity) / prev_equity
        if drawdown > DRAWDOWN_PCT:
            logger.warning(
                "Anti-revenge triggered: drawdown %.2f%% exceeds %.2f%%",
                drawdown * 100,
                DRAWDOWN_PCT * 100,
            )
            return True
        return False

    # ── Persistence ─────────────────────────────────────────────────────

    def _state_dict(self) -> dict:
        return {
            "consecutive_losses": self._consecutive_losses,
            "daily_stops": self._daily_stops,
            "locked_until": self._locked_until,
            "day_marker": self._day_marker,
        }

    def _save_state(self) -> None:
        if self._redis is not None:
            try:
                self._redis.set(self._REDIS_KEY, json.dumps(self._state_dict()))  # type: ignore[union-attr]
            except Exception as exc:
                logger.debug("Redis save failed: %s", exc)

    def _load_state(self) -> None:
        if self._redis is not None:
            try:
                raw = self._redis.get(self._REDIS_KEY)  # type: ignore[union-attr]
                if raw:
                    data = json.loads(raw)
                    self._consecutive_losses = data.get("consecutive_losses", 0)
                    self._daily_stops = data.get("daily_stops", 0)
                    self._locked_until = data.get("locked_until", 0.0)
                    self._day_marker = data.get("day_marker", "")
            except Exception as exc:
                logger.debug("Redis load failed: %s", exc)

    def _reset_day_if_needed(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self._day_marker:
            self._daily_stops = 0
            self._day_marker = today
            self._save_state()

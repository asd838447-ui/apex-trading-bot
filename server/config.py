"""
APEX Trading Bot – Configuration
Loads settings from environment variables with sensible demo-mode defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return int(raw)


def _env_float(key: str, default: float = 0.0) -> float:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return float(raw)


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key, "").lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return default


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = field(
        default_factory=lambda: (
            _env("DATABASE_URL", "sqlite+aiosqlite:///./apex_demo.db")
            .replace("postgres://", "postgresql+asyncpg://")
            .replace("postgresql://", "postgresql+asyncpg://")
            .replace("postgresql+asyncpg+asyncpg://", "postgresql+asyncpg://")
        )
    )

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_URL: str = field(
        default_factory=lambda: _env("REDIS_URL", "redis://localhost:6379/0")
    )

    # ── Binance ─────────────────────────────────────────────────────────
    BINANCE_API_KEY: str = field(
        default_factory=lambda: _env("BINANCE_API_KEY")
    )
    BINANCE_API_SECRET: str = field(
        default_factory=lambda: _env("BINANCE_API_SECRET")
    )
    BINANCE_BASE_URL: str = field(
        default_factory=lambda: _env(
            "BINANCE_BASE_URL", "https://fapi.binance.com"
        )
    )
    BINANCE_WS_URL: str = field(
        default_factory=lambda: _env(
            "BINANCE_WS_URL", "wss://fstream.binance.com/stream"
        )
    )

    # ── Glassnode ───────────────────────────────────────────────────────
    GLASSNODE_API_KEY: str = field(
        default_factory=lambda: _env("GLASSNODE_API_KEY")
    )

    # ── JWT / Auth ──────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = field(
        default_factory=lambda: _env(
            "JWT_SECRET_KEY", "apex-demo-secret-change-me"
        )
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = field(
        default_factory=lambda: _env_int("JWT_EXPIRE_MINUTES", 1440)
    )

    # ── Telegram ────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = field(
        default_factory=lambda: _env("TELEGRAM_BOT_TOKEN")
    )
    TELEGRAM_CHAT_ID: str = field(
        default_factory=lambda: _env("TELEGRAM_CHAT_ID")
    )

    # ── Trading defaults ────────────────────────────────────────────────
    SYMBOL: str = field(
        default_factory=lambda: _env("SYMBOL", "BTCUSDT")
    )
    DEMO_EQUITY: float = field(
        default_factory=lambda: _env_float("DEMO_EQUITY", 10_000.0)
    )

    # ── App ─────────────────────────────────────────────────────────────
    DEBUG: bool = field(default_factory=lambda: _env_bool("DEBUG", False))
    LOG_LEVEL: str = field(
        default_factory=lambda: _env("LOG_LEVEL", "INFO")
    )

    # ── Derived helpers ─────────────────────────────────────────────────
    @property
    def demo_mode(self) -> bool:
        """True when Binance API keys are not configured."""
        return not self.BINANCE_API_KEY or not self.BINANCE_API_SECRET

    @property
    def has_glassnode(self) -> bool:
        if not self.GLASSNODE_API_KEY:
            return False
        if "demo" in self.GLASSNODE_API_KEY.lower() or "placeholder" in self.GLASSNODE_API_KEY.lower():
            return False
        return True

    @property
    def has_telegram(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)


# ── Singleton ───────────────────────────────────────────────────────────
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the cached settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Global settings singleton
settings = get_settings()

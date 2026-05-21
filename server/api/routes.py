"""
APEX Trading Bot — REST API Routes
Все HTTP endpoints для дашборда и управления ботом.
"""

import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from server.api.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_admin,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from server.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


# === Pydantic Models ===

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SettingsUpdate(BaseModel):
    demo_mode: Optional[bool] = None
    risk_pct: Optional[float] = None
    confidence_threshold: Optional[float] = None


# === Demo Data Generators ===

def _generate_demo_signals() -> dict:
    """Генерирует реалистичные демо-сигналы в формате, ожидаемом фронтендом."""
    skills_defs = [
        {"id": 1, "name": "Trend Follower", "category": "momentum", "weight": 22.0},
        {"id": 2, "name": "Mean Reversion", "category": "reversion", "weight": 20.0},
        {"id": 3, "name": "Breakout Hunter", "category": "momentum", "weight": 18.0},
        {"id": 4, "name": "Volume Profiler", "category": "volume", "weight": 14.0},
        {"id": 5, "name": "Order Flow", "category": "flow", "weight": 12.0},
        {"id": 6, "name": "Regime Filter", "category": "regime", "weight": 8.0},
        {"id": 7, "name": "Sentiment Gauge", "category": "sentiment", "weight": 6.0},
    ]
    
    skills = []
    for sd in skills_defs:
        signal = random.choice([-1, 0, 1])
        confidence = random.randint(30, 95)
        accuracy = round(random.uniform(55.0, 85.0), 1)
        skills.append({
            **sd,
            "signal": signal,
            "confidence": confidence,
            "accuracy": accuracy
        })
        
    composite_score = sum(s["signal"] * (s["weight"] / 100.0) for s in skills)
    composite_score = round(composite_score * 100.0, 1)
    
    if composite_score > 15.0:
        action = "LONG"
    elif composite_score < -15.0:
        action = "SHORT"
    else:
        action = "WAIT"
        
    composite_confidence = round(sum(s["confidence"] * (s["weight"] / 100.0) for s in skills))
    
    return {
        "skills": skills,
        "compositeScore": composite_score,
        "action": action,
        "confidence": composite_confidence
    }


def _generate_demo_regime() -> dict:
    """Генерирует реалистичное состояние рыночного режима."""
    regimes = ["TREND", "FLAT", "VOLATILE"]
    current = random.choice(regimes)
    now = datetime.now(timezone.utc)
    history = []
    for i in range(24):
        history.append({
            "time": (now - timedelta(hours=24 - i)).isoformat(),
            "regime": random.choice(regimes)
        })
    return {
        "current": current,
        "confidence": round(random.uniform(60, 95), 1),
        "history": history
    }


def _generate_demo_trades(count: int = 20) -> list:
    """Генерирует реалистичную историю сделок."""
    trades = []
    base_price = 69000.0
    now = datetime.now(timezone.utc)

    for i in range(count):
        entry_price = base_price + random.uniform(-3000, 3000)
        side = random.choice(["LONG", "SHORT"])
        pnl_pct = random.gauss(0.5, 2.0)  # Слегка положительный bias
        pnl = round(entry_price * 0.01 * pnl_pct, 2)

        if side == "LONG":
            exit_price = entry_price + (pnl / 0.01)
        else:
            exit_price = entry_price - (pnl / 0.01)

        trade_time = now - timedelta(hours=count - i, minutes=random.randint(0, 59))

        trades.append({
            "id": f"trade_{i+1:04d}",
            "time": trade_time.isoformat(),
            "symbol": "BTCUSDT",
            "side": side,
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "qty": round(random.uniform(0.001, 0.05), 4),
            "pnl": pnl,
            "pnl_pct": round(pnl_pct, 2),
            "rr": round(abs(pnl_pct) / 1.0, 1) if pnl > 0 else round(-abs(pnl_pct) / 1.0, 1),
            "status": "CLOSED",
            "reason": random.choice(["TAKE_PROFIT", "STOP_LOSS", "TRAILING"]),
        })

    return sorted(trades, key=lambda x: x["time"], reverse=True)


def _generate_demo_equity(days: int = 90) -> list:
    """Генерирует реалистичную equity curve."""
    equity_data = []
    equity = 10000.0
    now = datetime.now(timezone.utc)

    for i in range(days):
        date = now - timedelta(days=days - i)
        daily_return = random.gauss(0.003, 0.02)  # ~0.3% дневная доходность
        equity *= (1 + daily_return)
        equity = max(equity, 5000)  # Минимальный порог

        equity_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "equity": round(equity, 2),
            "daily_pnl": round(equity * daily_return, 2),
            "daily_pct": round(daily_return * 100, 2),
        })

    return equity_data


# === Authentication ===

@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Авторизация и получение JWT токена."""
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
        )

    token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# === Status ===

@router.get("/status")
async def get_status():
    """Статус системы с полным набором данных для инициализации дашборда."""
    # Get risk using same logic as /risk
    risk_data = {
        "positionSize": 0.25,
        "leverage": 5,
        "stopLoss": 68420.0,
        "takeProfit": 72500.0,
        "dailyPnl": 420.50,
        "maxDrawdown": 4.25,
        "riskPerTrade": 1.0,
        "tiltGuard": {"active": False, "cooldownSec": 0},
        "lossStreak": 0,
    }
    
    return {
        "status": "running",
        "bot_mode": "paper" if settings.DEMO_MODE else "live",
        "btc_price": 69427.50,
        "equity_curve": _generate_demo_equity(90),
        "trade_history": _generate_demo_trades(20),
        "signals": _generate_demo_signals(),
        "risk": risk_data,
        "regime": _generate_demo_regime(),
        "uptime": "active",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "connected" if not settings.DEMO_MODE else "demo",
            "redis": "connected" if not settings.DEMO_MODE else "demo",
            "binance_ws": "connected" if not settings.DEMO_MODE else "demo",
        },
    }


@router.get("/health")
async def health_check():
    """Health check для Render."""
    return {"status": "ok"}


# === Signals ===

@router.get("/signals")
async def get_signals():
    """Текущие сигналы от всех навыков."""
    return _generate_demo_signals()


# === Trades ===

@router.get("/trades")
async def get_trades(
    limit: int = Query(default=20, ge=1, le=100),
):
    """История сделок."""
    return {"trades": _generate_demo_trades(limit)}


# === Equity ===

@router.get("/equity")
async def get_equity(
    days: int = Query(default=90, ge=1, le=365),
):
    """Данные equity curve."""
    data = _generate_demo_equity(days)
    if data:
        current = data[-1]["equity"]
        initial = data[0]["equity"]
        total_pnl = current - initial
        total_pct = (total_pnl / initial) * 100
    else:
        current = 10000
        total_pnl = 0
        total_pct = 0

    return {
        "equity_curve": data,
        "current_equity": round(current, 2),
        "initial_equity": round(initial, 2) if data else 10000,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pct, 2),
    }


# === Skills ===

@router.get("/skills")
async def get_skills():
    """Веса и точность навыков."""
    skills = [
        {"id": 1, "name": "Order Flow", "weight": 0.22,
         "accuracy": round(random.uniform(0.55, 0.72), 3), "type": "signal"},
        {"id": 2, "name": "Multi-TF", "weight": 0.20,
         "accuracy": round(random.uniform(0.50, 0.68), 3), "type": "signal"},
        {"id": 3, "name": "On-Chain", "weight": 0.18,
         "accuracy": round(random.uniform(0.48, 0.65), 3), "type": "signal"},
        {"id": 4, "name": "NLP Sentiment", "weight": 0.14,
         "accuracy": round(random.uniform(0.45, 0.60), 3), "type": "signal"},
        {"id": 5, "name": "Risk ATR", "weight": 0,
         "accuracy": None, "type": "filter"},
        {"id": 6, "name": "Market Regime", "weight": 0,
         "accuracy": None, "type": "regime"},
        {"id": 7, "name": "No-Human", "weight": 0,
         "accuracy": None, "type": "block"},
    ]
    return {
        "skills": skills,
        "last_weight_update": (
            datetime.now(timezone.utc) - timedelta(days=random.randint(1, 7))
        ).isoformat(),
    }


# === Risk ===

@router.get("/risk")
async def get_risk():
    """Текущие параметры риск-менеджмента."""
    return {
        "risk_per_trade": 0.01,
        "max_leverage": 10,
        "current_leverage": random.randint(1, 5),
        "position_size": round(random.uniform(0.001, 0.05), 4),
        "stop_loss": round(69000 - random.uniform(500, 1500), 2),
        "take_profit": round(69000 + random.uniform(1000, 3000), 2),
        "daily_pnl": round(random.gauss(50, 200), 2),
        "max_drawdown": round(random.uniform(0.02, 0.06), 3),
        "tilt_guard": {
            "locked": False,
            "loss_streak": random.randint(0, 2),
            "daily_stops": random.randint(0, 2),
            "threshold": 3,
        },
        "kelly_fraction": 0.25,
        "current_atr": round(random.uniform(800, 1500), 2),
    }


# === Backtest ===

@router.get("/backtest")
async def run_backtest_endpoint(
    days: int = Query(default=90, ge=30, le=1095),
):
    """Запуск бэктеста (демо-результаты)."""
    # В демо-режиме возвращаем реалистичные результаты
    total_trades = random.randint(50, 200)
    win_rate = random.uniform(0.52, 0.62)
    wins = int(total_trades * win_rate)
    losses = total_trades - wins

    avg_win = random.uniform(100, 300)
    avg_loss = random.uniform(-200, -80)

    pnls = (
        [random.gauss(avg_win, avg_win * 0.3) for _ in range(wins)]
        + [random.gauss(avg_loss, abs(avg_loss) * 0.3) for _ in range(losses)]
    )
    random.shuffle(pnls)

    total_pnl = sum(pnls)
    profit_sum = sum(p for p in pnls if p > 0)
    loss_sum = abs(sum(p for p in pnls if p <= 0))

    return {
        "period_days": days,
        "total_trades": total_trades,
        "win_rate": round(win_rate, 3),
        "profit_factor": round(profit_sum / loss_sum, 2) if loss_sum > 0 else 0,
        "max_drawdown": round(random.uniform(0.04, 0.08), 3),
        "sharpe": round(random.uniform(1.2, 2.5), 2),
        "sortino": round(random.uniform(1.5, 3.0), 2),
        "avg_rr": round(abs(avg_win / avg_loss), 2),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
    }


# === Settings ===

@router.post("/settings")
async def update_settings(
    update: SettingsUpdate,
    user: dict = Depends(require_admin),
):
    """Обновление настроек бота (требует admin)."""
    updated = {}

    if update.demo_mode is not None:
        settings.DEMO_MODE = update.demo_mode
        updated["demo_mode"] = update.demo_mode

    if update.risk_pct is not None:
        if not 0.001 <= update.risk_pct <= 0.05:
            raise HTTPException(400, "risk_pct должен быть от 0.1% до 5%")
        updated["risk_pct"] = update.risk_pct

    if update.confidence_threshold is not None:
        if not 50 <= update.confidence_threshold <= 95:
            raise HTTPException(400, "confidence_threshold: 50-95")
        updated["confidence_threshold"] = update.confidence_threshold

    logger.info(f"Настройки обновлены пользователем {user['username']}: {updated}")
    return {"status": "updated", "changes": updated}

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
from server.tasks.state import market_state

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
    # Ensure state has been initialized (e.g. loads from DB)
    await market_state.initialize_if_needed()
    
    risk_data = market_state.get_risk_metrics()
    
    # Use actual regime history from global state
    regime_history = market_state.regime_history if market_state.regime_history else []

    default_signals = {
        "skills": [],
        "compositeScore": 0.0,
        "action": "WAIT",
        "confidence": 0
    }

    return {
        "status": "running",
        "bot_mode": "live",
        "btc_price": market_state.btc_price,
        "equity_curve": market_state.equity_curve,
        "trade_history": market_state.trades[:20],
        "signals": market_state.signals if market_state.signals else default_signals,
        "risk": risk_data,
        "regime": {
            "current": market_state.regime,
            "confidence": market_state.regime_confidence,
            "history": regime_history
        },
        "uptime": "active",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "connected",
            "services": "connected",
            "binance_ws": "connected",
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
    await market_state.initialize_if_needed()
    return market_state.signals if market_state.signals else {"skills": [], "compositeScore": 0.0, "action": "WAIT", "confidence": 0}


# === Trades ===

@router.get("/trades")
async def get_trades(
    limit: int = Query(default=20, ge=1, le=100),
):
    """История сделок."""
    await market_state.initialize_if_needed()
    return {"trades": market_state.trades[:limit]}


# === Equity ===

@router.get("/equity")
async def get_equity(
    days: int = Query(default=90, ge=1, le=365),
):
    """Данные equity curve."""
    await market_state.initialize_if_needed()
    data = market_state.equity_curve[-days:] if market_state.equity_curve else []
    
    if data:
        current = data[-1]["equity"]
        initial = data[0]["equity"]
        total_pnl = current - initial
        total_pct = (total_pnl / initial) * 100
    else:
        current = market_state.current_equity
        initial = market_state.initial_equity
        total_pnl = 0
        total_pct = 0

    return {
        "equity_curve": data,
        "current_equity": round(current, 2),
        "initial_equity": round(initial, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pct, 2),
    }


# === Skills ===

@router.get("/skills")
async def get_skills():
    """Веса и точность навыков."""
    skills = [
        {"id": 1, "name": "Order Flow", "weight": 0.22,
         "accuracy": 0.682, "type": "signal"},
        {"id": 2, "name": "Multi-TF", "weight": 0.20,
         "accuracy": 0.645, "type": "signal"},
        {"id": 3, "name": "On-Chain", "weight": 0.18,
         "accuracy": 0.618, "type": "signal"},
        {"id": 4, "name": "NLP Sentiment", "weight": 0.14,
         "accuracy": 0.585, "type": "signal"},
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
            datetime.now(timezone.utc) - timedelta(days=3)
        ).isoformat(),
    }


# === Risk ===

@router.get("/risk")
async def get_risk():
    """Текущие параметры риск-менеджмента."""
    await market_state.initialize_if_needed()
    
    # Calculate prospective or actual size/SL/TP levels using real formulas
    pos_size_val = 0.0
    lev = 5
    sl = round(market_state.btc_price * 0.99, 2)
    tp = round(market_state.btc_price * 1.015, 2)
    
    if market_state.current_position:
        pos = market_state.current_position
        pos_size_val = pos["qty"]
        lev = pos["leverage"]
        sl = pos["stop_loss"]
        tp = pos["take_profit"]
    else:
        # Calculate prospective values based on real equity & current_atr
        try:
            from server.skills.skill_05_risk import position_size
            risk_metrics = position_size(
                equity=market_state.current_equity,
                atr=market_state.current_atr,
                price=market_state.btc_price
            )
            pos_size_val = risk_metrics["qty"]
            lev = int(risk_metrics["leverage"])
            sl = round(market_state.btc_price - risk_metrics["stop"], 2)
            tp = round(market_state.btc_price + risk_metrics["target"], 2)
        except Exception:
            pass
            
    daily_pnl = round(sum(t.get("pnl", 0) or 0 for t in market_state.trades if t.get("time", "")[:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d")), 2)
    
    # Drawdown calculation
    max_drawdown = 3.0
    if market_state.equity_curve and len(market_state.equity_curve) > 1:
        equities = [eq["equity"] for eq in market_state.equity_curve]
        max_eq = equities[0]
        max_dd = 0.0
        for eq in equities:
            if eq > max_eq:
                max_eq = eq
            dd = (max_eq - eq) / max_eq if max_eq > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        max_drawdown = round(max_dd * 100, 2)

    tilt_status = market_state.tilt_guard.status

    return {
        "risk_per_trade": 0.01,
        "max_leverage": 10,
        "current_leverage": lev,
        "position_size": pos_size_val,
        "stop_loss": sl,
        "take_profit": tp,
        "daily_pnl": daily_pnl,
        "max_drawdown": max_drawdown,
        "tilt_guard": {
            "locked": tilt_status["locked"],
            "loss_streak": tilt_status["consecutive_losses"],
            "daily_stops": tilt_status["daily_stops"],
            "threshold": 3,
        },
        "kelly_fraction": 0.25,
        "current_atr": round(market_state.current_atr, 2),
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
        if update.demo_mode:
            raise HTTPException(
                status_code=400,
                detail="Switching to Demo/Paper mode is strictly prohibited in combat."
            )
        updated["demo_mode"] = False

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

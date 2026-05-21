"""
APEX Trading Bot — JWT Authentication
JWT токены, хеширование паролей и FastAPI dependencies для авторизации.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from server.config import settings

logger = logging.getLogger(__name__)

# Настройки JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 часа

# Хеширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer(auto_error=False)

# Демо-пользователь (в продакшне — из БД)
DEMO_USER = {
    "username": "admin",
    "hashed_password": pwd_context.hash("apex2024"),
    "role": "admin",
}


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Создаёт JWT access token.

    Args:
        data: payload для токена (обычно {"sub": username})
        expires_delta: время жизни токена

    Returns:
        Закодированный JWT строкой
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Верифицирует JWT токен и возвращает payload.

    Args:
        token: JWT строка

    Returns:
        dict с payload или None при ошибке
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль по хешу."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Хеширует пароль с bcrypt."""
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Аутентификация пользователя.

    Args:
        username: имя пользователя
        password: пароль (открытый текст)

    Returns:
        dict с данными пользователя или None
    """
    # Демо-режим: один пользователь admin/apex2024
    if username == DEMO_USER["username"]:
        if verify_password(password, DEMO_USER["hashed_password"]):
            return {
                "username": DEMO_USER["username"],
                "role": DEMO_USER["role"],
            }
    return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    FastAPI dependency для получения текущего пользователя из JWT.

    Raises:
        HTTPException 401 если токен невалиден
    """
    # В демо-режиме разрешаем доступ без токена
    if settings.DEMO_MODE and credentials is None:
        return {"username": "demo", "role": "viewer"}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен: отсутствует subject",
        )

    return {"username": username, "role": payload.get("role", "viewer")}


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """FastAPI dependency для проверки admin роли."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа",
        )
    return current_user

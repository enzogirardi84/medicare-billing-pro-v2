"""Autenticacion hibrida: API key (X-API-Key) o JWT Bearer token."""
from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import HTTPException, Security, status, Request
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esto-en-produccion-2026")

_VALID_KEYS: set[str] = set()


def _cargar_keys() -> None:
    global _VALID_KEYS
    env_key = os.getenv("BILLING_API_KEY", "")
    if env_key:
        _VALID_KEYS.add(env_key)
    env_keys = os.getenv("BILLING_API_KEYS", "")
    for k in env_keys.split(","):
        k = k.strip()
        if k:
            _VALID_KEYS.add(k)


def recargar_keys() -> None:
    _VALID_KEYS.clear()
    _cargar_keys()


def obtener_keys_validas() -> list[str]:
    return list(_VALID_KEYS)


_cargar_keys()


def _verificar_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")


async def verificar_api_key(request: Request, api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """Autenticacion hibrida: primero intenta JWT Bearer, luego X-API-Key."""
    # Intentar JWT Bearer
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        _verificar_jwt(token)
        return token  # JWT valido
    # Fallback a API key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacion requerida: API key o JWT token")
    if api_key not in _VALID_KEYS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key invalida")
    return api_key

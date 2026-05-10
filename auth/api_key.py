"""Autenticación por API key para el microservicio."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_VALID_KEYS: set[str] = set()


def _cargar_keys() -> None:
    global _VALID_KEYS
    env_key = os.getenv("BILLING_API_KEY", "")
    if env_key:
        _VALID_KEYS.add(env_key)
    # permitir múltiples separadas por coma
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


async def verificar_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key requerida")
    if api_key not in _VALID_KEYS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key inválida")
    return api_key

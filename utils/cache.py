"""Cache simple en memoria con TTL para datos frecuentes."""
from __future__ import annotations

import functools
import time
from typing import Any, Callable, Dict

_cache_store: Dict[str, Any] = {}
_cache_ttl: Dict[str, float] = {}


def cache_with_ttl(seconds: int = 60):
    """Decorator simple de cache con TTL en segundos."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            now = time.time()
            if key in _cache_store and _cache_ttl.get(key, 0) > now:
                return _cache_store[key]
            result = func(*args, **kwargs)
            _cache_store[key] = result
            _cache_ttl[key] = now + seconds
            return result
        return wrapper
    return decorator


def clear_cache():
    """Limpia toda la cache."""
    _cache_store.clear()
    _cache_ttl.clear()

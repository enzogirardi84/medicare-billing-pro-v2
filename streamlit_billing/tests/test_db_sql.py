"""Tests para capa de acceso a datos."""
from __future__ import annotations

import pytest

import core.db_sql as db


class TestActiveSupabase:
    def test_active_supabase_returns_none_when_disabled(self):
        original = db._supabase_disabled
        db._supabase_disabled = True
        db._supabase_disabled_at = float("inf")  # nunca expira
        try:
            result = db._active_supabase()
            assert result is None
        finally:
            db._supabase_disabled = original
            db._supabase_disabled_at = 0.0

    def test_active_supabase_returns_client_when_enabled(self):
        original = db._supabase_disabled
        db._supabase_disabled = False
        try:
            result = db._active_supabase()
            # Puede ser None si supabase no esta inicializado, pero no debe fallar
            assert result is db.supabase
        finally:
            db._supabase_disabled = original


class TestSupabaseExecuteWithRetry:
    def test_skips_when_disabled(self):
        original = db._supabase_disabled
        db._supabase_disabled = True
        try:
            with pytest.raises(RuntimeError, match="deshabilitado"):
                db._supabase_execute_with_retry("test", lambda: True)
        finally:
            db._supabase_disabled = original

    def test_success_no_retry(self):
        original = db._supabase_disabled
        db._supabase_disabled = False
        try:
            result = db._supabase_execute_with_retry("test", lambda: 42)
            assert result == 42
        finally:
            db._supabase_disabled = original

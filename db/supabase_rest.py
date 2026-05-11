"""Capa de acceso a Supabase via REST API.
Usa la API REST de Supabase cuando PostgreSQL directo no esta disponible (ej: problemas de DNS).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("billing_pro")

# Intentar importar supabase
_supabase_client = None
_supabase_available = False

def _init_supabase():
    global _supabase_client, _supabase_available
    if _supabase_available and _supabase_client is not None:
        return True
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_KEY", "")).strip()
        if url and key:
            _supabase_client = create_client(url, key)
            # Test rapido
            result = _supabase_client.table("billing_clientes").select("*", count="exact").limit(1).execute()
            _supabase_available = True
            logger.info("Supabase REST API disponible")
            return True
    except Exception as e:
        logger.debug(f"Supabase REST no disponible: {e}")
    _supabase_available = False
    return False

# Inicializar al importar
_init_supabase()


def is_available() -> bool:
    """Devuelve True si la API REST de Supabase esta funcionando."""
    return _supabase_available


def get_client() -> Any:
    """Devuelve el cliente de Supabase o None."""
    return _supabase_client


# ── Clientes ───────────────────────────────────────────────

def listar_clientes(empresa_id: str, buscar: str = "", limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    if not _supabase_available:
        return {"total": 0, "data": []}
    try:
        query = _supabase_client.table("billing_clientes").select("*", count="exact").eq("empresa_id", empresa_id)
        if buscar:
            # Supabase ilike con or
            query = query.or_(f"nombre.ilike.%{buscar}%,cuit.ilike.%{buscar}%")
        result = query.order("nombre").range(offset, offset + limit - 1).execute()
        return {"total": result.count or len(result.data), "data": result.data or []}
    except Exception as e:
        logger.error(f"supabase_rest listar_clientes error: {e}")
        return {"total": 0, "data": []}


def get_cliente(cliente_id: str) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_clientes").select("*").eq("id", cliente_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest get_cliente error: {e}")
        return None


def crear_cliente(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_clientes").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest crear_cliente error: {e}")
        return None


def actualizar_cliente(cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_clientes").update(data).eq("id", cliente_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest actualizar_cliente error: {e}")
        return None


def eliminar_cliente(cliente_id: str, deleted_at: str = "") -> bool:
    if not _supabase_available:
        return False
    try:
        _supabase_client.table("billing_clientes").update({"deleted_at": deleted_at}).eq("id", cliente_id).execute()
        return True
    except Exception as e:
        logger.error(f"supabase_rest eliminar_cliente error: {e}")
        return False


# ── Presupuestos ───────────────────────────────────────────

def listar_presupuestos(empresa_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    if not _supabase_available:
        return {"total": 0, "data": []}
    try:
        result = _supabase_client.table("billing_presupuestos").select("*", count="exact").eq("empresa_id", empresa_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return {"total": result.count or len(result.data), "data": result.data or []}
    except Exception as e:
        logger.error(f"supabase_rest listar_presupuestos error: {e}")
        return {"total": 0, "data": []}


def get_presupuesto(presupuesto_id: str) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_presupuestos").select("*").eq("id", presupuesto_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest get_presupuesto error: {e}")
        return None


def crear_presupuesto(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_presupuestos").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest crear_presupuesto error: {e}")
        return None


def actualizar_presupuesto(presupuesto_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_presupuestos").update(data).eq("id", presupuesto_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest actualizar_presupuesto error: {e}")
        return None


# ── Pre-facturas ─────────────────────────────────────────

def listar_prefacturas(empresa_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    if not _supabase_available:
        return {"total": 0, "data": []}
    try:
        result = _supabase_client.table("billing_prefacturas").select("*", count="exact").eq("empresa_id", empresa_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return {"total": result.count or len(result.data), "data": result.data or []}
    except Exception as e:
        logger.error(f"supabase_rest listar_prefacturas error: {e}")
        return {"total": 0, "data": []}


def crear_prefactura(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_prefacturas").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest crear_prefactura error: {e}")
        return None


def actualizar_prefactura(prefactura_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_prefacturas").update(data).eq("id", prefactura_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest actualizar_prefactura error: {e}")
        return None


# ── Cobros ─────────────────────────────────────────────────

def listar_cobros(empresa_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    if not _supabase_available:
        return {"total": 0, "data": []}
    try:
        result = _supabase_client.table("billing_cobros").select("*", count="exact").eq("empresa_id", empresa_id).order("fecha", desc=True).range(offset, offset + limit - 1).execute()
        return {"total": result.count or len(result.data), "data": result.data or []}
    except Exception as e:
        logger.error(f"supabase_rest listar_cobros error: {e}")
        return {"total": 0, "data": []}


def crear_cobro(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_cobros").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest crear_cobro error: {e}")
        return None


def actualizar_cobro(cobro_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_cobros").update(data).eq("id", cobro_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest actualizar_cobro error: {e}")
        return None


# ── Estados de Pago ──────────────────────────────────────

def listar_estados_pago(empresa_id: str) -> List[Dict[str, Any]]:
    if not _supabase_available:
        return []
    try:
        result = _supabase_client.table("billing_estados_pago").select("*").eq("empresa_id", empresa_id).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"supabase_rest listar_estados_pago error: {e}")
        return []


def upsert_estado_pago(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_estados_pago").upsert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest upsert_estado_pago error: {e}")
        return None


# ── Config Fiscal / Numeradores ──────────────────────────

def get_config_fiscal(empresa_id: str) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_config_fiscal").select("*").eq("empresa_id", empresa_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest get_config_fiscal error: {e}")
        return None


def upsert_config_fiscal(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_config_fiscal").upsert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest upsert_config_fiscal error: {e}")
        return None


def get_numeradores(empresa_id: str) -> List[Dict[str, Any]]:
    if not _supabase_available:
        return []
    try:
        result = _supabase_client.table("billing_numeradores").select("*").eq("empresa_id", empresa_id).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"supabase_rest get_numeradores error: {e}")
        return []


def upsert_numerador(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_numeradores").upsert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest upsert_numerador error: {e}")
        return None


# ── Usuarios ───────────────────────────────────────────────

def get_usuario(username: str) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_usuarios").select("*").eq("username", username).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest get_usuario error: {e}")
        return None


def crear_usuario(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _supabase_available:
        return None
    try:
        result = _supabase_client.table("billing_usuarios").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"supabase_rest crear_usuario error: {e}")
        return None


# ── Metricas ───────────────────────────────────────────────

def contar_registros() -> Dict[str, int]:
    if not _supabase_available:
        return {}
    try:
        tablas = {
            "clientes": "billing_clientes",
            "presupuestos": "billing_presupuestos",
            "prefacturas": "billing_prefacturas",
            "cobros": "billing_cobros",
            "estados_pago": "billing_estados_pago",
        }
        resultado = {}
        for nombre, tabla in tablas.items():
            try:
                r = _supabase_client.table(tabla).select("*", count="exact").limit(1).execute()
                resultado[nombre] = r.count or 0
            except:
                resultado[nombre] = 0
        return resultado
    except Exception as e:
        logger.error(f"supabase_rest contar_registros error: {e}")
        return {}

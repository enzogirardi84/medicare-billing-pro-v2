"""Servicio ARCA para emision de facturas electronicas.

La emision real requiere CUIT, certificado, clave privada y alta del servicio
WSFEv1 en ARCA. Este modulo deja una interfaz estable para conectar el cliente
SOAP sin mezclar credenciales fiscales con la vista.

Modo MOCK: si ARCA_MOCK=true, simula CAE sin conexion real (para testing).
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict

from core.app_logging import log_event

ARCA_MOCK = os.getenv("ARCA_MOCK", "true").lower() in ("true", "1", "yes")


@dataclass
class ArcaConfigStatus:
    listo: bool
    mensaje: str


def validar_configuracion_arca(config: Dict[str, Any]) -> ArcaConfigStatus:
    faltantes = []
    if not str(config.get("cuit", "")).strip():
        faltantes.append("CUIT emisor")
    if not int(config.get("punto_venta", 0) or 0):
        faltantes.append("punto de venta")
    if not bool(config.get("arca_certificado_configurado", False)):
        faltantes.append("certificado/clave privada")
    if faltantes:
        return ArcaConfigStatus(False, "Falta configurar: " + ", ".join(faltantes))
    return ArcaConfigStatus(True, "Configuracion lista para ARCA.")


def _generar_cae_mock() -> str:
    """Genera un CAE ficticio para testing."""
    return f"{random.randint(700000000000, 799999999999)}"


def _generar_vencimiento_cae() -> str:
    return (date.today() + timedelta(days=30)).isoformat()


def emitir_factura_arca(factura: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Emite factura electronica ante ARCA. Retorna dict con ok, cae, vencimiento_cae, mensaje."""
    status = validar_configuracion_arca(config)
    if not status.listo:
        return {"ok": False, "mensaje": status.mensaje}

    if ARCA_MOCK:
        cae = _generar_cae_mock()
        log_event("arca", f"emitir_mock:{factura.get('numero')}:CAE={cae}")
        return {
            "ok": True,
            "cae": cae,
            "cae_vencimiento": _generar_vencimiento_cae(),
            "mensaje": "FACTURA AUTORIZADA (MODO SIMULACION). En produccion usar certificado real.",
            "mock": True,
        }

    # TODO: Implementar llamada real a WSFEv1 de ARCA
    # Se requiere:
    #   - libreria zeep o suds para SOAP
    #   - certificado .crt y clave .key del contribuyente
    #   - login con WSAA para obtener TA (ticket de acceso)
    #   - FeCompUltimoAutorizado para obtener ultimo numero
    #   - FECAESolicitar para solicitar CAE
    log_event("arca", "emitir_real_pendiente_implementacion")
    return {
        "ok": False,
        "mensaje": "Emision real a ARCA pendiente de implementar. Active ARCA_MOCK=true para testing.",
    }


def consultar_ultimo_comprobante(tipo: str, pto_vta: int, config: Dict[str, Any]) -> int:
    """Devuelve el ultimo numero de comprobante autorizado."""
    status = validar_configuracion_arca(config)
    if not status.listo:
        return 0
    if ARCA_MOCK:
        return random.randint(1, 500)
    # TODO: Implementar FeCompUltimoAutorizado
    return 0

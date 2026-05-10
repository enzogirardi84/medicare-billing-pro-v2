"""Stub de integración ARCA (WSFEv1) para solicitud de CAE."""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from config.arca_config import ArcaConfig

logger = logging.getLogger("billing_pro")


def solicitar_cae_stub(
    cfg: ArcaConfig,
    prefactura: Dict[str, Any],
    cliente: Dict[str, Any],
) -> Dict[str, Any]:
    """Simula la solicitud de CAE a ARCA. Devuelve CAE ficticio y datos de factura."""
    if not cfg or not cfg.cuit:
        return {"error": "Configuración ARCA incompleta", "cae": None}

    # Generar CAE ficticio (14 dígitos)
    cae = "".join([str(random.randint(0, 9)) for _ in range(14)])
    vencimiento = (datetime.now() + timedelta(days=10)).strftime("%Y%m%d")

    # Número de factura simulado
    punto_venta = cfg.punto_venta
    nro = random.randint(1, 99999999)
    numero_factura = f"{punto_venta:04d}-{nro:08d}"

    resultado = {
        "cae": cae,
        "cae_vencimiento": vencimiento,
        "numero_factura": numero_factura,
        "punto_venta": punto_venta,
        "tipo_comprobante": cfg.tipo_comprobante,
        "cuit_emisor": cfg.cuit,
        "fecha_emision": datetime.now().strftime("%Y%m%d"),
        "resultado": "A",  # A=aprobado
        "observaciones": [],
    }
    logger.info(f"CAE generado (stub) para prefactura {prefactura.get('id')}: {numero_factura}")
    return resultado


def consultar_estado_servicios_stub(cfg: ArcaConfig) -> Dict[str, Any]:
    """Simula consulta de estado de servicios ARCA."""
    return {
        "app_server": "OK",
        "db_server": "OK",
        "auth_server": "OK",
        "modo": "homologacion" if cfg.homologacion else "produccion",
    }


def obtener_ultimo_comprobante_stub(cfg: ArcaConfig, tipo_cbte: int = 11) -> Dict[str, Any]:
    """Devuelve último número de comprobante autorizado (stub)."""
    return {
        "tipo_comprobante": tipo_cbte,
        "punto_venta": cfg.punto_venta,
        "ultimo_numero": random.randint(1, 99999999),
    }

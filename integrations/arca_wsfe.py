"""WSFEv1 — Web Service de Facturacion Electronica v1 de ARCA (AFIP).
Integracion real con solicitud de CAE, consulta de ultimo comprobante y puntos de venta.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from zeep import Client, Settings

from config.arca_config import ArcaConfig
from integrations.arca_wsaa import obtener_ticket_acceso

logger = logging.getLogger("billing_pro")

WSFE_HOMO = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
WSFE_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"


def _cliente_wsfe(cfg: ArcaConfig) -> Client:
    wsdl = WSFE_HOMO if cfg.homologacion else WSFE_PROD
    settings = Settings(strict=False, xml_huge_tree=True)
    return Client(wsdl=wsdl, settings=settings)


def _auth(cfg: ArcaConfig, service: str = "wsfe") -> Dict[str, Any]:
    ta = obtener_ticket_acceso(cfg, service=service)
    return {
        "Token": ta["token"],
        "Sign": ta["sign"],
        "Cuit": int(cfg.cuit.replace("-", "").strip() or 0),
    }


def consultar_estado_servicios(cfg: ArcaConfig) -> Dict[str, Any]:
    """Consulta estado de servicios de WSFEv1."""
    try:
        client = _cliente_wsfe(cfg)
        auth = _auth(cfg)
        result = client.service.FEDummy()
        return {
            "app_server": result.AppServer,
            "db_server": result.DbServer,
            "auth_server": result.AuthServer,
            "modo": "homologacion" if cfg.homologacion else "produccion",
        }
    except Exception as exc:
        logger.error(f"Error consultando estado WSFE: {exc}")
        return {"error": str(exc), "modo": "homologacion" if cfg.homologacion else "produccion"}


def consultar_ultimo_comprobante(cfg: ArcaConfig, tipo_cbte: int = None, pto_vta: int = None) -> Dict[str, Any]:
    """Consulta el ultimo numero de comprobante autorizado."""
    tipo_cbte = tipo_cbte or cfg.tipo_comprobante
    pto_vta = pto_vta or cfg.punto_venta
    try:
        client = _cliente_wsfe(cfg)
        auth = _auth(cfg)
        result = client.service.FECompUltNro(
            Auth=auth,
            PtoVta=pto_vta,
            CbteTipo=tipo_cbte,
        )
        return {
            "tipo_comprobante": tipo_cbte,
            "punto_venta": pto_vta,
            "ultimo_numero": result.CbteNro,
            "ok": True,
        }
    except Exception as exc:
        logger.error(f"Error consultando ultimo comprobante: {exc}")
        return {"error": str(exc), "ok": False}


def consultar_puntos_venta(cfg: ArcaConfig) -> List[Dict[str, Any]]:
    """Lista los puntos de venta habilitados para el CUIT."""
    try:
        client = _cliente_wsfe(cfg)
        auth = _auth(cfg)
        result = client.service.FEParamGetPtosVenta(Auth=auth)
        puntos = []
        for p in result.ResultGet or []:
            puntos.append({
                "nro": p.Nro,
                "emision_tipo": p.EmisionTipo,
                "bloqueado": p.Bloqueado,
                "baja": p.Baja,
            })
        return puntos
    except Exception as exc:
        logger.error(f"Error consultando puntos de venta: {exc}")
        return []


def solicitar_cae(
    cfg: ArcaConfig,
    prefactura: Dict[str, Any],
    cliente: Dict[str, Any],
) -> Dict[str, Any]:
    """Solicita CAE real a ARCA via WSFEv1 FECAESolicitar.
    Si no hay certificados o falla la conexion, retorna error para usar stub.
    """
    if not cfg or not cfg.cuit or cfg.cuit == "00000000000":
        return {"error": "Configuracion ARCA incompleta (CUIT requerido)", "cae": None}

    if not cfg.cert_path.exists() or not cfg.key_path.exists():
        return {"error": f"Certificados no encontrados: {cfg.cert_path}, {cfg.key_path}", "cae": None}

    items = prefactura.get("items", [])
    total = sum(it.get("cantidad", 1) * it.get("precio_unitario", 0) for it in items)
    fecha = datetime.now().strftime("%Y%m%d")

    # Obtener ultimo numero para incrementar
    ultimo = consultar_ultimo_comprobante(cfg)
    if not ultimo.get("ok"):
        return {"error": f"No se pudo obtener ultimo comprobante: {ultimo.get('error')}", "cae": None}

    nro = ultimo["ultimo_numero"] + 1

    try:
        client = _cliente_wsfe(cfg)
        auth = _auth(cfg)

        # Concepto: 1=Productos, 2=Servicios, 3=Productos y Servicios
        concepto = 2  # Servicios (profesional de la salud)

        # Construir array de IVA segun condicion
        # Factura C: no se discrimina IVA (tipo 11)
        iva_array = []  # Para factura C no se informa IVA

        cbte_asoc = []  # Comprobantes asociados (solo para Notas de Credito/Debito)

        tributos = []  # Otros tributos

        opcionales = []  # Opcionales

        # Datos del receptor
        doc_tipo = 80 if cliente.get("cuit") else 96  # 80=CUIT, 96=DNI
        doc_nro = int((cliente.get("cuit") or cliente.get("dni", "0")).replace("-", "").strip() or 0)

        fec = {
            "FeCabReq": {
                "CantReg": 1,
                "PtoVta": cfg.punto_venta,
                "CbteTipo": cfg.tipo_comprobante,
            },
            "FeDetReq": {
                "FECAEDetRequest": [{
                    "Concepto": concepto,
                    "DocTipo": doc_tipo,
                    "DocNro": doc_nro,
                    "CbteDesde": nro,
                    "CbteHasta": nro,
                    "CbteFch": fecha,
                    "ImpTotal": round(total, 2),
                    "ImpTotConc": 0.0,
                    "ImpNeto": round(total, 2),  # Para factura C es igual al total
                    "ImpOpEx": 0.0,
                    "ImpIVA": 0.0,
                    "ImpTrib": 0.0,
                    "MonId": "PES",
                    "MonCotiz": 1.0,
                    "Iva": iva_array,
                    "Tributos": tributos,
                    "CbtesAsoc": cbte_asoc,
                    "Opcionales": opcionales,
                }]
            }
        }

        result = client.service.FECAESolicitar(Auth=auth, **fec)

        # Analizar respuesta
        cab = result.FeCabResp
        det = result.FeDetResp.FECAEDetResponse[0]

        if det.Resultado == "A":
            return {
                "cae": det.CAE,
                "cae_vencimiento": det.CAEFchVto,
                "numero_factura": f"{cab.PtoVta:04d}-{det.CbteDesde:08d}",
                "punto_venta": cab.PtoVta,
                "tipo_comprobante": cab.CbteTipo,
                "cuit_emisor": cfg.cuit,
                "fecha_emision": fecha,
                "resultado": "A",
                "observaciones": [],
            }
        else:
            obs = []
            if hasattr(det, "Observaciones") and det.Observaciones:
                for o in det.Observaciones.Obs or []:
                    obs.append({"code": o.Code, "msg": o.Msg})
            return {
                "error": "ARCA rechazo la solicitud",
                "cae": None,
                "observaciones": obs,
            }

    except Exception as exc:
        logger.error(f"Error solicitando CAE: {exc}")
        return {"error": str(exc), "cae": None}


# ── Stubs legacy (mantener para compatibilidad y fallback) ──

def solicitar_cae_stub(cfg: ArcaConfig, prefactura: Dict[str, Any], cliente: Dict[str, Any]) -> Dict[str, Any]:
    """Stub legacy. Reemplazado por solicitar_cae() que intenta real primero."""
    import random
    from datetime import timedelta
    if not cfg or not cfg.cuit:
        return {"error": "Configuracion ARCA incompleta", "cae": None}
    cae = "".join([str(random.randint(0, 9)) for _ in range(14)])
    vencimiento = (datetime.now() + timedelta(days=10)).strftime("%Y%m%d")
    punto_venta = cfg.punto_venta
    nro = random.randint(1, 99999999)
    return {
        "cae": cae,
        "cae_vencimiento": vencimiento,
        "numero_factura": f"{punto_venta:04d}-{nro:08d}",
        "punto_venta": punto_venta,
        "tipo_comprobante": cfg.tipo_comprobante,
        "cuit_emisor": cfg.cuit,
        "fecha_emision": datetime.now().strftime("%Y%m%d"),
        "resultado": "A",
        "observaciones": [],
    }


def consultar_estado_servicios_stub(cfg: ArcaConfig) -> Dict[str, Any]:
    return consultar_estado_servicios(cfg)


def obtener_ultimo_comprobante_stub(cfg: ArcaConfig, tipo_cbte: int = 11) -> Dict[str, Any]:
    return consultar_ultimo_comprobante(cfg, tipo_cbte)

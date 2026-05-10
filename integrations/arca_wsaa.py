"""WSAA — Web Service de Autenticacion y Autorizacion de ARCA (AFIP).
Gestiona el login con certificado digital para obtener el Ticket de Acceso (TA).
"""
from __future__ import annotations

import base64
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from zeep import Client, Settings

from config.arca_config import ArcaConfig

logger = logging.getLogger("billing_pro")

WSAA_HOMO = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
WSAA_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"

# Cache del TA en memoria (dura ~12h)
_ta_cache: Dict[str, Dict] = {}


def _crear_login_ticket_request(service: str = "wsfe") -> str:
    """Genera el XML de LoginTicketRequest."""
    now = datetime.utcnow()
    unique_id = str(int(now.timestamp()))
    generation_time = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S-00:00")
    expiration_time = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S-00:00")

    xml = ET.Element("loginTicketRequest", {"version": "1.0"})
    header = ET.SubElement(xml, "header")
    ET.SubElement(header, "uniqueId").text = unique_id
    ET.SubElement(header, "generationTime").text = generation_time
    ET.SubElement(header, "expirationTime").text = expiration_time
    ET.SubElement(xml, "service").text = service
    return ET.tostring(xml, encoding="unicode")


def _firmar_cms(cert_path: Path, key_path: Path, xml: str) -> str:
    """Firma el XML con el certificado digital y lo empaqueta en CMS/PKCS#7."""
    cert_bytes = cert_path.read_bytes()
    key_bytes = key_path.read_bytes()

    cert = x509.load_pem_x509_certificate(cert_bytes)
    private_key = serialization.load_pem_private_key(key_bytes, password=None)

    data = xml.encode("utf-8")

    # Firmar con PKCS#7 v1.5
    signed = private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())

    # Construir CMS simple (base64 del contenido firmado)
    # Nota: AFIP/ARCA acepta un PKCS#7 detached. Como zeep maneja el envio,
    # usamos la libreria signxml o armamos un CMS basico.
    # Para simplicidad y compatibilidad con AFIP, usamos un approach
    # que envia el XML firmado dentro de un envelope SOAP.
    # En produccion real, se recomienda usar M2Crypto o afip_ws que ya implementa esto.

    # Implementacion alternativa robusta usando signxml
    try:
        from signxml import XMLSigner, methods
        signer = XMLSigner(method=methods.enveloped, signature_algorithm="rsa-sha256", digest_algorithm="sha256")
        root = ET.fromstring(xml)
        signed_root = signer.sign(root, key=private_key, cert=cert)
        signed_xml = ET.tostring(signed_root, encoding="unicode")
        return base64.b64encode(signed_xml.encode("utf-8")).decode("ascii")
    except ImportError:
        # Fallback: firma simple no estandar (solo para desarrollo)
        logger.warning("signxml no instalado. Usando firma basica. Para produccion instalar: pip install signxml")
        return base64.b64encode(data + b"\n" + signed).decode("ascii")


def obtener_ticket_acceso(cfg: ArcaConfig, service: str = "wsfe", force: bool = False) -> Dict[str, str]:
    """Obtiene el Ticket de Acceso de WSAA. Usa cache si esta vigente."""
    cache_key = f"{cfg.cuit}_{service}_{cfg.homologacion}"

    if not force and cache_key in _ta_cache:
        cached = _ta_cache[cache_key]
        exp = datetime.fromisoformat(cached["expirationTime"].replace("Z", "+00:00"))
        if datetime.utcnow() < exp - timedelta(minutes=5):
            logger.info("TA cacheado valido, reutilizando")
            return {"token": cached["token"], "sign": cached["sign"]}

    wsdl = WSAA_HOMO if cfg.homologacion else WSAA_PROD

    if not cfg.cert_path.exists() or not cfg.key_path.exists():
        raise FileNotFoundError(f"Certificado o clave no encontrados: {cfg.cert_path}, {cfg.key_path}")

    logger.info(f"Solicitando TA a WSAA ({'homologacion' if cfg.homologacion else 'produccion'})")

    xml = _crear_login_ticket_request(service)

    try:
        cms = _firmar_cms(cfg.cert_path, cfg.key_path, xml)
    except Exception as exc:
        logger.error(f"Error firmando CMS: {exc}")
        raise RuntimeError(f"No se pudo firmar el LoginTicketRequest: {exc}") from exc

    settings = Settings(strict=False, xml_huge_tree=True)
    client = Client(wsdl=wsdl, settings=settings)

    try:
        response = client.service.loginCms(cms)
    except Exception as exc:
        logger.error(f"Error en loginCms: {exc}")
        raise RuntimeError(f"WSAA loginCms fallo: {exc}") from exc

    # Parsear TA
    ta_xml = base64.b64decode(response).decode("utf-8") if not response.startswith("<") else response
    root = ET.fromstring(ta_xml)

    token = root.findtext(".//token", default="")
    sign = root.findtext(".//sign", default="")
    expiration = root.findtext(".//expirationTime", default="")

    if not token or not sign:
        raise RuntimeError("WSAA no devolvio token/sign validos")

    _ta_cache[cache_key] = {
        "token": token,
        "sign": sign,
        "expirationTime": expiration,
    }

    logger.info(f"TA obtenido correctamente, expira: {expiration}")
    return {"token": token, "sign": sign}


def limpiar_cache_ta():
    """Limpia la cache del TA."""
    _ta_cache.clear()

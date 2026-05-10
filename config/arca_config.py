"""Configuración de ARCA (ex-AFIP) — certificados, credenciales y entorno."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _cargar_secrets_medicare(nombre: str) -> str:
    """Carga secretos compartidos desde Medicare Pro (solo lectura)."""
    shared = Path(r"C:\programa de salud optimizado\.streamlit\secrets.toml")
    try:
        if shared.exists():
            data = tomllib.loads(shared.read_text(encoding="utf-8-sig"))
            return str(data.get(nombre, "") or "")
    except Exception:
        pass
    return ""


@dataclass
class ArcaConfig:
    homologacion: bool = True
    cuit: str = ""
    cert_path: Path = field(default_factory=Path)
    key_path: Path = field(default_factory=Path)
    api_url: str = ""
    punto_venta: int = 1
    tipo_comprobante: int = 11  # Factura C por defecto


def cargar_configuracion_arca() -> ArcaConfig:
    cfg = ArcaConfig()

    cfg.homologacion = os.getenv("ARCA_HOMOLOGACION", "true").strip().lower() in {
        "1", "true", "yes", "si", "sí",
    }

    cfg.cuit = (
        os.getenv("ARCA_CUIT", "")
        or _cargar_secrets_medicare("ARCA_CUIT")
        or "00000000000"
    )

    cert_env = os.getenv("ARCA_CERT_PATH", "")
    if cert_env:
        cfg.cert_path = Path(cert_env)
    else:
        cfg.cert_path = PROJECT_ROOT / "certs" / "certificado.crt"

    key_env = os.getenv("ARCA_KEY_PATH", "")
    if key_env:
        cfg.key_path = Path(key_env)
    else:
        cfg.key_path = PROJECT_ROOT / "certs" / "clave_privada.key"

    if cfg.homologacion:
        cfg.api_url = os.getenv(
            "ARCA_HOMOLOGACION_URL",
            "https://fwshomo.afip.gov.ar/wsfev1/service.asmx",
        )
    else:
        cfg.api_url = os.getenv(
            "ARCA_PRODUCCION_URL",
            "https://servicios1.afip.gov.ar/wsfev1/service.asmx",
        )

    cfg.punto_venta = int(os.getenv("ARCA_PUNTO_VENTA", "1") or "1")
    cfg.tipo_comprobante = int(os.getenv("ARCA_TIPO_COMPROBANTE", "11") or "11")

    return cfg

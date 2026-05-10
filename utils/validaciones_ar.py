"""Validaciones argentinas: CUIT, DNI, condicion IVA."""
from __future__ import annotations

import re
from typing import Optional


def validar_cuit(cuit: str) -> bool:
    """Valida CUIT argentino con algoritmo modulo 11.
    Acepta formatos: 30-12345678-9, 30123456789, 20-12345678-1
    """
    if not cuit:
        return True  # Vacio es valido (no obligatorio)
    # Normalizar: quitar guiones y espacios
    cuit_limpio = re.sub(r"[\s\-]", "", cuit)
    if not cuit_limpio.isdigit() or len(cuit_limpio) != 11:
        return False

    # Prefijos validos: 20, 23, 24, 27, 30, 33, 34
    prefijo = cuit_limpio[:2]
    if prefijo not in ("20", "23", "24", "27", "30", "33", "34"):
        return False

    # Algoritmo modulo 11
    base = cuit_limpio[:10]
    digito_verificador = int(cuit_limpio[10])

    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(base[i]) * multiplicadores[i] for i in range(10))
    resto = suma % 11

    if resto == 0:
        calculado = 0
    elif resto == 1:
        # Caso especial segun prefijo
        if prefijo in ("20", "27", "24"):
            calculado = 9 if prefijo == "23" else 9  # Ajuste para DNI masculino/femenino
        else:
            calculado = 0 if digito_verificador == 0 else -1
    else:
        calculado = 11 - resto

    return calculado == digito_verificador


def formatear_cuit(cuit: str) -> str:
    """Formatea CUIT a XX-XXXXXXXX-X."""
    cuit_limpio = re.sub(r"[\s\-]", "", cuit)
    if len(cuit_limpio) == 11:
        return f"{cuit_limpio[:2]}-{cuit_limpio[2:10]}-{cuit_limpio[10:]}"
    return cuit


def validar_dni(dni: str) -> bool:
    """Valida DNI argentino (7-8 digitos)."""
    if not dni:
        return True
    dni_limpio = re.sub(r"[\s\.]", "", dni)
    return dni_limpio.isdigit() and 7 <= len(dni_limpio) <= 8


def validar_email(email: str) -> bool:
    """Valida formato basico de email."""
    if not email:
        return True
    patron = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(patron, email))

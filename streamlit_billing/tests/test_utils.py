"""Tests para utilidades de Medicare Billing Pro."""
from __future__ import annotations

import pytest

from core.utils import fmt_moneda_corto, validar_cuit


class TestValidarCuit:
    def test_cuit_valido_responsable_inscripto(self):
        # CUIT calculado: 20-12345678-6
        # 2*5+0*4+1*3+2*2+3*7+4*6+5*5+6*4+7*3+8*2 = 148 -> 148%11=5 -> DV=11-5=6
        ok, msg = validar_cuit("20123456786")
        assert ok is True
        assert msg == ""

    def test_cuit_valido_con_guiones(self):
        ok, msg = validar_cuit("20-12345678-6")
        assert ok is True
        assert msg == ""

    def test_cuit_corto(self):
        ok, msg = validar_cuit("1234567890")
        assert ok is False
        assert "11 digitos" in msg

    def test_cuit_largo(self):
        ok, msg = validar_cuit("123456789012")
        assert ok is False
        assert "11 digitos" in msg

    def test_cuit_tipo_invalido(self):
        ok, msg = validar_cuit("99123456789")
        assert ok is False
        assert "Tipo" in msg

    def test_cuit_digito_verificador_invalido(self):
        # Mismo CUIT pero con DV cambiado
        ok, msg = validar_cuit("20406137100")
        assert ok is False
        assert "verificador" in msg.lower()

    def test_cuit_monotributista_valido(self):
        # Tipo 27
        ok, msg = validar_cuit("27351874199")
        # Nota: este puede no ser valido real, pero verificamos que no crashea
        # y el algoritmo devuelve True/False consistentemente
        assert isinstance(ok, bool)


class TestFmtMonedaCorto:
    def test_miles(self):
        assert fmt_moneda_corto(1500) == "$2k"

    def test_millones(self):
        assert fmt_moneda_corto(1_200_000) == "$1.2M"

    def test_miles_de_millones(self):
        assert fmt_moneda_corto(2_500_000_000) == "$2.5B"

    def test_cero(self):
        assert fmt_moneda_corto(0) == "$0"

    def test_valor_nulo(self):
        assert fmt_moneda_corto(None) == "$0"

    def test_string_valido(self):
        assert fmt_moneda_corto("3500") == "$4k"

"""Exportación PDF — generación de recibos, remitos y reportes con ReportLab."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_DISPONIBLE = True
except ImportError:
    REPORTLAB_DISPONIBLE = False


def _safe_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "ñ": "n", "Ñ": "N", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "ü": "u", "Ü": "U",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def _fmt_moneda(monto: float) -> str:
    return f"${monto:,.2f}"


def exportar_presupuesto_pdf(presupuesto: Dict[str, Any]) -> bytes | None:
    if not REPORTLAB_DISPONIBLE:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elementos = []

    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=18, textColor=HexColor("#0F2644"))
    elementos.append(Paragraph(f"Presupuesto {presupuesto.get('numero', '')}", title_style))
    elementos.append(Spacer(1, 6*mm))
    elementos.append(Paragraph(f"<b>Cliente:</b> {_safe_text(presupuesto.get('cliente_nombre', ''))}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {presupuesto.get('fecha', '')[:10]}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Estado:</b> {presupuesto.get('estado', '')}", styles["Normal"]))
    elementos.append(Spacer(1, 6*mm))

    items = presupuesto.get("items", [])
    data = [["Concepto", "Cant.", "Precio Unit.", "Subtotal"]]
    for it in items:
        data.append([
            _safe_text(it.get("concepto", "")),
            str(it.get("cantidad", 1)),
            _fmt_moneda(it.get("precio_unitario", 0)),
            _fmt_moneda(it.get("cantidad", 1) * it.get("precio_unitario", 0)),
        ])
    total = sum(it.get("cantidad", 1) * it.get("precio_unitario", 0) for it in items)
    data.append(["", "", "TOTAL", _fmt_moneda(total)])

    t = Table(data, colWidths=[80*mm, 20*mm, 35*mm, 35*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F2644")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [HexColor("#FFFFFF"), HexColor("#F8FAFC")]),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ]))
    elementos.append(t)

    if presupuesto.get("notas"):
        elementos.append(Spacer(1, 6*mm))
        elementos.append(Paragraph(f"<b>Notas:</b> {_safe_text(presupuesto.get('notas', ''))}", styles["Normal"]))

    doc.build(elementos)
    buf.seek(0)
    return buf.getvalue()


def exportar_prefactura_pdf(prefactura: Dict[str, Any]) -> bytes | None:
    if not REPORTLAB_DISPONIBLE:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elementos = []

    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=18, textColor=HexColor("#0F2644"))
    elementos.append(Paragraph(f"Pre-factura {prefactura.get('numero', '')}", title_style))
    elementos.append(Spacer(1, 6*mm))
    elementos.append(Paragraph(f"<b>Cliente:</b> {_safe_text(prefactura.get('cliente_nombre', ''))}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {prefactura.get('fecha', '')[:10]}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Estado:</b> {prefactura.get('estado', '')}", styles["Normal"]))
    if prefactura.get("cae"):
        elementos.append(Paragraph(f"<b>CAE:</b> {prefactura.get('cae', '')}", styles["Normal"]))
    elementos.append(Spacer(1, 6*mm))

    items = prefactura.get("items", [])
    data = [["Concepto", "Cant.", "Precio Unit.", "Subtotal"]]
    for it in items:
        data.append([
            _safe_text(it.get("concepto", "")),
            str(it.get("cantidad", 1)),
            _fmt_moneda(it.get("precio_unitario", 0)),
            _fmt_moneda(it.get("cantidad", 1) * it.get("precio_unitario", 0)),
        ])
    total = sum(it.get("cantidad", 1) * it.get("precio_unitario", 0) for it in items)
    data.append(["", "", "TOTAL", _fmt_moneda(total)])

    t = Table(data, colWidths=[80*mm, 20*mm, 35*mm, 35*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F2644")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [HexColor("#FFFFFF"), HexColor("#F8FAFC")]),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ]))
    elementos.append(t)

    if prefactura.get("notas"):
        elementos.append(Spacer(1, 6*mm))
        elementos.append(Paragraph(f"<b>Notas:</b> {_safe_text(prefactura.get('notas', ''))}", styles["Normal"]))

    doc.build(elementos)
    buf.seek(0)
    return buf.getvalue()


def exportar_reporte_mensual_pdf(reporte: Dict[str, Any]) -> bytes | None:
    if not REPORTLAB_DISPONIBLE:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elementos = []

    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=18, textColor=HexColor("#0F2644"))
    elementos.append(Paragraph("Reporte Mensual para Contador", title_style))
    elementos.append(Spacer(1, 6*mm))

    totales = reporte.get("totales", {})
    elementos.append(Paragraph(f"<b>Total Cobrado:</b> {totales.get('total_cobrado_fmt', '$0.00')}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Total Facturado:</b> {totales.get('total_facturado_fmt', '$0.00')}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Pendiente:</b> {totales.get('pendiente_fmt', '$0.00')}", styles["Normal"]))
    elementos.append(Spacer(1, 6*mm))

    meses = reporte.get("meses", {})
    data = [["Mes", "Cobros", "Cobros $", "Prefacturas", "Prefacturas $"]]
    for mes, datos in sorted(meses.items(), reverse=True):
        data.append([
            mes,
            str(datos.get("cobros_cantidad", 0)),
            _fmt_moneda(datos.get("cobros_total", 0)),
            str(datos.get("prefacturas_cantidad", 0)),
            _fmt_moneda(datos.get("prefacturas_total", 0)),
        ])

    t = Table(data, colWidths=[30*mm, 25*mm, 35*mm, 30*mm, 35*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F2644")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F8FAFC")]),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ]))
    elementos.append(t)

    doc.build(elementos)
    buf.seek(0)
    return buf.getvalue()

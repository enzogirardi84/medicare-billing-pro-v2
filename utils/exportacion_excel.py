"""Exportación Excel — generación de archivos .xlsx con pandas + openpyxl."""
from __future__ import annotations

import io
from typing import Any, Dict, List

try:
    import pandas as pd
    PANDAS_DISPONIBLE = True
except ImportError:
    pd = None
    PANDAS_DISPONIBLE = False


def exportar_clientes_excel(clientes: List[Dict[str, Any]]) -> bytes | None:
    if not PANDAS_DISPONIBLE:
        return None
    df = pd.DataFrame(clientes)
    columnas = ["nombre", "cuit", "dni", "condicion_iva", "direccion", "telefono", "email"]
    df = df[[c for c in columnas if c in df.columns]]
    df.columns = ["Nombre", "CUIT", "DNI", "Condición IVA", "Dirección", "Teléfono", "Email"]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Clientes", index=False)
        ws = writer.sheets["Clientes"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
    return output.getvalue()


def exportar_cobros_excel(cobros: List[Dict[str, Any]]) -> bytes | None:
    if not PANDAS_DISPONIBLE:
        return None
    df = pd.DataFrame(cobros)
    columnas = ["fecha", "cliente_nombre", "monto", "metodo_pago", "referencia"]
    df = df[[c for c in columnas if c in df.columns]]
    df.columns = ["Fecha", "Cliente", "Monto", "Método", "Referencia"]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Cobros", index=False)
        ws = writer.sheets["Cobros"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
    return output.getvalue()


def exportar_presupuestos_excel(presupuestos: List[Dict[str, Any]]) -> bytes | None:
    if not PANDAS_DISPONIBLE:
        return None
    filas = []
    for p in presupuestos:
        for it in p.get("items", []):
            filas.append({
                "Número": p.get("numero", ""),
                "Fecha": p.get("fecha", "")[:10],
                "Cliente": p.get("cliente_nombre", ""),
                "Estado": p.get("estado", ""),
                "Concepto": it.get("concepto", ""),
                "Cantidad": it.get("cantidad", 1),
                "Precio Unit.": it.get("precio_unitario", 0),
                "Subtotal": it.get("cantidad", 1) * it.get("precio_unitario", 0),
            })
    df = pd.DataFrame(filas)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Presupuestos", index=False)
        ws = writer.sheets["Presupuestos"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
    return output.getvalue()


def exportar_reporte_mensual_excel(reporte: Dict[str, Any]) -> bytes | None:
    if not PANDAS_DISPONIBLE:
        return None
    meses = reporte.get("meses", {})
    filas = []
    for mes, datos in sorted(meses.items(), reverse=True):
        filas.append({
            "Mes": mes,
            "Cobros (cant.)": datos.get("cobros_cantidad", 0),
            "Cobros ($)": datos.get("cobros_total", 0),
            "Prefacturas (cant.)": datos.get("prefacturas_cantidad", 0),
            "Prefacturas ($)": datos.get("prefacturas_total", 0),
        })
    df = pd.DataFrame(filas)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Reporte Mensual", index=False)
        ws = writer.sheets["Reporte Mensual"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
    return output.getvalue()

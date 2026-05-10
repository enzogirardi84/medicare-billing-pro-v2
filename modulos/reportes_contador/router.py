"""Reportes para Contador — SQLite."""
from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session

from db.database import get_db, CobroModel, PrefacturaModel, EstadoPagoModel, ClienteModel
from utils import fmt_moneda

router = APIRouter()

@router.get("/mensual", response_model=dict)
async def reporte_mensual(
    empresa_id: str = Query(default="default"),
    anio: int = Query(default=0),
    mes: str = Query(default=""),
    db: Session = Depends(get_db),
):
    q_cobros = db.query(CobroModel).filter(CobroModel.empresa_id == empresa_id, CobroModel.deleted_at == "")
    q_prefac = db.query(PrefacturaModel).filter(PrefacturaModel.empresa_id == empresa_id, PrefacturaModel.deleted_at == "")
    q_estados = db.query(EstadoPagoModel).filter(EstadoPagoModel.empresa_id == empresa_id, EstadoPagoModel.deleted_at == "")

    if anio:
        a = str(anio)
        q_cobros = q_cobros.filter(CobroModel.fecha.like(f"{a}%"))
        q_prefac = q_prefac.filter(PrefacturaModel.fecha.like(f"{a}%"))
        q_estados = q_estados.filter(EstadoPagoModel.fecha_vencimiento.like(f"{a}%"))
    if mes:
        q_cobros = q_cobros.filter(CobroModel.fecha.like(f"{mes}%"))
        q_prefac = q_prefac.filter(PrefacturaModel.fecha.like(f"{mes}%"))
        q_estados = q_estados.filter(EstadoPagoModel.fecha_vencimiento.like(f"{mes}%"))

    cobros = q_cobros.all()
    prefacturas = q_prefac.all()
    estados = q_estados.all()

    total_cobrado = sum(c.monto for c in cobros)
    total_facturado = sum(e.monto_total for e in estados)
    total_pagado = sum(e.monto_pagado for e in estados)

    from utils import agrupar_por_mes
    cobros_agrupados = agrupar_por_mes([{"fecha": c.fecha, "monto": c.monto} for c in cobros], "fecha")
    facs_agrupadas = agrupar_por_mes([{"fecha": p.fecha, "items": p.items_json} for p in prefacturas], "fecha")

    meses_resumen = {}
    for clave in sorted(set(list(cobros_agrupados.keys()) + list(facs_agrupadas.keys())), reverse=True):
        cobros_mes = cobros_agrupados.get(clave, [])
        facs_mes = facs_agrupadas.get(clave, [])
        total_fac_mes = 0.0
        for f in facs_mes:
            import json
            items = json.loads(f.get("items") or "[]")
            total_fac_mes += sum(it.get("cantidad",1) * it.get("precio_unitario",0) for it in items)
        meses_resumen[clave] = {
            "cobros_cantidad": len(cobros_mes),
            "cobros_total": sum(c.get("monto",0) for c in cobros_mes),
            "cobros_total_fmt": fmt_moneda(sum(c.get("monto",0) for c in cobros_mes)),
            "prefacturas_cantidad": len(facs_mes),
            "prefacturas_total": total_fac_mes,
        }

    return {
        "empresa_id": empresa_id,
        "filtro_anio": anio or "todos",
        "filtro_mes": mes or "todos",
        "totales": {
            "total_cobrado": total_cobrado,
            "total_cobrado_fmt": fmt_moneda(total_cobrado),
            "total_facturado": total_facturado,
            "total_facturado_fmt": fmt_moneda(total_facturado),
            "total_pagado": total_pagado,
            "total_pagado_fmt": fmt_moneda(total_pagado),
            "pendiente": total_facturado - total_pagado,
            "pendiente_fmt": fmt_moneda(total_facturado - total_pagado),
        },
        "meses": meses_resumen,
    }

@router.get("/iva", response_model=dict)
async def reporte_iva(
    empresa_id: str = Query(default="default"),
    anio: int = Query(default=0),
    db: Session = Depends(get_db),
):
    q_clientes = db.query(ClienteModel).filter(ClienteModel.empresa_id == empresa_id, ClienteModel.deleted_at == "")
    clientes = {c.id: c for c in q_clientes.all()}
    q_prefac = db.query(PrefacturaModel).filter(PrefacturaModel.empresa_id == empresa_id, PrefacturaModel.deleted_at == "")
    if anio:
        q_prefac = q_prefac.filter(PrefacturaModel.fecha.like(f"{anio}%"))
    prefacturas = q_prefac.all()

    por_condicion = {}
    for p in prefacturas:
        import json
        cliente = clientes.get(p.cliente_id)
        condicion = cliente.condicion_iva if cliente else "Consumidor Final"
        if condicion not in por_condicion:
            por_condicion[condicion] = {"cantidad": 0, "total": 0.0}
        por_condicion[condicion]["cantidad"] += 1
        items = json.loads(p.items_json) if p.items_json else []
        total = sum(it.get("cantidad",1) * it.get("precio_unitario",0) for it in items)
        por_condicion[condicion]["total"] += total

    for cond in por_condicion:
        por_condicion[cond]["total_fmt"] = fmt_moneda(por_condicion[cond]["total"])

    return {
        "empresa_id": empresa_id,
        "anio": anio or "todos",
        "por_condicion_iva": por_condicion,
    }

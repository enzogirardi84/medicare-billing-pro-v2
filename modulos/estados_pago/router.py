"""Estados de Pago — SQLite."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db, EstadoPagoModel, _generar_id, _ahora
from utils import fmt_moneda

router = APIRouter()

ESTADOS_PAGO = ["Pendiente", "Parcial", "Cancelado", "Vencido", "En Mora", "Incobrable"]

class EstadoPagoCreate(BaseModel):
    empresa_id: str = Field(default="default")
    prefactura_id: str = Field(..., min_length=1)
    cliente_id: str = Field(..., min_length=1)
    cliente_nombre: str = Field(default="")
    monto_total: float = Field(..., gt=0)
    monto_pagado: float = Field(default=0.0, ge=0.0)
    estado: str = Field(default="Pendiente")
    fecha_vencimiento: str = Field(default="")
    notas: str = Field(default="", max_length=1000)

class EstadoPagoUpdate(BaseModel):
    monto_pagado: Optional[float] = None
    estado: Optional[str] = None
    notas: Optional[str] = None

def _row_to_dict(e: EstadoPagoModel) -> dict:
    monto_total = e.monto_total or 0
    monto_pagado = e.monto_pagado or 0
    saldo = monto_total - monto_pagado
    return {
        "id": e.id,
        "empresa_id": e.empresa_id,
        "prefactura_id": e.prefactura_id,
        "cliente_id": e.cliente_id,
        "cliente_nombre": e.cliente_nombre,
        "monto_total": monto_total,
        "monto_total_fmt": fmt_moneda(monto_total),
        "monto_pagado": monto_pagado,
        "monto_pagado_fmt": fmt_moneda(monto_pagado),
        "saldo": saldo,
        "saldo_fmt": fmt_moneda(saldo),
        "estado": e.estado,
        "fecha_vencimiento": e.fecha_vencimiento,
        "notas": e.notas,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }

@router.get("/")
async def listar_estados(
    empresa_id: str = Query(default="default"),
    estado: str = Query(default=""),
    cliente_id: str = Query(default=""),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(EstadoPagoModel).filter(EstadoPagoModel.empresa_id == empresa_id, EstadoPagoModel.deleted_at == "")
    if estado:
        q = q.filter(EstadoPagoModel.estado == estado)
    if cliente_id:
        q = q.filter(EstadoPagoModel.cliente_id == cliente_id)
    total = q.count()
    rows = q.order_by(EstadoPagoModel.fecha_vencimiento).offset(offset).limit(limit).all()
    return {"total": total, "data": [_row_to_dict(e) for e in rows]}

@router.get("/{estado_id}", response_model=dict)
async def obtener_estado(estado_id: str, db: Session = Depends(get_db)):
    e = db.query(EstadoPagoModel).filter(EstadoPagoModel.id == estado_id, EstadoPagoModel.deleted_at == "").first()
    if not e:
        raise HTTPException(404, "Estado de pago no encontrado")
    return _row_to_dict(e)

@router.post("/", response_model=dict, status_code=201)
async def crear_estado(body: EstadoPagoCreate, db: Session = Depends(get_db)):
    if body.estado not in ESTADOS_PAGO:
        raise HTTPException(400, f"Estado invalido. Validos: {ESTADOS_PAGO}")
    data = body.model_dump()
    data["id"] = _generar_id()
    data["created_at"] = _ahora()
    data["updated_at"] = data["created_at"]
    row = EstadoPagoModel(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)

@router.put("/{estado_id}", response_model=dict)
async def actualizar_estado(estado_id: str, body: EstadoPagoUpdate, db: Session = Depends(get_db)):
    e = db.query(EstadoPagoModel).filter(EstadoPagoModel.id == estado_id, EstadoPagoModel.deleted_at == "").first()
    if not e:
        raise HTTPException(404, "Estado de pago no encontrado")
    updates = body.model_dump(exclude_unset=True)
    if "estado" in updates and updates["estado"] not in ESTADOS_PAGO:
        raise HTTPException(400, f"Estado invalido. Validos: {ESTADOS_PAGO}")
    for k, v in updates.items():
        if v is not None:
            setattr(e, k, v)
    if e.monto_pagado >= e.monto_total:
        e.estado = "Cancelado"
    elif e.monto_pagado > 0:
        e.estado = "Parcial"
    e.updated_at = _ahora()
    db.commit()
    db.refresh(e)
    return _row_to_dict(e)

@router.delete("/{estado_id}", status_code=204)
async def eliminar_estado(estado_id: str, db: Session = Depends(get_db)):
    e = db.query(EstadoPagoModel).filter(EstadoPagoModel.id == estado_id, EstadoPagoModel.deleted_at == "").first()
    if not e:
        raise HTTPException(404, "Estado de pago no encontrado")
    e.deleted_at = _ahora()
    db.commit()

@router.get("/resumen/cartera", response_model=dict)
async def resumen_cartera(empresa_id: str = Query(default="default"), db: Session = Depends(get_db)):
    rows = db.query(EstadoPagoModel).filter(EstadoPagoModel.empresa_id == empresa_id, EstadoPagoModel.deleted_at == "").all()
    total_facturado = sum((e.monto_total or 0) for e in rows)
    total_cobrado = sum((e.monto_pagado or 0) for e in rows)
    por_estado = {}
    for e in rows:
        est = e.estado or "Pendiente"
        if est not in por_estado:
            por_estado[est] = {"cantidad": 0, "monto_total": 0.0, "monto_pagado": 0.0}
        por_estado[est]["cantidad"] += 1
        por_estado[est]["monto_total"] += e.monto_total or 0
        por_estado[est]["monto_pagado"] += e.monto_pagado or 0
    return {
        "empresa_id": empresa_id,
        "total_facturado": total_facturado,
        "total_facturado_fmt": fmt_moneda(total_facturado),
        "total_cobrado": total_cobrado,
        "total_cobrado_fmt": fmt_moneda(total_cobrado),
        "pendiente_cobro": total_facturado - total_cobrado,
        "pendiente_cobro_fmt": fmt_moneda(total_facturado - total_cobrado),
        "por_estado": por_estado,
    }

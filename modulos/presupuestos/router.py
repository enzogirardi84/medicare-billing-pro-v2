"""Presupuestos — gestión con SQLite."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db, PresupuestoModel, _generar_id, _ahora
from utils import fmt_moneda

router = APIRouter()

ESTADOS = ["Borrador", "Enviado", "Aceptado", "Rechazado", "Vencido", "Convertido"]

class ConceptoItem(BaseModel):
    concepto: str = Field(..., min_length=1, max_length=300)
    cantidad: int = Field(default=1, ge=1)
    precio_unitario: float = Field(default=0.0, ge=0.0)

class PresupuestoCreate(BaseModel):
    empresa_id: str = Field(default="default")
    cliente_id: str = Field(..., min_length=1)
    cliente_nombre: str = Field(default="")
    fecha: str = Field(default="")
    valido_hasta: str = Field(default="")
    items: list[ConceptoItem] = Field(default_factory=list, min_length=1)
    notas: str = Field(default="", max_length=2000)

class PresupuestoUpdate(BaseModel):
    estado: Optional[str] = None
    items: Optional[list[ConceptoItem]] = None
    notas: Optional[str] = None
    valido_hasta: Optional[str] = None
    cliente_nombre: Optional[str] = None

def _row_to_dict(p: PresupuestoModel) -> dict:
    items = json.loads(p.items_json) if p.items_json else []
    total = sum(it.get("cantidad",1) * it.get("precio_unitario",0) for it in items)
    return {
        "id": p.id,
        "empresa_id": p.empresa_id,
        "numero": p.numero,
        "cliente_id": p.cliente_id,
        "cliente_nombre": p.cliente_nombre,
        "fecha": p.fecha,
        "valido_hasta": p.valido_hasta,
        "estado": p.estado,
        "items": items,
        "total": total,
        "total_fmt": fmt_moneda(total),
        "notas": p.notas,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }

@router.get("/")
async def listar_presupuestos(
    empresa_id: str = Query(default="default"),
    estado: str = Query(default=""),
    cliente_id: str = Query(default=""),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(PresupuestoModel).filter(PresupuestoModel.empresa_id == empresa_id)
    if estado:
        q = q.filter(PresupuestoModel.estado == estado)
    if cliente_id:
        q = q.filter(PresupuestoModel.cliente_id == cliente_id)
    total = q.count()
    rows = q.order_by(PresupuestoModel.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "data": [_row_to_dict(p) for p in rows]}

@router.get("/{presupuesto_id}", response_model=dict)
async def obtener_presupuesto(presupuesto_id: str, db: Session = Depends(get_db)):
    p = db.query(PresupuestoModel).filter(PresupuestoModel.id == presupuesto_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    return _row_to_dict(p)

@router.post("/", response_model=dict, status_code=201)
async def crear_presupuesto(body: PresupuestoCreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["id"] = _generar_id()
    data["numero"] = "PRES-" + _generar_id()[:6].upper()
    data["estado"] = "Borrador"
    data["created_at"] = _ahora()
    data["updated_at"] = data["created_at"]
    data.setdefault("fecha", data["created_at"])
    data.setdefault("valido_hasta", data["created_at"])
    data["items_json"] = json.dumps(data.pop("items"))
    row = PresupuestoModel(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)

@router.put("/{presupuesto_id}", response_model=dict)
async def actualizar_presupuesto(presupuesto_id: str, body: PresupuestoUpdate, db: Session = Depends(get_db)):
    p = db.query(PresupuestoModel).filter(PresupuestoModel.id == presupuesto_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    updates = body.model_dump(exclude_unset=True)
    if "estado" in updates and updates["estado"] not in ESTADOS:
        raise HTTPException(400, f"Estado invalido. Validos: {ESTADOS}")
    for k, v in updates.items():
        if v is not None:
            if k == "items":
                v = json.dumps(v)
                k = "items_json"
            setattr(p, k, v)
    p.updated_at = _ahora()
    db.commit()
    db.refresh(p)
    return _row_to_dict(p)

@router.delete("/{presupuesto_id}", status_code=204)
async def eliminar_presupuesto(presupuesto_id: str, db: Session = Depends(get_db)):
    p = db.query(PresupuestoModel).filter(PresupuestoModel.id == presupuesto_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    db.delete(p)
    db.commit()

@router.post("/{presupuesto_id}/convertir", response_model=dict)
async def convertir_a_prefactura(presupuesto_id: str, db: Session = Depends(get_db)):
    p = db.query(PresupuestoModel).filter(PresupuestoModel.id == presupuesto_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    if p.estado not in ("Aceptado", "Enviado"):
        raise HTTPException(400, "Solo se pueden convertir presupuestos Aceptados o Enviados")
    p.estado = "Convertido"
    p.updated_at = _ahora()
    db.commit()
    items = json.loads(p.items_json) if p.items_json else []
    return {
        "mensaje": "Presupuesto convertido a pre-factura",
        "presupuesto_id": presupuesto_id,
        "prefactura_crear": {
            "cliente_id": p.cliente_id,
            "cliente_nombre": p.cliente_nombre,
            "items": items,
            "presupuesto_origen_id": presupuesto_id,
        },
    }

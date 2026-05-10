"""Historial de Cobros — SQLite."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db, CobroModel, _generar_id, _ahora
from utils import fmt_moneda

router = APIRouter()

METODOS_PAGO = ["Efectivo", "Transferencia", "Debito", "Credito", "Cheque", "MercadoPago", "Otro"]

class CobroCreate(BaseModel):
    empresa_id: str = Field(default="default")
    prefactura_id: str = Field(default="")
    cliente_id: str = Field(..., min_length=1)
    cliente_nombre: str = Field(default="")
    fecha: str = Field(default="")
    monto: float = Field(..., gt=0)
    metodo_pago: str = Field(default="Efectivo")
    referencia: str = Field(default="", max_length=200)
    notas: str = Field(default="", max_length=1000)

class CobroUpdate(BaseModel):
    metodo_pago: Optional[str] = None
    referencia: Optional[str] = None
    notas: Optional[str] = None

def _row_to_dict(c: CobroModel) -> dict:
    return {
        "id": c.id,
        "empresa_id": c.empresa_id,
        "prefactura_id": c.prefactura_id,
        "cliente_id": c.cliente_id,
        "cliente_nombre": c.cliente_nombre,
        "fecha": c.fecha,
        "monto": c.monto,
        "monto_fmt": fmt_moneda(c.monto),
        "metodo_pago": c.metodo_pago,
        "referencia": c.referencia,
        "notas": c.notas,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }

@router.get("/")
async def listar_cobros(
    empresa_id: str = Query(default="default"),
    cliente_id: str = Query(default=""),
    metodo_pago: str = Query(default=""),
    mes: str = Query(default=""),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(CobroModel).filter(CobroModel.empresa_id == empresa_id)
    if cliente_id:
        q = q.filter(CobroModel.cliente_id == cliente_id)
    if metodo_pago:
        q = q.filter(CobroModel.metodo_pago == metodo_pago)
    if mes:
        q = q.filter(CobroModel.fecha.like(f"{mes}%"))
    total = q.count()
    rows = q.order_by(CobroModel.fecha.desc()).offset(offset).limit(limit).all()
    return {"total": total, "data": [_row_to_dict(c) for c in rows]}

@router.get("/{cobro_id}", response_model=dict)
async def obtener_cobro(cobro_id: str, db: Session = Depends(get_db)):
    c = db.query(CobroModel).filter(CobroModel.id == cobro_id).first()
    if not c:
        raise HTTPException(404, "Cobro no encontrado")
    return _row_to_dict(c)

@router.post("/", response_model=dict, status_code=201)
async def registrar_cobro(body: CobroCreate, db: Session = Depends(get_db)):
    if body.metodo_pago not in METODOS_PAGO:
        raise HTTPException(400, f"Metodo de pago invalido. Validos: {METODOS_PAGO}")
    data = body.model_dump()
    data["id"] = _generar_id()
    data["created_at"] = _ahora()
    data["updated_at"] = data["created_at"]
    data.setdefault("fecha", data["created_at"])
    row = CobroModel(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)

@router.put("/{cobro_id}", response_model=dict)
async def actualizar_cobro(cobro_id: str, body: CobroUpdate, db: Session = Depends(get_db)):
    c = db.query(CobroModel).filter(CobroModel.id == cobro_id).first()
    if not c:
        raise HTTPException(404, "Cobro no encontrado")
    updates = body.model_dump(exclude_unset=True)
    if "metodo_pago" in updates and updates["metodo_pago"] not in METODOS_PAGO:
        raise HTTPException(400, f"Metodo de pago invalido. Validos: {METODOS_PAGO}")
    for k, v in updates.items():
        if v is not None:
            setattr(c, k, v)
    c.updated_at = _ahora()
    db.commit()
    db.refresh(c)
    return _row_to_dict(c)

@router.delete("/{cobro_id}", status_code=204)
async def eliminar_cobro(cobro_id: str, db: Session = Depends(get_db)):
    c = db.query(CobroModel).filter(CobroModel.id == cobro_id).first()
    if not c:
        raise HTTPException(404, "Cobro no encontrado")
    db.delete(c)
    db.commit()

@router.get("/resumen/mensual", response_model=dict)
async def resumen_mensual(
    empresa_id: str = Query(default="default"),
    anio: int = Query(default=0),
    db: Session = Depends(get_db),
):
    q = db.query(CobroModel).filter(CobroModel.empresa_id == empresa_id)
    if anio:
        q = q.filter(CobroModel.fecha.like(f"{anio}%"))
    rows = q.all()
    resumen = {}
    for c in rows:
        mes = str(c.fecha)[:7] if c.fecha else "unknown"
        if mes not in resumen:
            resumen[mes] = {"total": 0.0, "cantidad": 0, "metodos": {}}
        resumen[mes]["total"] += c.monto
        resumen[mes]["cantidad"] += 1
        resumen[mes]["metodos"][c.metodo_pago] = resumen[mes]["metodos"].get(c.metodo_pago, 0.0) + c.monto
    return {"empresa_id": empresa_id, "meses": resumen}

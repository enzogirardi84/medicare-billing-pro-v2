"""Clientes Fiscales — ABM con SQLite + validaciones argentinas + soft delete."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db, ClienteModel, _generar_id, _ahora
from utils.validaciones_ar import validar_cuit, validar_dni, validar_email, formatear_cuit

router = APIRouter()

class ClienteFiscalBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    cuit: str = Field(default="", max_length=13)
    dni: str = Field(default="", max_length=20)
    condicion_iva: str = Field(default="Consumidor Final")
    direccion: str = Field(default="", max_length=300)
    telefono: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=150)
    notas: str = Field(default="", max_length=1000)

class ClienteFiscalCreate(ClienteFiscalBase):
    empresa_id: str = Field(default="default")

class ClienteFiscalUpdate(BaseModel):
    nombre: Optional[str] = None
    cuit: Optional[str] = None
    dni: Optional[str] = None
    condicion_iva: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    notas: Optional[str] = None

class ClienteFiscalResponse(ClienteFiscalBase):
    id: str
    empresa_id: str
    created_at: str
    updated_at: str
    model_config = {"from_attributes": True}

def _row_to_dict(c: ClienteModel) -> dict:
    return {
        "id": c.id,
        "empresa_id": c.empresa_id,
        "nombre": c.nombre,
        "cuit": formatear_cuit(c.cuit) if c.cuit else "",
        "dni": c.dni,
        "condicion_iva": c.condicion_iva,
        "direccion": c.direccion,
        "telefono": c.telefono,
        "email": c.email,
        "notas": c.notas,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }

def _validar(body: ClienteFiscalBase):
    if body.cuit and not validar_cuit(body.cuit):
        raise HTTPException(400, f"CUIT invalido: {body.cuit}")
    if body.dni and not validar_dni(body.dni):
        raise HTTPException(400, f"DNI invalido: {body.dni}")
    if body.email and not validar_email(body.email):
        raise HTTPException(400, f"Email invalido: {body.email}")

@router.get("/", summary="Listar clientes fiscales")
async def listar_clientes(
    empresa_id: str = Query(default="default"),
    buscar: str = Query(default=""),
    condicion_iva: str = Query(default=""),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(ClienteModel).filter(ClienteModel.empresa_id == empresa_id, ClienteModel.deleted_at == "")
    if buscar:
        q = q.filter(
            (ClienteModel.nombre.ilike(f"%{buscar}%")) |
            (ClienteModel.cuit.ilike(f"%{buscar}%")) |
            (ClienteModel.dni.ilike(f"%{buscar}%"))
        )
    if condicion_iva:
        q = q.filter(ClienteModel.condicion_iva == condicion_iva)
    total = q.count()
    rows = q.order_by(ClienteModel.nombre).offset(offset).limit(limit).all()
    return {"total": total, "data": [_row_to_dict(c) for c in rows]}

@router.get("/{cliente_id}", response_model=dict, summary="Obtener cliente por ID")
async def obtener_cliente(cliente_id: str, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id, ClienteModel.deleted_at == "").first()
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return _row_to_dict(c)

@router.post("/", response_model=dict, status_code=201, summary="Crear cliente fiscal")
async def crear_cliente(body: ClienteFiscalCreate, db: Session = Depends(get_db)):
    _validar(body)
    data = body.model_dump()
    data["id"] = _generar_id()
    data["created_at"] = _ahora()
    data["updated_at"] = data["created_at"]
    row = ClienteModel(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)

@router.put("/{cliente_id}", response_model=dict, summary="Actualizar cliente fiscal")
async def actualizar_cliente(cliente_id: str, body: ClienteFiscalUpdate, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id, ClienteModel.deleted_at == "").first()
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    updates = body.model_dump(exclude_unset=True)
    if "cuit" in updates and updates["cuit"] and not validar_cuit(updates["cuit"]):
        raise HTTPException(400, f"CUIT invalido: {updates['cuit']}")
    if "dni" in updates and updates["dni"] and not validar_dni(updates["dni"]):
        raise HTTPException(400, f"DNI invalido: {updates['dni']}")
    if "email" in updates and updates["email"] and not validar_email(updates["email"]):
        raise HTTPException(400, f"Email invalido: {updates['email']}")
    for k, v in updates.items():
        if v is not None:
            setattr(c, k, v)
    c.updated_at = _ahora()
    db.commit()
    db.refresh(c)
    return _row_to_dict(c)

@router.delete("/{cliente_id}", status_code=204, summary="Eliminar cliente (soft delete)")
async def eliminar_cliente(cliente_id: str, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id, ClienteModel.deleted_at == "").first()
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.deleted_at = _ahora()
    db.commit()

@router.get("/stats/condiciones", response_model=dict, summary="Estadisticas por condicion IVA")
async def stats_condiciones(empresa_id: str = Query(default="default"), db: Session = Depends(get_db)):
    rows = db.query(ClienteModel).filter(ClienteModel.empresa_id == empresa_id, ClienteModel.deleted_at == "").all()
    conteo = {}
    for c in rows:
        iva = c.condicion_iva or "Consumidor Final"
        conteo[iva] = conteo.get(iva, 0) + 1
    return {"empresa_id": empresa_id, "condiciones": conteo, "total": sum(conteo.values())}

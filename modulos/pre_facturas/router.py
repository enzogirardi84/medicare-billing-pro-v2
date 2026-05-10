"""Pre-facturas — SQLite con CAE stub."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db, PrefacturaModel, _generar_id, _ahora
from utils import fmt_moneda
from integrations.arca_wsfe import solicitar_cae, solicitar_cae_stub
from config.arca_config import cargar_configuracion_arca

router = APIRouter()

ESTADOS = ["Pendiente", "Enviada_ARCA", "Aprobada", "Rechazada_ARCA", "Anulada", "Parcial"]

class ConceptoItem(BaseModel):
    concepto: str = Field(..., min_length=1, max_length=300)
    cantidad: int = Field(default=1, ge=1)
    precio_unitario: float = Field(default=0.0, ge=0.0)

class PrefacturaCreate(BaseModel):
    empresa_id: str = Field(default="default")
    cliente_id: str = Field(..., min_length=1)
    cliente_nombre: str = Field(default="")
    fecha: str = Field(default="")
    items: list[ConceptoItem] = Field(default_factory=list, min_length=1)
    notas: str = Field(default="", max_length=2000)
    presupuesto_origen_id: str = Field(default="")

class PrefacturaUpdate(BaseModel):
    estado: Optional[str] = None
    items: Optional[list[ConceptoItem]] = None
    notas: Optional[str] = None
    cae: Optional[str] = None
    cae_vencimiento: Optional[str] = None
    numero_factura: Optional[str] = None

def _row_to_dict(p: PrefacturaModel) -> dict:
    items = json.loads(p.items_json) if p.items_json else []
    total = sum(it.get("cantidad",1) * it.get("precio_unitario",0) for it in items)
    return {
        "id": p.id,
        "empresa_id": p.empresa_id,
        "numero": p.numero,
        "cliente_id": p.cliente_id,
        "cliente_nombre": p.cliente_nombre,
        "fecha": p.fecha,
        "estado": p.estado,
        "items": items,
        "total": total,
        "total_fmt": fmt_moneda(total),
        "notas": p.notas,
        "cae": p.cae,
        "cae_vencimiento": p.cae_vencimiento,
        "numero_factura": p.numero_factura,
        "presupuesto_origen_id": p.presupuesto_origen_id,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }

@router.get("/")
async def listar_prefacturas(
    empresa_id: str = Query(default="default"),
    estado: str = Query(default=""),
    cliente_id: str = Query(default=""),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(PrefacturaModel).filter(PrefacturaModel.empresa_id == empresa_id)
    if estado:
        q = q.filter(PrefacturaModel.estado == estado)
    if cliente_id:
        q = q.filter(PrefacturaModel.cliente_id == cliente_id)
    total = q.count()
    rows = q.order_by(PrefacturaModel.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "data": [_row_to_dict(p) for p in rows]}

@router.get("/{prefactura_id}", response_model=dict)
async def obtener_prefactura(prefactura_id: str, db: Session = Depends(get_db)):
    p = db.query(PrefacturaModel).filter(PrefacturaModel.id == prefactura_id).first()
    if not p:
        raise HTTPException(404, "Pre-factura no encontrada")
    return _row_to_dict(p)

@router.post("/", response_model=dict, status_code=201)
async def crear_prefactura(body: PrefacturaCreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["id"] = _generar_id()
    data["numero"] = "FAC-" + _generar_id()[:6].upper()
    data["estado"] = "Pendiente"
    data["cae"] = ""
    data["cae_vencimiento"] = ""
    data["numero_factura"] = ""
    data["created_at"] = _ahora()
    data["updated_at"] = data["created_at"]
    data.setdefault("fecha", data["created_at"])
    data["items_json"] = json.dumps(data.pop("items"))
    row = PrefacturaModel(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)

@router.put("/{prefactura_id}", response_model=dict)
async def actualizar_prefactura(prefactura_id: str, body: PrefacturaUpdate, db: Session = Depends(get_db)):
    p = db.query(PrefacturaModel).filter(PrefacturaModel.id == prefactura_id).first()
    if not p:
        raise HTTPException(404, "Pre-factura no encontrada")
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

@router.delete("/{prefactura_id}", status_code=204)
async def eliminar_prefactura(prefactura_id: str, db: Session = Depends(get_db)):
    p = db.query(PrefacturaModel).filter(PrefacturaModel.id == prefactura_id).first()
    if not p:
        raise HTTPException(404, "Pre-factura no encontrada")
    db.delete(p)
    db.commit()

@router.post("/{prefactura_id}/solicitar-cae", response_model=dict)
async def endpoint_solicitar_cae(prefactura_id: str, db: Session = Depends(get_db)):
    p = db.query(PrefacturaModel).filter(PrefacturaModel.id == prefactura_id).first()
    if not p:
        raise HTTPException(404, "Pre-factura no encontrada")
    if p.estado not in ("Pendiente", "Rechazada_ARCA"):
        raise HTTPException(400, "La pre-factura no esta en estado Pendiente")
    p.estado = "Enviada_ARCA"
    p.updated_at = _ahora()
    db.commit()
    cfg = cargar_configuracion_arca()

    # Buscar datos del cliente para el CUIT/DNI
    from db.database import ClienteModel
    cliente_db = db.query(ClienteModel).filter(ClienteModel.id == p.cliente_id).first()
    cliente = {
        "nombre": p.cliente_nombre,
        "cuit": cliente_db.cuit if cliente_db else "",
        "dni": cliente_db.dni if cliente_db else "",
        "condicion_iva": cliente_db.condicion_iva if cliente_db else "Consumidor Final",
    }
    items = json.loads(p.items_json) if p.items_json else []
    prefactura = {"id": p.id, "items": items}

    # Intentar integracion real; si falla o faltan certificados, fallback a stub
    resultado = None
    try:
        if cfg.cert_path.exists() and cfg.key_path.exists() and cfg.cuit and cfg.cuit != "00000000000":
            resultado = solicitar_cae(cfg, prefactura, cliente)
            if resultado.get("cae"):
                p.cae = resultado["cae"]
                p.cae_vencimiento = resultado.get("cae_vencimiento", "")
                p.numero_factura = resultado.get("numero_factura", "")
                p.estado = "Aprobada"
            else:
                p.estado = "Rechazada_ARCA"
        else:
            raise RuntimeError("Certificados ARCA no configurados")
    except Exception as exc:
        import logging
        logging.getLogger("billing_pro").warning(f"ARCA real fallo ({exc}), usando stub")
        resultado = solicitar_cae_stub(cfg, prefactura, cliente)
        if resultado.get("cae"):
            p.cae = resultado["cae"]
            p.cae_vencimiento = resultado.get("cae_vencimiento", "")
            p.numero_factura = resultado.get("numero_factura", "")
            p.estado = "Aprobada"
        else:
            p.estado = "Rechazada_ARCA"

    p.updated_at = _ahora()
    db.commit()
    return {
        "mensaje": "CAE procesado",
        "prefactura_id": prefactura_id,
        "estado": p.estado,
        "cae": p.cae,
        "numero_factura": p.numero_factura,
        "modo": "real" if (cfg.cert_path.exists() and cfg.cuit != "00000000000") else "stub",
    }

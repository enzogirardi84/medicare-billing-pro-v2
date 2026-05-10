"""Medicare Billing Pro — Microservicio de Facturacion Electronica ARCA.
Punto de entrada principal. Ejecutar con: uvicorn main:app --reload --port 8502
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config.arca_config import cargar_configuracion_arca, ArcaConfig
from auth.api_key import verificar_api_key
from db.database import get_db, ClienteModel, PresupuestoModel, PrefacturaModel, CobroModel, EstadoPagoModel
from modulos.clientes_fiscales.router import router as clientes_router
from modulos.presupuestos.router import router as presupuestos_router
from modulos.pre_facturas.router import router as prefacturas_router
from modulos.historial_cobros.router import router as cobros_router
from modulos.estados_pago.router import router as estados_router
from modulos.reportes_contador.router import router as reportes_router
from utils.exportacion_excel import exportar_clientes_excel, exportar_cobros_excel, exportar_presupuestos_excel
from utils.exportacion_pdf import exportar_presupuesto_pdf, exportar_prefactura_pdf
from utils.middleware import TimingMiddleware
from integrations.arca_wsfe import consultar_estado_servicios_stub

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("billing_pro")

arca_config: ArcaConfig | None = None
limiter = Limiter(key_func=get_remote_address)

tags_metadata = [
    {"name": "Sistema", "description": "Health check, metricas y estado del microservicio"},
    {"name": "ARCA", "description": "Estado y servicios de ARCA (AFIP)"},
    {"name": "Clientes Fiscales", "description": "ABM de datos fiscales: CUIT, DNI, condicion IVA"},
    {"name": "Presupuestos", "description": "Presupuestos no fiscales para clientes"},
    {"name": "Pre-facturas", "description": "Preparacion de facturas y solicitud de CAE a ARCA"},
    {"name": "Historial de Cobros", "description": "Registro de cobros exitosos y rechazados"},
    {"name": "Estados de Pago", "description": "Control de pagos pendientes, parciales o cancelados"},
    {"name": "Reportes Contador", "description": "Reportes mensuales y de IVA para el contador"},
    {"name": "Exportacion", "description": "Exportacion a Excel (.xlsx)"},
    {"name": "Webhooks", "description": "Webhooks para notificaciones externas"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global arca_config
    logger.info("Iniciando Medicare Billing Pro v2.0.0")
    arca_config = cargar_configuracion_arca()
    if arca_config.homologacion:
        logger.info("Modo HOMOLOGACION ARCA activo")
    else:
        logger.info("Modo PRODUCCION ARCA activo")
    yield
    logger.info("Apagando Medicare Billing Pro")


app = FastAPI(
    title="Medicare Billing Pro",
    version="2.0.0",
    description="Microservicio de facturacion electronica ARCA para profesionales de la salud.",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)

# ── Routers ─────────────────────────────────────────────────
app.include_router(clientes_router, prefix="/api/clientes", tags=["Clientes Fiscales"], dependencies=[Depends(verificar_api_key)])
app.include_router(presupuestos_router, prefix="/api/presupuestos", tags=["Presupuestos"], dependencies=[Depends(verificar_api_key)])
app.include_router(prefacturas_router, prefix="/api/prefacturas", tags=["Pre-facturas"], dependencies=[Depends(verificar_api_key)])
app.include_router(cobros_router, prefix="/api/cobros", tags=["Historial de Cobros"], dependencies=[Depends(verificar_api_key)])
app.include_router(estados_router, prefix="/api/estados", tags=["Estados de Pago"], dependencies=[Depends(verificar_api_key)])
app.include_router(reportes_router, prefix="/api/reportes", tags=["Reportes Contador"], dependencies=[Depends(verificar_api_key)])


# ── Health & Info ───────────────────────────────────────────
@app.get("/api/health", tags=["Sistema"], summary="Estado del microservicio")
@limiter.limit("10/minute")
async def health_check(request: Request):
    return {
        "status": "ok",
        "servicio": "Medicare Billing Pro",
        "version": "2.0.0",
        "arca_modo": "homologacion" if (arca_config and arca_config.homologacion) else "produccion",
        "arca_ready": arca_config is not None and arca_config.cert_path.exists(),
    }


@app.get("/api/arca/status", tags=["ARCA"], summary="Configuracion y estado de certificados ARCA")
@limiter.limit("10/minute")
async def arca_status(request: Request):
    if not arca_config:
        return JSONResponse({"error": "Configuracion ARCA no cargada"}, 503)
    return {
        "homologacion": arca_config.homologacion,
        "cuit": arca_config.cuit,
        "certificado": str(arca_config.cert_path),
        "cert_valido": arca_config.cert_path.exists(),
        "key_valida": arca_config.key_path.exists(),
    }


@app.get("/api/arca/servicios", tags=["ARCA"], summary="Estado de servidores ARCA")
@limiter.limit("10/minute")
async def arca_servicios(request: Request):
    if not arca_config:
        return JSONResponse({"error": "Configuracion ARCA no cargada"}, 503)
    return consultar_estado_servicios_stub(arca_config)


# ── Métricas ────────────────────────────────────────────────
@app.get("/api/metrics", tags=["Sistema"], summary="Conteo de registros por entidad")
@limiter.limit("10/minute")
async def metrics(request: Request, db=Depends(get_db)):
    return {
        "clientes": db.query(ClienteModel).filter(ClienteModel.deleted_at == "").count(),
        "presupuestos": db.query(PresupuestoModel).filter(PresupuestoModel.deleted_at == "").count(),
        "prefacturas": db.query(PrefacturaModel).filter(PrefacturaModel.deleted_at == "").count(),
        "cobros": db.query(CobroModel).filter(CobroModel.deleted_at == "").count(),
        "estados_pago": db.query(EstadoPagoModel).filter(EstadoPagoModel.deleted_at == "").count(),
    }


# ── Exportaciones ───────────────────────────────────────────
@app.get("/api/exportar/clientes/excel", tags=["Exportacion"], summary="Exportar clientes a Excel")
@limiter.limit("5/minute")
async def exportar_clientes_xlsx(request: Request, empresa_id: str = "default", db=Depends(get_db)):
    rows = db.query(ClienteModel).filter(ClienteModel.empresa_id == empresa_id, ClienteModel.deleted_at == "").all()
    data = [{"nombre": c.nombre, "cuit": c.cuit, "condicion_iva": c.condicion_iva, "email": c.email} for c in rows]
    buf = exportar_clientes_excel(data)
    return PlainTextResponse(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=clientes.xlsx"})


@app.get("/api/exportar/cobros/excel", tags=["Exportacion"], summary="Exportar cobros a Excel")
@limiter.limit("5/minute")
async def exportar_cobros_xlsx(request: Request, empresa_id: str = "default", db=Depends(get_db)):
    rows = db.query(CobroModel).filter(CobroModel.empresa_id == empresa_id, CobroModel.deleted_at == "").all()
    data = [{"fecha": c.fecha, "cliente_nombre": c.cliente_nombre, "monto": c.monto, "metodo_pago": c.metodo_pago} for c in rows]
    buf = exportar_cobros_excel(data)
    return PlainTextResponse(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=cobros.xlsx"})


@app.get("/api/exportar/presupuestos/excel", tags=["Exportacion"], summary="Exportar presupuestos a Excel")
@limiter.limit("5/minute")
async def exportar_presupuestos_xlsx(request: Request, empresa_id: str = "default", db=Depends(get_db)):
    import json
    rows = db.query(PresupuestoModel).filter(PresupuestoModel.empresa_id == empresa_id, PresupuestoModel.deleted_at == "").all()
    data = []
    for p in rows:
        items = json.loads(p.items_json) if p.items_json else []
        total = sum(it.get("cantidad",1)*it.get("precio_unitario",0) for it in items)
        data.append({"numero": p.numero, "cliente_nombre": p.cliente_nombre, "estado": p.estado, "total": total, "fecha": p.fecha})
    buf = exportar_presupuestos_excel(data)
    return PlainTextResponse(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=presupuestos.xlsx"})


# ── Webhook CAE ─────────────────────────────────────────────
@app.post("/api/webhooks/arca/cae", tags=["Webhooks"], summary="Recibir resultado de CAE desde ARCA")
async def webhook_cae_resultado(payload: dict):
    """Recibe resultado de CAE desde ARCA (o sistema externo)."""
    prefactura_id = payload.get("prefactura_id")
    cae = payload.get("cae")
    estado = payload.get("estado")
    logger.info(f"Webhook CAE recibido: prefactura={prefactura_id} cae={cae} estado={estado}")
    return {"mensaje": "Webhook procesado", "prefactura_id": prefactura_id, "cae": cae}


# ── Frontend ──────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "frontend")), name="static")

@app.get("/", tags=["Frontend"], include_in_schema=False)
async def serve_index():
    return FileResponse(str(PROJECT_ROOT / "frontend" / "index.html"))

@app.get("/{path:path}", tags=["Frontend"], include_in_schema=False)
async def serve_spa(path: str):
    # Solo si no es una ruta de API, servir el SPA
    if not path.startswith("api/") and not path.startswith("static/"):
        return FileResponse(str(PROJECT_ROOT / "frontend" / "index.html"))
    return JSONResponse({"error": "Not found"}, 404)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {type(exc).__name__}: {exc}")
    return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, 500)

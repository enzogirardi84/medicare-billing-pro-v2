"""Capa de persistencia con SQLAlchemy.
Soporta PostgreSQL (Supabase) como principal y SQLite como fallback.
El microservicio es totalmente independiente de Medicare Pro.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger("billing_pro")

# Cargar .env propio del microservicio
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

Base = declarative_base()


class _AuditMixin:
    """Mixin base para auditoria y soft delete."""
    created_at = Column(String, default="")
    updated_at = Column(String, default="")
    created_by = Column(String, default="")
    updated_by = Column(String, default="")
    deleted_at = Column(String, default="")  # soft delete: vacio = activo


class ClienteModel(Base, _AuditMixin):
    __tablename__ = "clientes"
    id = Column(String, primary_key=True)
    empresa_id = Column(String, default="default")
    nombre = Column(String, nullable=False)
    cuit = Column(String, default="")
    dni = Column(String, default="")
    condicion_iva = Column(String, default="Consumidor Final")
    direccion = Column(String, default="")
    telefono = Column(String, default="")
    email = Column(String, default="")
    notas = Column(Text, default="")


class PresupuestoModel(Base, _AuditMixin):
    __tablename__ = "presupuestos"
    id = Column(String, primary_key=True)
    empresa_id = Column(String, default="default")
    numero = Column(String, default="")
    cliente_id = Column(String, default="")
    cliente_nombre = Column(String, default="")
    fecha = Column(String, default="")
    valido_hasta = Column(String, default="")
    estado = Column(String, default="Borrador")
    items_json = Column(Text, default="[]")
    notas = Column(Text, default="")


class PrefacturaModel(Base, _AuditMixin):
    __tablename__ = "prefacturas"
    id = Column(String, primary_key=True)
    empresa_id = Column(String, default="default")
    numero = Column(String, default="")
    cliente_id = Column(String, default="")
    cliente_nombre = Column(String, default="")
    fecha = Column(String, default="")
    estado = Column(String, default="Pendiente")
    items_json = Column(Text, default="[]")
    notas = Column(Text, default="")
    cae = Column(String, default="")
    cae_vencimiento = Column(String, default="")
    numero_factura = Column(String, default="")
    presupuesto_origen_id = Column(String, default="")


class CobroModel(Base, _AuditMixin):
    __tablename__ = "cobros"
    id = Column(String, primary_key=True)
    empresa_id = Column(String, default="default")
    prefactura_id = Column(String, default="")
    cliente_id = Column(String, default="")
    cliente_nombre = Column(String, default="")
    fecha = Column(String, default="")
    monto = Column(Float, default=0.0)
    metodo_pago = Column(String, default="Efectivo")
    referencia = Column(String, default="")
    notas = Column(Text, default="")


class EstadoPagoModel(Base, _AuditMixin):
    __tablename__ = "estados_pago"
    id = Column(String, primary_key=True)
    empresa_id = Column(String, default="default")
    prefactura_id = Column(String, default="")
    cliente_id = Column(String, default="")
    cliente_nombre = Column(String, default="")
    monto_total = Column(Float, default=0.0)
    monto_pagado = Column(Float, default=0.0)
    estado = Column(String, default="Pendiente")
    fecha_vencimiento = Column(String, default="")
    notas = Column(Text, default="")


# ── Seleccion de motor: PostgreSQL > SQLite ──────────────────
def _crear_engine():
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        try:
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args={"connect_timeout": 10},
            )
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            logger.info("Conectado a PostgreSQL (Supabase)")
            return engine
        except Exception as exc:
            logger.warning(f"PostgreSQL no disponible ({exc}), usando SQLite fallback")
    sqlite_path = os.getenv("SQLITE_PATH", "./billing_pro.db")
    engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
    )
    logger.info(f"Usando SQLite: {sqlite_path}")
    return engine


ENGINE = _crear_engine()
Base.metadata.create_all(ENGINE)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def get_db() -> Session:
    return SessionLocal()


def _generar_id() -> str:
    return uuid.uuid4().hex[:12]


def _ahora() -> str:
    return datetime.now().isoformat()

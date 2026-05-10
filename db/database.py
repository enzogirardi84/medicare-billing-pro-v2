"""Capa de persistencia con SQLAlchemy + SQLite."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, select, delete, update
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

Base = declarative_base()


class ClienteModel(Base):
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
    created_at = Column(String, default="")
    updated_at = Column(String, default="")


class PresupuestoModel(Base):
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
    created_at = Column(String, default="")
    updated_at = Column(String, default="")


class PrefacturaModel(Base):
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
    created_at = Column(String, default="")
    updated_at = Column(String, default="")


class CobroModel(Base):
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
    created_at = Column(String, default="")
    updated_at = Column(String, default="")


class EstadoPagoModel(Base):
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
    created_at = Column(String, default="")
    updated_at = Column(String, default="")


# ── Engine ──────────────────────────────────────────────────
ENGINE = create_engine("sqlite:///./billing_pro.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(ENGINE)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def get_db() -> Session:
    return SessionLocal()


def _generar_id() -> str:
    return uuid.uuid4().hex[:12]


def _ahora() -> str:
    return datetime.now().isoformat()

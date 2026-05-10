"""Tests basicos para Medicare Billing Pro API."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

API_KEY = "test-key-123"
HEADERS = {"X-API-Key": API_KEY}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_crud_clientes():
    # create
    r = client.post("/api/clientes/", json={
        "nombre": "Clinica Test",
        "condicion_iva": "Responsable Inscripto",
        "empresa_id": "default",
    }, headers=HEADERS)
    assert r.status_code == 201
    cid = r.json()["id"]

    # get
    r = client.get(f"/api/clientes/{cid}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Clinica Test"

    # list
    r = client.get("/api/clientes/", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # update
    r = client.put(f"/api/clientes/{cid}", json={"nombre": "Clinica Test Updated"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Clinica Test Updated"

    # delete
    r = client.delete(f"/api/clientes/{cid}", headers=HEADERS)
    assert r.status_code == 204

    r = client.get(f"/api/clientes/{cid}", headers=HEADERS)
    assert r.status_code == 404


def test_presupuestos():
    r = client.post("/api/presupuestos/", json={
        "empresa_id": "default",
        "cliente_id": "test-cli",
        "cliente_nombre": "Clinica Test",
        "items": [
            {"concepto": "Consulta", "cantidad": 1, "precio_unitario": 15000},
        ],
    }, headers=HEADERS)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["total"] == 15000

    r = client.get(f"/api/presupuestos/{pid}", headers=HEADERS)
    assert r.status_code == 200

    r = client.delete(f"/api/presupuestos/{pid}", headers=HEADERS)
    assert r.status_code == 204


def test_prefactura_solicitar_cae():
    r = client.post("/api/prefacturas/", json={
        "empresa_id": "default",
        "cliente_id": "test-cli",
        "cliente_nombre": "Clinica Test",
        "items": [
            {"concepto": "Consulta", "cantidad": 1, "precio_unitario": 10000},
        ],
    }, headers=HEADERS)
    assert r.status_code == 201
    fid = r.json()["id"]

    r = client.post(f"/api/prefacturas/{fid}/solicitar-cae", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["estado"] == "Enviada_ARCA"

    # BackgroundTasks en TestClient se ejecutan sincronamente; verificar con GET
    r = client.get(f"/api/prefacturas/{fid}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["estado"] == "Aprobada"
    assert r.json()["cae"] != ""

    r = client.delete(f"/api/prefacturas/{fid}", headers=HEADERS)
    assert r.status_code == 204


def test_cobros():
    r = client.post("/api/cobros/", json={
        "empresa_id": "default",
        "cliente_id": "test-cli",
        "cliente_nombre": "Clinica Test",
        "monto": 5000,
        "metodo_pago": "Transferencia",
    }, headers=HEADERS)
    assert r.status_code == 201
    cobro_id = r.json()["id"]

    r = client.get("/api/cobros/resumen/mensual?empresa_id=default", headers=HEADERS)
    assert r.status_code == 200
    assert "meses" in r.json()

    r = client.delete(f"/api/cobros/{cobro_id}", headers=HEADERS)
    assert r.status_code == 204


def test_estados_pago():
    r = client.post("/api/estados/", json={
        "empresa_id": "default",
        "prefactura_id": "pf-1",
        "cliente_id": "test-cli",
        "cliente_nombre": "Clinica Test",
        "monto_total": 10000,
        "monto_pagado": 0,
        "estado": "Pendiente",
    }, headers=HEADERS)
    assert r.status_code == 201
    eid = r.json()["id"]

    r = client.put(f"/api/estados/{eid}", json={"monto_pagado": 10000}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["estado"] == "Cancelado"

    r = client.delete(f"/api/estados/{eid}", headers=HEADERS)
    assert r.status_code == 204

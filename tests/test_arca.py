"""Tests de integracion ARCA (modo stub cuando no hay certificados)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

API_KEY = "test-key-123"
HEADERS = {"X-API-Key": API_KEY}


def test_arca_status():
    r = client.get("/api/arca/status")
    # Puede ser 200 (config cargada) o 503 (sin config en tests)
    assert r.status_code in (200, 503)
    data = r.json()
    assert "homologacion" in data or "error" in data


def test_arca_servicios():
    r = client.get("/api/arca/servicios")
    assert r.status_code in (200, 503)
    data = r.json()
    assert "app_server" in data or "error" in data


def test_webhook_cae():
    r = client.post("/api/webhooks/arca/cae", json={
        "prefactura_id": "test-123",
        "cae": "12345678901234",
        "estado": "Aprobada",
    })
    assert r.status_code == 200
    assert r.json()["cae"] == "12345678901234"

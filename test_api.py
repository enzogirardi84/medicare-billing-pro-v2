import urllib.request, json

BASE = "http://localhost:8502/api"

# Crear cliente
data = json.dumps({
    "nombre": "Clinica Test",
    "cuit": "30-12345678-9",
    "condicion_iva": "Responsable Inscripto",
    "empresa_id": "default",
}).encode()
req = urllib.request.Request(f"{BASE}/clientes/", data=data, headers={"Content-Type": "application/json"}, method="POST")
r = urllib.request.urlopen(req)
c = json.loads(r.read())
print("CREADO:", c["id"], c["nombre"])

# Listar
r2 = urllib.request.urlopen(f"{BASE}/clientes/")
l = json.loads(r2.read())
print("TOTAL:", l["total"])

# Eliminar
req3 = urllib.request.Request(f"{BASE}/clientes/{c['id']}", method="DELETE")
urllib.request.urlopen(req3)
r4 = urllib.request.urlopen(f"{BASE}/clientes/")
print("POST-DELETE:", json.loads(r4.read())["total"])

# Crear presupuesto
data2 = json.dumps({
    "empresa_id": "default",
    "cliente_id": "test-cli",
    "cliente_nombre": "Clinica Test",
    "items": [
        {"concepto": "Consulta cardiológica", "cantidad": 1, "precio_unitario": 15000},
        {"concepto": "ECG", "cantidad": 1, "precio_unitario": 8500},
    ],
}).encode()
req5 = urllib.request.Request(f"{BASE}/presupuestos/", data=data2, headers={"Content-Type": "application/json"}, method="POST")
r5 = urllib.request.urlopen(req5)
p = json.loads(r5.read())
print("PRESUPUESTO:", p["numero"], p["total_fmt"])

print("ALL OK")

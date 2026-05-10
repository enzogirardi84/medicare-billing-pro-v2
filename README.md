# Medicare Billing Pro — Microservicio de Facturación Electrónica ARCA

Microservicio independiente para facturación electrónica ante ARCA (ex-AFIP).
Completamente aislado de la lógica clínica de Medicare Pro.

## Estructura

```
medicare_billing_pro/
├── main.py                    # Punto de entrada FastAPI
├── config/
│   └── arca_config.py         # Certificados y credenciales ARCA
├── modulos/
│   ├── clientes_fiscales/     # ABM de datos fiscales
│   ├── presupuestos/          # Presupuestos no fiscales
│   ├── pre_facturas/          # Pre-facturas antes del CAE
│   ├── historial_cobros/      # Registro de cobros
│   ├── estados_pago/          # Control de pagos
│   └── reportes_contador/     # Reportes mensuales
└── utils/
    ├── exportacion_excel.py   # Exportación .xlsx
    └── exportacion_pdf.py     # Exportación .pdf
```

## Instalación

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Ejecución

```bash
uvicorn main:app --reload --port 8502
```

## API Docs

- Swagger: http://localhost:8502/docs
- ReDoc: http://localhost:8502/redoc
- Health: http://localhost:8502/api/health

## Certificados ARCA

Colocar los certificados en `certs/`:
- `certificado.crt`
- `clave_privada.key`

"""Medicare Billing Pro - entry point."""
from __future__ import annotations

import traceback

import streamlit as st

from core.app_logging import configurar_logging_basico, log_event
from core.auth import render_logout_button, require_auth
from core.config import ALLOW_LOCAL_FALLBACK, APP_NAME, APP_VERSION, DEBUG, PAGE_TITLE
from core.db_sql import LOCAL_DATA_PATH, get_clientes, get_cobros, get_facturas_arca, get_prefacturas, get_presupuestos, supabase
from core.billing_logic import total_saldo_prefacturas
from core.utils import fmt_moneda

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="B",
    layout="wide",
    initial_sidebar_state="expanded",
)

configurar_logging_basico()


def _main():
    if not require_auth():
        st.stop()

    user = st.session_state.get("billing_user", {})
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    empresa_id = st.session_state.get("billing_empresa_id", "")

    with st.sidebar:
        st.markdown(f"## {APP_NAME}")
        st.caption(f"v{APP_VERSION}")
        st.divider()
        st.markdown(f"**{user.get('nombre', 'Usuario')}**")
        st.caption(f"Empresa: {empresa_nombre}")
        st.caption(f"Rol: {user.get('rol', 'usuario')}")
        st.caption("Supabase conectado" if supabase else "Supabase requerido")
        if ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
            st.caption(f"Archivo local: `{LOCAL_DATA_PATH.name}`")
        st.divider()
        render_logout_button()
        st.divider()
        st.caption("2026 Medicare Pro Suite")
        st.caption("[Documentacion](https://github.com/enzogirardi84/medicare-pro-v2)")

    st.title("Medicare Billing Pro")
    st.caption(f"Facturacion medica profesional | {empresa_nombre}")
    status = "Supabase activo" if supabase else "Supabase requerido"
    if supabase:
        st.success(status)
    else:
        st.warning(status)

    MODULOS = {
        "Resumen": "dashboard",
        "Clientes fiscales": "clientes",
        "Presupuestos": "presupuestos",
        "Pre-facturas": "prefacturas",
        "Facturas ARCA": "facturas_arca",
        "Cobros": "cobros",
        "Cuenta corriente": "cuenta_corriente",
        "Reportes": "reportes",
        "Configuracion": "configuracion",
    }

    if "billing_modulo_activo" not in st.session_state or st.session_state["billing_modulo_activo"] not in MODULOS:
        st.session_state["billing_modulo_activo"] = "Resumen"

    modulo_activo = st.session_state["billing_modulo_activo"]

    clientes_resumen = get_clientes(empresa_id)
    presupuestos_resumen = get_presupuestos(empresa_id)
    prefacturas_resumen = get_prefacturas(empresa_id)
    cobros_resumen = get_cobros(empresa_id)
    facturas_arca_resumen = get_facturas_arca(empresa_id)
    cobros_total = sum(float(c.get("monto", 0) or 0) for c in cobros_resumen)
    pendiente_total = total_saldo_prefacturas(prefacturas_resumen, cobros_resumen)

    kpi_cols = st.columns(6)
    kpis = [
        ("Clientes", len(clientes_resumen)),
        ("Presupuestos", len(presupuestos_resumen)),
        ("Pre-facturas", len(prefacturas_resumen)),
        ("Facturas ARCA", len(facturas_arca_resumen)),
        ("Cobrado", fmt_moneda(cobros_total)),
        ("Pendiente", fmt_moneda(pendiente_total)),
    ]
    for col, (label, value) in zip(kpi_cols, kpis):
        with col:
            st.metric(label=label, value=value)

    cols = st.columns(len(MODULOS))
    for i, label in enumerate(MODULOS):
        with cols[i]:
            if st.button(
                label,
                key=f"nav_{label}",
                use_container_width=True,
                type="primary" if modulo_activo == label else "secondary",
            ):
                st.session_state["billing_modulo_activo"] = label
                st.rerun()

    st.divider()

    if not supabase:
        st.error(
            "Supabase no esta conectado. Configura SUPABASE_URL, SUPABASE_KEY y SUPABASE_SERVICE_ROLE_KEY."
        )
    elif ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
        st.info("Modo respaldo local habilitado. En produccion usa BILLING_ALLOW_LOCAL_FALLBACK=false.")

    modulo_key = MODULOS.get(modulo_activo, "dashboard")

    if modulo_key == "dashboard":
        from views.dashboard import render_dashboard
        render_dashboard()
    elif modulo_key == "clientes":
        from views.clientes import render_clientes
        render_clientes()
    elif modulo_key == "presupuestos":
        from views.presupuestos import render_presupuestos
        render_presupuestos()
    elif modulo_key == "prefacturas":
        from views.prefacturas import render_prefacturas
        render_prefacturas()
    elif modulo_key == "facturas_arca":
        from views.facturas_arca import render_facturas_arca
        render_facturas_arca()
    elif modulo_key == "cobros":
        from views.cobros import render_cobros
        render_cobros()
    elif modulo_key == "cuenta_corriente":
        from views.cuenta_corriente import render_cuenta_corriente
        render_cuenta_corriente()
    elif modulo_key == "reportes":
        from views.reportes import render_reportes
        render_reportes()
    elif modulo_key == "configuracion":
        from views.configuracion import render_configuracion
        render_configuracion()


try:
    _main()
except Exception:
    st.error("Error en la aplicacion. Detalles tecnicos:")
    st.code(traceback.format_exc())

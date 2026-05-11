"""Medicare Billing Pro - entry point."""
from __future__ import annotations

import time
import traceback
from html import escape

import streamlit as st

from core.app_logging import configurar_logging_basico, log_event
from core.auth import render_logout_button, require_auth
from core.config import ALLOW_LOCAL_FALLBACK, APP_NAME, APP_VERSION, DEBUG, PAGE_TITLE
from core.db_sql import LOCAL_DATA_PATH, _active_supabase, get_clientes, get_cobros, get_facturas_arca, get_prefacturas, get_presupuestos
from core.billing_logic import total_saldo_prefacturas
from core.utils import fmt_moneda

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="B",
    layout="wide",
    initial_sidebar_state="expanded",
)

configurar_logging_basico()


MODULOS = {
    "Resumen": "dashboard",
    "Clientes fiscales": "clientes",
    "Presupuestos": "presupuestos",
    "Pre-facturas": "prefacturas",
    "Facturas ARCA": "facturas_arca",
    "Cobros": "cobros",
    "Cuenta corriente": "cuenta_corriente",
    "Reportes": "reportes",
    "Auditoria": "auditoria",
    "Configuracion": "configuracion",
}

MODULO_ICONOS = {
    "Resumen": "Panel",
    "Clientes fiscales": "Clientes",
    "Presupuestos": "Presupuestos",
    "Pre-facturas": "Pre-facturas",
    "Facturas ARCA": "ARCA",
    "Cobros": "Cobros",
    "Cuenta corriente": "Cuenta",
    "Reportes": "Reportes",
    "Auditoria": "Auditoria",
    "Configuracion": "Config.",
}


def _inject_global_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --mbp-bg: #080d16;
            --mbp-panel: #111a2a;
            --mbp-panel-soft: #172236;
            --mbp-line: #2a3548;
            --mbp-text: #f7fbff;
            --mbp-muted: #9aa7b9;
            --mbp-teal: #20c7ba;
            --mbp-blue: #2e7df0;
            --mbp-red: #ff4b4b;
        }
        .stApp { background: var(--mbp-bg); color: var(--mbp-text); }
        .main .block-container {
            max-width: 1240px;
            padding: 1.2rem 1.8rem 2.4rem;
        }
        [data-testid="stSidebar"] {
            background: #101827;
            border-right: 1px solid rgba(255,255,255,.08);
        }
        h1, h2, h3, h4, p, label, span { letter-spacing: 0 !important; }
        h2 { margin-top: .8rem; }
        .billing-header {
            border: 1px solid rgba(255,255,255,.1);
            border-radius: 8px;
            padding: 1.35rem 1.45rem;
            background: linear-gradient(135deg, #122342 0%, #102235 50%, #0c726c 100%);
            box-shadow: 0 18px 48px rgba(0,0,0,.28);
            margin-bottom: 1rem;
        }
        .billing-header__eyebrow {
            color: #7ef3e8;
            font-size: .75rem;
            text-transform: uppercase;
            font-weight: 800;
            letter-spacing: .08em !important;
            margin-bottom: .35rem;
        }
        .billing-header h1 {
            margin: 0;
            font-size: clamp(1.55rem, 3vw, 2.35rem);
            line-height: 1.12;
        }
        .billing-header p {
            margin: .6rem 0 0;
            color: rgba(255,255,255,.82);
        }
        .billing-summary {
            display: grid;
            grid-template-columns: repeat(6, minmax(120px, 1fr));
            gap: .75rem;
            margin: .85rem 0 1.1rem;
        }
        .billing-summary__card {
            border: 1px solid rgba(255,255,255,.1);
            border-radius: 8px;
            padding: .85rem .95rem;
            background: rgba(17, 26, 42, .9);
            min-width: 0;
        }
        .billing-summary__label {
            color: var(--mbp-muted);
            font-size: .78rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: .25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .billing-summary__value {
            color: var(--mbp-text);
            font-size: clamp(1.05rem, 1.7vw, 1.45rem);
            font-weight: 800;
            line-height: 1.2;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .stButton > button,
        .stDownloadButton > button,
        .stFormSubmitButton > button,
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"],
        [data-testid="stBaseButton-primary"] {
            min-height: 42px;
            border-radius: 8px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            padding: .5rem .8rem !important;
            font-weight: 700 !important;
        }
        .stButton > button p,
        .stDownloadButton > button p,
        .stFormSubmitButton > button p {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            margin: 0 !important;
        }
        .stFormSubmitButton > button,
        .stButton > button[kind="primary"],
        [data-testid="stBaseButton-primary"] {
            background: linear-gradient(135deg, var(--mbp-teal) 0%, var(--mbp-blue) 100%) !important;
            border: 1px solid rgba(94, 234, 212, .35) !important;
            color: #fff !important;
        }
        .stFormSubmitButton > button p,
        .stButton > button[kind="primary"] p,
        [data-testid="stBaseButton-primary"] p {
            color: #fff !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 8px;
            padding: .35rem .45rem;
            margin-bottom: .35rem;
            background: rgba(255,255,255,.025);
        }
        [data-testid="stTabs"] [role="tab"] p,
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricValue"] {
            white-space: nowrap !important;
        }
        [data-testid="stMetricValue"] {
            font-size: clamp(1.2rem, 2vw, 1.85rem) !important;
        }
        [data-testid="stExpander"] {
            border-radius: 8px !important;
            border-color: rgba(255,255,255,.12) !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 8px !important;
        }
        div[data-testid="stHorizontalBlock"] {
            align-items: stretch;
        }
        .stTextInput input,
        .stDateInput input,
        .stNumberInput input,
        .stSelectbox div[data-baseweb="select"] > div {
            min-height: 42px;
        }
        @media (max-width: 1100px) {
            .billing-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .main .block-container { padding-left: 1rem; padding-right: 1rem; }
        }
        @media (max-width: 720px) {
            .billing-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _summary_cards(items: list[tuple[str, object]]) -> str:
    cards = []
    for label, value in items:
        cards.append(
            "<div class='billing-summary__card'>"
            f"<div class='billing-summary__label'>{escape(str(label))}</div>"
            f"<div class='billing-summary__value'>{escape(str(value))}</div>"
            "</div>"
        )
    return "<div class='billing-summary'>" + "".join(cards) + "</div>"


def _main():
    if not require_auth():
        st.stop()

    _inject_global_style()

    user = st.session_state.get("billing_user", {})
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    empresa_id = st.session_state.get("billing_empresa_id", "")

    if "billing_modulo_activo" not in st.session_state or st.session_state["billing_modulo_activo"] not in MODULOS:
        st.session_state["billing_modulo_activo"] = "Resumen"

    with st.sidebar:
        st.markdown(f"## {APP_NAME}")
        st.caption(f"v{APP_VERSION}")
        st.divider()
        st.markdown(f"**{user.get('nombre', 'Usuario')}**")
        st.caption(f"Empresa: {empresa_nombre}")
        st.caption(f"Rol: {user.get('rol', 'usuario')}")
        sb_conn = _active_supabase() is not None
        st.caption("Supabase conectado" if sb_conn else "Modo local")
        if ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
            st.caption(f"Archivo local: `{LOCAL_DATA_PATH.name}`")
        st.divider()
        st.caption("Modulo")
        etiquetas = list(MODULOS)
        modulo_seleccionado = st.radio(
            "Modulo",
            etiquetas,
            index=etiquetas.index(st.session_state["billing_modulo_activo"]),
            format_func=lambda label: f"{MODULO_ICONOS.get(label, '')} - {label}",
            label_visibility="collapsed",
        )
        if modulo_seleccionado != st.session_state["billing_modulo_activo"]:
            st.session_state["billing_modulo_activo"] = modulo_seleccionado
            st.rerun()
        st.divider()
        render_logout_button()
        st.divider()
        st.caption("2026 Medicare Pro Suite")
        st.caption("[Documentacion](https://github.com/enzogirardi84/medicare-pro-v2)")

    modulo_activo = st.session_state["billing_modulo_activo"]
    st.markdown(
        f"""
        <section class="billing-header">
            <div class="billing-header__eyebrow">Facturacion medica profesional</div>
            <h1>Medicare Billing Pro</h1>
            <p>{escape(empresa_nombre)} - {escape(modulo_activo)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    _cache_key = f"billing_cache_{empresa_id}"
    _cache_ts_key = "billing_cache_ts"
    cache_valid = False
    if _cache_key in st.session_state and _cache_ts_key in st.session_state:
        cache_valid = time.time() - st.session_state[_cache_ts_key] < 30

    if cache_valid:
        cached = st.session_state[_cache_key]
        clientes_resumen = cached["clientes"]
        presupuestos_resumen = cached["presupuestos"]
        prefacturas_resumen = cached["prefacturas"]
        cobros_resumen = cached["cobros"]
        facturas_arca_resumen = cached["facturas_arca"]
    else:
        clientes_resumen = get_clientes(empresa_id)
        presupuestos_resumen = get_presupuestos(empresa_id)
        prefacturas_resumen = get_prefacturas(empresa_id)
        cobros_resumen = get_cobros(empresa_id)
        facturas_arca_resumen = get_facturas_arca(empresa_id)
        st.session_state[_cache_key] = {
            "clientes": clientes_resumen,
            "presupuestos": presupuestos_resumen,
            "prefacturas": prefacturas_resumen,
            "cobros": cobros_resumen,
            "facturas_arca": facturas_arca_resumen,
        }
        st.session_state[_cache_ts_key] = time.time()
    cobros_total = sum(float(c.get("monto", 0) or 0) for c in cobros_resumen)
    pendiente_total = total_saldo_prefacturas(prefacturas_resumen, cobros_resumen)

    kpis = [
        ("Clientes", len(clientes_resumen)),
        ("Presupuestos", len(presupuestos_resumen)),
        ("Pre-facturas", len(prefacturas_resumen)),
        ("Facturas ARCA", len(facturas_arca_resumen)),
        ("Cobrado", fmt_moneda(cobros_total)),
        ("Pendiente", fmt_moneda(pendiente_total)),
    ]
    st.markdown(_summary_cards(kpis), unsafe_allow_html=True)

    if not _active_supabase():
        st.warning("Modo local activo. Conecta Supabase para persistencia en la nube.")
    elif ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
        st.success("Supabase conectado. Modo respaldo local habilitado.")

    if st.button("🔄 Refrescar datos", use_container_width=True, key="refresh_all_data"):
        for key in list(st.session_state.keys()):
            if key.startswith(("cache_", "borrador_")):
                del st.session_state[key]
        st.toast("Cache limpiado. Recargando datos...")
        st.rerun()

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
    elif modulo_key == "auditoria":
        from views.auditoria import render_auditoria
        render_auditoria()
    elif modulo_key == "configuracion":
        from views.configuracion import render_configuracion
        render_configuracion()


def run_app() -> None:
    try:
        _main()
    except Exception:
        st.error("Error en la aplicacion. Detalles tecnicos:")
        st.code(traceback.format_exc())


if __name__ == "__main__":
    run_app()

"""Vista de Auditoria - registro de cambios."""
from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from core.db_sql import get_auditoria
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda


def render_auditoria() -> None:
    st.markdown("## 🕐 Historial de auditoria")
    st.caption("Registro de cambios realizados por los usuarios.")

    empresa_id = st.session_state.get("billing_empresa_id", "")

    with st.spinner("Cargando auditoria..."):
        registros = get_auditoria(empresa_id, limit=200)

    if not registros:
        bloque_estado_vacio("Sin registros", "Aun no hay cambios registrados.")
        return

    f1, f2 = st.columns([2, 1])
    with f1:
        busqueda = st.text_input("Buscar", placeholder="Usuario, accion o entidad...").strip().lower()
    with f2:
        entidad_filtro = st.selectbox("Entidad", ["Todas", "cliente", "presupuesto", "prefactura", "cobro", "factura_arca", "cambiar_estado"])

    filtrados = registros
    if entidad_filtro != "Todas":
        filtrados = [r for r in filtrados if entidad_filtro in str(r.get("entidad", "")).lower()]
    if busqueda:
        filtrados = [
            r for r in filtrados
            if busqueda in str(r.get("usuario", "")).lower()
            or busqueda in str(r.get("accion", "")).lower()
            or busqueda in str(r.get("entidad", "")).lower()
        ]

    st.metric("Registros", len(filtrados))

    # Paginacion
    _PAGE_SIZE = 20
    total_pages = max(1, (len(filtrados) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    if len(filtrados) > _PAGE_SIZE:
        pg_cols = st.columns([3, 1])
        with pg_cols[0]:
            page = st.selectbox("Pagina", options=list(range(1, total_pages + 1)), key="audit_page") - 1
        with pg_cols[1]:
            st.caption(f"Mostrando {min(_PAGE_SIZE, len(filtrados) - page * _PAGE_SIZE)} de {len(filtrados)}")
    else:
        page = 0
    paginated = filtrados[page * _PAGE_SIZE:(page + 1) * _PAGE_SIZE]

    with st.container(height=600, border=False):
        for r in paginated:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    iconos = {
                        "cliente": "👤",
                        "presupuesto": "📋",
                        "prefactura": "📄",
                        "cobro": "💵",
                        "factura_arca": "🏛️",
                        "cambiar_estado": "🔄",
                    }
                    entidad = str(r.get("entidad", "")).lower()
                    icon = iconos.get(entidad, "📝")
                    st.markdown(
                        f"**{icon} {r.get('accion', '-').replace('_', ' ').title()}** | "
                        f"{r.get('entidad', '-').replace('_', ' ').title()}"
                    )
                    detalle = r.get("detalle", {})
                    if detalle and isinstance(detalle, dict):
                        detalle_str = " | ".join(f"{k}: {v}" for k, v in detalle.items() if v is not None)
                        if detalle_str:
                            st.caption(f"Detalle: {detalle_str}")
                with c2:
                    st.caption(f"👤 {r.get('usuario', '—')}")
                    st.caption(f"🕐 {fmt_fecha(str(r.get('created_at', ''))[:10])}")

"""Vista de Pre-facturas."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_prefactura, get_clientes, get_prefacturas, upsert_prefactura
from core.excel_export import XLSX_DISPONIBLE, exportar_prefacturas_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_prefactura_pdf
from core.billing_logic import enriquecer_prefacturas_con_saldo, money
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda, fmt_moneda_corto, generar_id, hoy, mostrar_error_db, sanitize_filename

ESTADOS_PREFACTURA = ["Pendiente", "Cobrada", "Anulada", "Parcial"]


def _parse_date(value: Any, default: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return default


def _form_prefactura(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    es_edicion = existing is not None
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    if not cliente_opts:
        st.warning("Primero carga un cliente fiscal para poder crear pre-facturas.")
        return None

    base_items = existing.get("items", []) if existing else []
    form_id = existing.get("id", "new") if existing else "new"
    borrador_key = f"borrador_prefactura_{form_id}"
    borrador = st.session_state.get(borrador_key, {}) if not es_edicion else {}

    item_count = st.number_input(
        "Cantidad de conceptos",
        min_value=1,
        max_value=20,
        value=max(1, len(base_items) or borrador.get("item_count", 1) or 1),
        key=f"fac_item_count_{form_id}",
    )

    # Setear defaults en session_state para widgets con key
    for i in range(int(item_count)):
        base = base_items[i] if i < len(base_items) and isinstance(base_items[i], dict) else {}
        for field, default in [(f"fac_conc_{form_id}_{i}", base.get("concepto", "")),
                                (f"fac_cant_{form_id}_{i}", float(base.get("cantidad", 1) or 1)),
                                (f"fac_precio_{form_id}_{i}", float(base.get("precio_unitario", 0) or 0))]:
            if field not in st.session_state:
                st.session_state[field] = default

    with st.form(f"fac_form_{form_id}", border=True):
        st.markdown(f"### {'Editar pre-factura' if existing else 'Nueva pre-factura'}")
        c1, c2 = st.columns(2)
        names = list(cliente_opts.keys())
        with c1:
            default_cliente = existing.get("cliente_nombre", "") if existing else borrador.get("cliente_nombre", "")
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + names,
                index=names.index(default_cliente) + 1
                if default_cliente in cliente_opts
                else 0,
            )
        with c2:
            fecha = st.date_input("Fecha", value=_parse_date(existing.get("fecha") if existing else borrador.get("fecha", ""), date.today()))

        st.markdown("#### Conceptos")
        # Headers
        h1, h2, h3, h4 = st.columns([3.2, 1, 1.3, 1.5])
        with h1:
            st.markdown("**Concepto**")
        with h2:
            st.markdown("**Cant.**")
        with h3:
            st.markdown("**Precio $**")
        with h4:
            st.markdown("**Subtotal**")
        items = []
        for i in range(int(item_count)):
            ic1, ic2, ic3, ic4 = st.columns([3.2, 1, 1.3, 1.5])
            with ic1:
                concepto = st.text_input(
                    "Concepto",
                    key=f"fac_conc_{form_id}_{i}",
                    placeholder="Ej: Honorarios medicos marzo",
                    label_visibility="collapsed",
                )
            with ic2:
                cantidad = st.number_input("Cant.", min_value=1.0, step=1.0, key=f"fac_cant_{form_id}_{i}", label_visibility="collapsed")
            with ic3:
                precio = st.number_input("Precio $", min_value=0.0, step=100.0, key=f"fac_precio_{form_id}_{i}", label_visibility="collapsed")
            with ic4:
                sub = cantidad * precio
                st.markdown(f"<p style='margin-top:.6rem'>{fmt_moneda(sub)}</p>", unsafe_allow_html=True)
            if concepto.strip():
                items.append({"concepto": concepto.strip(), "cantidad": cantidad, "precio_unitario": precio})

        total = sum(float(it["cantidad"]) * float(it["precio_unitario"]) for it in items)
        st.markdown(f"**Total: {fmt_moneda(total)}**")
        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else borrador.get("notas", ""), height=70)

        sc1, sc2 = st.columns([1, 1])
        with sc1:
            submitted = st.form_submit_button("Guardar pre-factura", use_container_width=True, type="primary")
        with sc2:
            guardar_borrador = st.form_submit_button("💾 Guardar borrador", use_container_width=True)
        if guardar_borrador:
            st.session_state[borrador_key] = {
                "cliente_nombre": cliente_sel,
                "fecha": fecha.isoformat() if fecha else "",
                "notas": notas,
                "item_count": int(item_count),
            }
            st.toast("Borrador guardado.")
            st.rerun()
        if submitted:
            if not cliente_sel:
                st.error("Selecciona un cliente.")
                return None
            if not items:
                st.error("Agrega al menos un concepto.")
                return None
            if total <= 0:
                st.error("El total debe ser mayor a cero.")
                return None
            st.session_state.pop(borrador_key, None)
            cliente_data = cliente_opts.get(cliente_sel, {})
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "numero": existing.get("numero") if existing else f"FAC-{generar_id()[:6].upper()}",
                "cliente_id": cliente_data.get("id", ""),
                "cliente_nombre": cliente_sel,
                "cliente_dni": cliente_data.get("dni", ""),
                "fecha": fecha.isoformat(),
                "items": items,
                "total": total,
                "estado": existing.get("estado", "Pendiente") if existing else "Pendiente",
                "notas": notas.strip(),
            }
    return None


def render_prefacturas() -> None:
    st.markdown("## Pre-facturas")
    st.caption("Documentos previos a la factura oficial, listos para cobrar y exportar.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    from core.db_sql import get_cobros

    with st.spinner("Cargando pre-facturas..."):
        cobros = get_cobros(empresa_id)
        prefacturas = enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), cobros)

    tab1, tab2 = st.tabs(["Historial", "Nueva pre-factura"])

    with tab1:
        if not prefacturas:
            bloque_estado_vacio("Sin pre-facturas", "Crea tu primera pre-factura o converti un presupuesto aceptado.")
        else:
            # Busqueda con boton
            sc1, sc2, sc3 = st.columns([2.5, 0.8, 0.8])
            with sc1:
                busqueda_input = st.text_input(
                    "Buscar",
                    placeholder="Numero, cliente o DNI/CUIT...",
                    key="pref_search_input",
                    value=st.session_state.get("pref_busqueda", ""),
                )
            with sc2:
                if st.button("🔍 Buscar", key="pref_buscar", use_container_width=True):
                    st.session_state["pref_busqueda"] = busqueda_input.strip().lower()
                    st.rerun()
            with sc3:
                if st.session_state.get("pref_busqueda"):
                    if st.button("✕ Limpiar", key="pref_limpiar", use_container_width=True):
                        st.session_state["pref_busqueda"] = ""
                        st.rerun()
                else:
                    st.empty()

            f2, f3, f4 = st.columns([1, 1, 1])
            with f2:
                estado_filtro = st.selectbox("Estado", ["Todos"] + ESTADOS_PREFACTURA)
            with f3:
                fecha_desde = st.date_input("Desde", value=None, key="pref_fecha_desde")
            with f4:
                fecha_hasta = st.date_input("Hasta", value=None, key="pref_fecha_hasta")
            busqueda = st.session_state.get("pref_busqueda", "")
            filtradas = prefacturas
            if estado_filtro != "Todos":
                filtradas = [p for p in filtradas if p.get("estado") == estado_filtro]
            if fecha_desde:
                filtradas = [p for p in filtradas if str(p.get("fecha", ""))[:10] >= fecha_desde.isoformat()]
            if fecha_hasta:
                filtradas = [p for p in filtradas if str(p.get("fecha", ""))[:10] <= fecha_hasta.isoformat()]
            if busqueda:
                filtradas = [
                    p
                    for p in filtradas
                    if busqueda in str(p.get("numero", "")).lower()
                    or busqueda in str(p.get("cliente_nombre", "")).lower()
                    or busqueda in str(p.get("cliente_dni", "")).lower()
                ]

            k1, k2, k3 = st.columns(3)
            total_filtrado = sum(money(p.get("total")) for p in filtradas)
            cobrado_filtrado = sum(money(p.get("cobrado")) for p in filtradas)
            saldo_filtrado = sum(money(p.get("saldo")) for p in filtradas)
            k1.metric("Total filtrado", fmt_moneda_corto(total_filtrado), help=fmt_moneda(total_filtrado))
            k2.metric("Cobrado", fmt_moneda_corto(cobrado_filtrado), help=fmt_moneda(cobrado_filtrado))
            k3.metric("Saldo", fmt_moneda_corto(saldo_filtrado), help=fmt_moneda(saldo_filtrado))
            if XLSX_DISPONIBLE and filtradas:
                st.download_button(
                    "Exportar Excel",
                    data=exportar_prefacturas_excel(filtradas, empresa_nombre),
                    file_name=f"prefacturas_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            # Paginacion
            _PAGE_SIZE = 15
            total_pages = max(1, (len(filtradas) + _PAGE_SIZE - 1) // _PAGE_SIZE)
            if len(filtradas) > _PAGE_SIZE:
                pg_cols = st.columns([3, 1])
                with pg_cols[0]:
                    page = st.selectbox("Pagina", options=list(range(1, total_pages + 1)), key="pref_page") - 1
                with pg_cols[1]:
                    st.caption(f"Mostrando {min(_PAGE_SIZE, len(filtradas) - page * _PAGE_SIZE)} de {len(filtradas)}")
            else:
                page = 0
            paginated = filtradas[page * _PAGE_SIZE:(page + 1) * _PAGE_SIZE]

            with st.container(height=610, border=False):
                for p in paginated:
                    pid = p.get("id")
                    with st.container(border=True):
                        c1, c2 = st.columns([4.2, 1.4])
                        with c1:
                            st.markdown(f"**{p.get('numero', '-')}** | {p.get('cliente_nombre', '-')}")
                            st.caption(f"DNI/CUIT: {p.get('cliente_dni', '-')} | {fmt_fecha(p.get('fecha', ''))}")
                            st.caption(
                                f"Total: {fmt_moneda(p.get('total', 0))} | "
                                f"Cobrado: {fmt_moneda(p.get('cobrado', 0))} | "
                                f"Saldo: {fmt_moneda(p.get('saldo', 0))}"
                            )
                            if p.get("estado_calculado") and p.get("estado_calculado") != p.get("estado"):
                                st.caption(f"Estado sugerido por cobros: {p.get('estado_calculado')}")
                        with c2:
                            nuevo_estado = st.selectbox(
                                "Estado",
                                ESTADOS_PREFACTURA,
                                index=ESTADOS_PREFACTURA.index(p.get("estado", "Pendiente")) if p.get("estado") in ESTADOS_PREFACTURA else 0,
                                key=f"fac_est_{pid}",
                                label_visibility="collapsed",
                            )
                            if nuevo_estado != p.get("estado"):
                                updated = dict(p)
                                updated["estado"] = nuevo_estado
                                if upsert_prefactura(updated):
                                    st.toast("Estado actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el estado")

                        a1, a2, a3, a4, a5 = st.columns([1, 1, 1, 1, 1])
                        with a1:
                            if FPDF_DISPONIBLE:
                                st.download_button(
                                    "PDF",
                                    data=exportar_prefactura_pdf(p, empresa_nombre, p.get("items", [])),
                                    file_name=f"prefactura_{sanitize_filename(p.get('numero', ''))}.pdf",
                                    mime="application/pdf",
                                    key=f"pdf_fac_{pid}",
                                    use_container_width=True,
                                )
                        with a2:
                            if st.button("Duplicar", key=f"dup_fac_{pid}", use_container_width=True):
                                duplicado = {
                                    "id": generar_id(),
                                    "empresa_id": empresa_id,
                                    "numero": f"FAC-{generar_id()[:6].upper()}",
                                    "cliente_id": p.get("cliente_id", ""),
                                    "cliente_nombre": p.get("cliente_nombre", ""),
                                    "cliente_dni": p.get("cliente_dni", ""),
                                    "fecha": hoy().isoformat(),
                                    "items": p.get("items", []),
                                    "total": p.get("total", 0),
                                    "estado": "Pendiente",
                                    "notas": f"Duplicada de {p.get('numero', '')}. {p.get('notas', '')}".strip(),
                                }
                                if upsert_prefactura(duplicado):
                                    st.toast(f"Pre-factura duplicada: {duplicado['numero']}")
                                    st.rerun()
                                else:
                                    mostrar_error_db("duplicar la pre-factura")
                        with a3:
                            if st.button("Editar", key=f"edit_fac_{pid}", use_container_width=True):
                                st.session_state["fac_editing"] = pid
                                st.rerun()
                        with a4:
                            confirm = st.checkbox("Confirmar", key=f"confirm_del_fac_{pid}")
                        with a5:
                            if st.button("Eliminar", key=f"del_fac_{pid}", use_container_width=True, disabled=not confirm):
                                if delete_prefactura(pid):
                                    st.toast("Pre-factura eliminada.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("eliminar la pre-factura")

                        if st.session_state.get("fac_editing") == pid:
                            st.divider()
                            data = _form_prefactura(p)
                            if data:
                                if upsert_prefactura(data):
                                    st.session_state.pop("fac_editing", None)
                                    st.toast("Pre-factura actualizada.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar la pre-factura")

    with tab2:
        data = _form_prefactura()
        if data:
            if upsert_prefactura(data):
                st.toast("Pre-factura creada.")
                st.rerun()
            else:
                mostrar_error_db("guardar la pre-factura")

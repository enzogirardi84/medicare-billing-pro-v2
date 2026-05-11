"""Vista de Presupuestos."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_presupuesto, get_clientes, get_presupuestos, upsert_prefactura, upsert_presupuesto
from core.excel_export import XLSX_DISPONIBLE, exportar_presupuestos_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_presupuesto_pdf
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda, generar_id, hoy, mostrar_error_db, sanitize_filename

ESTADOS_PRESUPUESTO = ["Borrador", "Enviado", "Aceptado", "Rechazado", "Vencido", "Convertido"]


def _parse_date(value: Any, default: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return default


def _form_presupuesto(existing: Dict[str, Any] | None = None, items_preset: list | None = None) -> Dict[str, Any] | None:
    es_edicion = existing is not None
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    if not cliente_opts:
        st.warning("Primero carga un cliente fiscal para poder crear presupuestos.")
        return None

    base_items = existing.get("items", []) if existing else (items_preset or [])
    form_id = existing.get("id", "new") if existing else "new"
    borrador_key = f"borrador_presupuesto_{form_id}"
    borrador = st.session_state.get(borrador_key, {}) if not es_edicion else {}

    item_count = st.number_input(
        "Cantidad de conceptos",
        min_value=1,
        max_value=20,
        value=min(20, max(1, len(base_items) or borrador.get("item_count", 1) or 1)),
        key=f"pres_item_count_{form_id}",
    )

    # Setear defaults en session_state para widgets con key
    for i in range(int(item_count)):
        base = base_items[i] if i < len(base_items) and isinstance(base_items[i], dict) else {}
        for field, default in [(f"pres_conc_{form_id}_{i}", base.get("concepto", "")),
                                (f"pres_cant_{form_id}_{i}", float(base.get("cantidad", 1) or 1)),
                                (f"pres_precio_{form_id}_{i}", float(base.get("precio_unitario", 0) or 0))]:
            if field not in st.session_state:
                st.session_state[field] = default

    with st.form(f"pres_form_{form_id}", border=True):
        st.markdown(f"### {'Editar presupuesto' if es_edicion else 'Nuevo presupuesto'}")
        c1, c2, c3 = st.columns(3)
        cliente_names = list(cliente_opts.keys())
        with c1:
            default_cliente = existing.get("cliente_nombre", "") if existing else borrador.get("cliente_nombre", "")
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + cliente_names,
                index=cliente_names.index(default_cliente) + 1
                if default_cliente in cliente_opts
                else 0,
            )
        with c2:
            fecha = st.date_input(
                "Fecha",
                value=_parse_date(existing.get("fecha") if existing else borrador.get("fecha", ""), date.today()),
            )
        with c3:
            valido_default = _parse_date(
                existing.get("valido_hasta") if existing else borrador.get("valido_hasta", ""),
                fecha + timedelta(days=15),
            )
            valido = st.date_input("Valido hasta", value=valido_default)

        st.markdown("#### Conceptos")
        items = []
        for i in range(int(item_count)):
            ic1, ic2, ic3, ic4 = st.columns([3, 1, 1.2, 0.7])
            with ic1:
                concepto = st.text_input(
                    "Concepto",
                    key=f"pres_conc_{form_id}_{i}",
                    placeholder="Ej: Consulta cardiologica",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with ic2:
                cantidad = st.number_input(
                    "Cant.",
                    min_value=1.0,
                    step=1.0,
                    key=f"pres_cant_{form_id}_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with ic3:
                precio = st.number_input(
                    "Precio $",
                    min_value=0.0,
                    step=100.0,
                    key=f"pres_precio_{form_id}_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with ic4:
                st.caption(fmt_moneda(cantidad * precio))
            if concepto.strip():
                items.append({"concepto": concepto.strip(), "cantidad": cantidad, "precio_unitario": precio})

        total = sum(float(it["cantidad"]) * float(it["precio_unitario"]) for it in items)
        st.markdown(f"**Total: {fmt_moneda(total)}**")
        notas = st.text_area(
            "Notas",
            value=existing.get("notas", "") if existing else borrador.get("notas", ""),
            height=70,
        )

        sc1, sc2 = st.columns([1, 1])
        with sc1:
            submitted = st.form_submit_button("Guardar presupuesto", use_container_width=True, type="primary")
        with sc2:
            guardar_borrador = st.form_submit_button("💾 Guardar borrador", use_container_width=True)
        if guardar_borrador:
            st.session_state[borrador_key] = {
                "cliente_nombre": cliente_sel,
                "fecha": fecha.isoformat() if fecha else "",
                "valido_hasta": valido.isoformat() if valido else "",
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
            st.session_state.pop(borrador_key, None)
            cliente_data = cliente_opts[cliente_sel]
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "cliente_id": cliente_data.get("id", ""),
                "cliente_nombre": cliente_sel,
                "cliente_dni": cliente_data.get("dni", ""),
                "fecha": fecha.isoformat(),
                "valido_hasta": valido.isoformat(),
                "items": items,
                "total": total,
                "estado": existing.get("estado", "Borrador") if existing else "Borrador",
                "notas": notas.strip(),
            }
    return None


def render_presupuestos() -> None:
    st.markdown("## Presupuestos")
    st.caption("Crea presupuestos profesionales, exportalos y convertilos en pre-facturas.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")

    with st.spinner("Cargando presupuestos..."):
        presupuestos = get_presupuestos(empresa_id)

    _PLANTILLAS_KEY = "presupuesto_plantillas"
    if _PLANTILLAS_KEY not in st.session_state:
        st.session_state[_PLANTILLAS_KEY] = []

    tab1, tab2, tab3 = st.tabs(["Historial", "Nuevo presupuesto", "Plantillas"])

    with tab1:
        if not presupuestos:
            bloque_estado_vacio("Sin presupuestos", "Crea tu primer presupuesto desde la pestaña Nuevo presupuesto.")
        else:
            # Busqueda con boton
            sc1, sc2, sc3 = st.columns([2.5, 0.8, 0.8])
            with sc1:
                busqueda_input = st.text_input(
                    "Buscar",
                    placeholder="Numero o cliente...",
                    key="pres_search_input",
                    value=st.session_state.get("pres_busqueda", ""),
                )
            with sc2:
                if st.button("🔍 Buscar", key="pres_buscar", use_container_width=True):
                    st.session_state["pres_busqueda"] = busqueda_input.strip().lower()
                    st.rerun()
            with sc3:
                if st.session_state.get("pres_busqueda"):
                    if st.button("✕ Limpiar", key="pres_limpiar", use_container_width=True):
                        st.session_state["pres_busqueda"] = ""
                        st.rerun()
                else:
                    st.empty()

            f2, f3, f4 = st.columns([1, 1, 1])
            with f2:
                estado_filtro = st.selectbox("Estado", ["Todos"] + ESTADOS_PRESUPUESTO)
            with f3:
                fecha_desde = st.date_input("Desde", value=None, key="pres_fecha_desde")
            with f4:
                fecha_hasta = st.date_input("Hasta", value=None, key="pres_fecha_hasta")
            busqueda = st.session_state.get("pres_busqueda", "")
            filtrados = presupuestos
            if estado_filtro != "Todos":
                filtrados = [p for p in filtrados if p.get("estado") == estado_filtro]
            if fecha_desde:
                filtrados = [p for p in filtrados if str(p.get("fecha", ""))[:10] >= fecha_desde.isoformat()]
            if fecha_hasta:
                filtrados = [p for p in filtrados if str(p.get("fecha", ""))[:10] <= fecha_hasta.isoformat()]
            if busqueda:
                filtrados = [
                    p
                    for p in filtrados
                    if busqueda in str(p.get("numero", "")).lower()
                    or busqueda in str(p.get("cliente_nombre", "")).lower()
                ]

            st.metric("Total filtrado", fmt_moneda(sum(float(p.get("total", 0) or 0) for p in filtrados)))
            if XLSX_DISPONIBLE and filtrados:
                st.download_button(
                    "Exportar Excel",
                    data=exportar_presupuestos_excel(filtrados, empresa_nombre),
                    file_name=f"presupuestos_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            # Paginacion
            _PAGE_SIZE = 15
            total_pages = max(1, (len(filtrados) + _PAGE_SIZE - 1) // _PAGE_SIZE)
            if len(filtrados) > _PAGE_SIZE:
                pg_cols = st.columns([3, 1])
                with pg_cols[0]:
                    page = st.selectbox("Pagina", options=list(range(1, total_pages + 1)), key="pres_page") - 1
                with pg_cols[1]:
                    st.caption(f"Mostrando {min(_PAGE_SIZE, len(filtrados) - page * _PAGE_SIZE)} de {len(filtrados)}")
            else:
                page = 0
            paginated = filtrados[page * _PAGE_SIZE:(page + 1) * _PAGE_SIZE]

            # Bulk actions
            if paginated:
                ba1, ba2, ba3 = st.columns([1.5, 1.5, 1])
                with ba1:
                    bulk_estado = st.selectbox("Accion masiva", ["—"] + ESTADOS_PRESUPUESTO, key="pres_bulk_estado")
                with ba2:
                    st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
                    if st.button("Aplicar a seleccionados", key="pres_bulk_apply", use_container_width=True, disabled=(bulk_estado == "—")):
                        seleccionados = [p for p in paginated if st.session_state.get(f"sel_pres_{p.get('id')}", False)]
                        if seleccionados:
                            ok_count = 0
                            for p in seleccionados:
                                updated = dict(p)
                                updated["estado"] = bulk_estado
                                if upsert_presupuesto(updated):
                                    ok_count += 1
                            st.toast(f"{ok_count} presupuesto(s) actualizado(s) a {bulk_estado}.")
                            st.rerun()
                        else:
                            st.warning("No seleccionaste ningun presupuesto.")
                with ba3:
                    st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
                    if st.button("Limpiar seleccion", key="pres_bulk_clear", use_container_width=True):
                        for p in paginated:
                            st.session_state[f"sel_pres_{p.get('id')}"] = False
                        st.rerun()

            with st.container(height=610, border=False):
                for p in paginated:
                    pid = p.get("id")
                    with st.container(border=True):

                        st.checkbox("Seleccionar", key=f"sel_pres_{pid}", value=st.session_state.get(f"sel_pres_{pid}", False))
                        c1, c2, c3 = st.columns([3, 1.3, 1.7])

                        with c1:
                            st.markdown(f"**{p.get('numero', '-')}** | {p.get('cliente_nombre', '-')}")
                            st.caption(f"{fmt_fecha(p.get('fecha', ''))} | Vence: {fmt_fecha(p.get('valido_hasta', ''))} | {fmt_moneda(p.get('total', 0))}")
                        with c2:
                            nuevo_estado = st.selectbox(
                                "Estado",
                                ESTADOS_PRESUPUESTO,
                                index=ESTADOS_PRESUPUESTO.index(p.get("estado", "Borrador")) if p.get("estado") in ESTADOS_PRESUPUESTO else 0,
                                key=f"pres_est_{pid}",
                                label_visibility="collapsed",
                            )
                            if nuevo_estado != p.get("estado"):
                                updated = dict(p)
                                updated["estado"] = nuevo_estado
                                if upsert_presupuesto(updated):
                                    st.toast("Estado actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el estado")

                        a1, a2, a3, a4 = st.columns([1.2, 1.2, 1.4, 1.2])
                        with a1:
                            if FPDF_DISPONIBLE:
                                st.download_button(
                                    "Descargar PDF",
                                    data=exportar_presupuesto_pdf(p, empresa_nombre, p.get("items", [])),
                                    file_name=f"presupuesto_{sanitize_filename(p.get('numero', ''))}.pdf",
                                    mime="application/pdf",
                                    key=f"pdf_pres_{pid}",
                                    use_container_width=True,
                                )
                        with a2:
                            if st.button("Editar", key=f"edit_pres_{pid}", use_container_width=True):
                                st.session_state["pres_editing"] = pid
                                st.rerun()
                        with a3:
                            confirm = st.checkbox("Confirmar borrado", key=f"confirm_del_pres_{pid}")
                        with a4:
                            if st.button("Eliminar", key=f"del_pres_{pid}", use_container_width=True, disabled=not confirm):
                                if delete_presupuesto(pid):
                                    st.toast("Presupuesto eliminado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("eliminar el presupuesto")

                        if p.get("estado") == "Aceptado":
                            if st.button("Convertir a pre-factura", key=f"conv_pres_{pid}", use_container_width=True):
                                from datetime import timedelta
                                prefactura_data = {
                                    "id": generar_id(),
                                    "empresa_id": empresa_id,
                                    "numero": generar_numero_formal(empresa_id, "PREF", 1, "PREF"),
                                    "cliente_id": p.get("cliente_id", ""),
                                    "cliente_nombre": p.get("cliente_nombre", ""),
                                    "cliente_dni": p.get("cliente_dni", ""),
                                    "fecha": hoy().isoformat(),
                                    "vencimiento": (hoy() + timedelta(days=30)).isoformat(),
                                    "items": p.get("items", []),
                                    "total": p.get("total", 0),
                                    "estado": "Pendiente",
                                    "presupuesto_origen": pid,
                                    "notas": p.get("notas", ""),
                                }
                                converted = dict(p)
                                converted["estado"] = "Convertido"
                                if upsert_prefactura(prefactura_data) and upsert_presupuesto(converted):
                                    st.toast("Pre-factura generada.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("convertir el presupuesto")

                        if st.session_state.get("pres_editing") == pid:
                            st.divider()
                            data = _form_presupuesto(p)
                            if data:
                                if upsert_presupuesto(data):
                                    st.session_state.pop("pres_editing", None)
                                    st.toast("Presupuesto actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el presupuesto")

    with tab2:
        plantillas = st.session_state.get(_PLANTILLAS_KEY, [])
        if plantillas:
            nombres = [p.get("nombre", "") for p in plantillas]
            colp1, colp2 = st.columns([2, 1])
            with colp1:
                sel = st.selectbox("Cargar plantilla", ["—"] + nombres, key="pres_plantilla_sel")
            with colp2:
                st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
                if sel != "—":
                    if st.button("Cargar", key="pres_plantilla_load_btn", use_container_width=True):
                        st.session_state["pres_plantilla_cargar"] = sel
                        st.rerun()
        plantilla_items = []
        if st.session_state.get("pres_plantilla_cargar"):
            sel_name = st.session_state.pop("pres_plantilla_cargar")
            for pl in plantillas:
                if pl.get("nombre") == sel_name:
                    plantilla_items = pl.get("items", [])
                    break
            if plantilla_items:
                st.info(f"Plantilla '{sel_name}' cargada.")
        data = _form_presupuesto(items_preset=plantilla_items)
        if data:
            if upsert_presupuesto(data):
                st.toast("Presupuesto creado.")
                st.rerun()
            else:
                mostrar_error_db("guardar el presupuesto")

    with tab3:
        st.markdown("### Plantillas de presupuestos")
        st.caption("Guarda conjuntos de conceptos reutilizables.")
        plantillas = st.session_state.get(_PLANTILLAS_KEY, [])
        if not plantillas:
            st.info("No hay plantillas guardadas.")
        else:
            for i, pl in enumerate(plantillas):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{pl.get('nombre', 'Sin nombre')}**")
                        items_str = " | ".join(f"{it.get('concepto', '')} (${it.get('precio_unitario', 0)})" for it in pl.get("items", []))
                        st.caption(items_str[:120] + ("..." if len(items_str) > 120 else ""))
                    with c2:
                        if st.button("Eliminar", key=f"del_plantilla_{i}", use_container_width=True):
                            st.session_state[_PLANTILLAS_KEY].pop(i)
                            st.rerun()
        st.divider()
        st.markdown("#### Guardar nueva plantilla")
        if presupuestos:
            opts = {p.get("numero", "") + " - " + p.get("cliente_nombre", ""): p for p in presupuestos}
            sel_pres = st.selectbox("Seleccionar presupuesto", ["—"] + list(opts.keys()), key="pres_save_plantilla_sel")
            nombre_pl = st.text_input("Nombre de la plantilla", placeholder="Ej: Consulta cardiologica completa", key="pres_save_plantilla_nombre")
            if st.button("Guardar como plantilla", key="pres_save_plantilla_btn", disabled=(sel_pres == "—" or not nombre_pl.strip())):
                p = opts[sel_pres]
                st.session_state[_PLANTILLAS_KEY].append({
                    "nombre": nombre_pl.strip(),
                    "items": p.get("items", []),
                })
                st.toast(f"Plantilla '{nombre_pl.strip()}' guardada.")
                st.rerun()
        else:
            st.caption("Crea un presupuesto primero.")

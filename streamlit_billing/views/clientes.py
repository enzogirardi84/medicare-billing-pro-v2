"""Vista de Clientes Fiscales."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_cliente, get_clientes, get_cobros, get_prefacturas, get_presupuestos, upsert_cliente
from core.excel_export import XLSX_DISPONIBLE, exportar_clientes_excel
from core.billing_logic import enriquecer_prefacturas_con_saldo, money
from core.utils import (
    bloque_estado_vacio,
    fmt_moneda,
    fmt_moneda_corto,
    generar_id,
    is_valid_email,
    mostrar_error_db,
    normalize_document,
    normalize_phone,
    sanitize_filename,
    validar_cuit,
)

CONDICIONES_FISCALES = [
    "Responsable Inscripto",
    "Monotributista",
    "Exento",
    "Consumidor Final",
    "No Categorizado",
]


def _form_cliente(existing: Dict[str, Any] | None = None, clientes: list[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    es_edicion = existing is not None
    form_key = existing.get("id", "new") if existing else "new"
    borrador_key = f"borrador_cliente_{form_key}"
    borrador = st.session_state.get(borrador_key, {}) if not es_edicion else {}

    def _v(field: str, default: str = "") -> str:
        if es_edicion:
            return existing.get(field, default)  # type: ignore[union-attr]
        return borrador.get(field, default)

    with st.form(f"cliente_form_{form_key}", border=True):
        st.markdown(f"### {'Editar cliente' if es_edicion else 'Nuevo cliente'}")
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre / Razon Social *", value=_v("nombre"))
            dni = st.text_input("DNI / CUIT *", value=_v("dni"))
            email = st.text_input("Email", value=_v("email"))
        with c2:
            telefono = st.text_input("Telefono", value=_v("telefono"))
            direccion = st.text_input("Direccion", value=_v("direccion"))
            default_cond = _v("condicion_fiscal", "Consumidor Final")
            condicion = st.selectbox(
                "Condicion Fiscal",
                options=CONDICIONES_FISCALES,
                index=CONDICIONES_FISCALES.index(default_cond) if default_cond in CONDICIONES_FISCALES else 3,
            )
        notas = st.text_area("Notas", value=_v("notas"), height=74)

        sc1, sc2 = st.columns([1, 1])
        with sc1:
            submitted = st.form_submit_button("Guardar cliente", use_container_width=True, type="primary")
        with sc2:
            guardar_borrador = st.form_submit_button("💾 Guardar borrador", use_container_width=True)
        if guardar_borrador:
            st.session_state[borrador_key] = {
                "nombre": nombre,
                "dni": dni,
                "email": email,
                "telefono": telefono,
                "direccion": direccion,
                "condicion_fiscal": condicion,
                "notas": notas,
            }
            st.toast("Borrador guardado.")
            st.rerun()
        if submitted:
            nombre = nombre.strip()
            dni = normalize_document(dni)
            email = email.strip().lower()
            if not nombre or not dni:
                st.error("Nombre y DNI/CUIT son obligatorios.")
                return {}
            if not is_valid_email(email):
                st.error("El email no tiene un formato valido.")
                return {}
            if len(re.sub(r"[^0-9]", "", dni)) == 11:
                ok, msg = validar_cuit(dni)
                if not ok:
                    st.error(f"CUIT/CUIL invalido: {msg}")
                    return {}
            duplicado = next(
                (
                    c
                    for c in clientes or []
                    if normalize_document(c.get("dni", "")) == dni
                    and str(c.get("id", "")) != str(existing.get("id", "") if existing else "")
                ),
                None,
            )
            if duplicado:
                st.error(f"Ya existe un cliente con ese DNI/CUIT: {duplicado.get('nombre', '')}.")
                return {}
            st.session_state.pop(borrador_key, None)
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "nombre": nombre,
                "dni": dni,
                "email": email,
                "telefono": normalize_phone(telefono),
                "direccion": direccion.strip(),
                "condicion_fiscal": condicion,
                "notas": notas.strip(),
            }
    return {}


def render_clientes() -> None:
    st.markdown("## Clientes fiscales")
    st.caption("Datos impositivos de pacientes, obras sociales y terceros.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")

    with st.spinner("Cargando clientes..."):
        clientes = get_clientes(empresa_id)
        presupuestos = get_presupuestos(empresa_id)
        cobros = get_cobros(empresa_id)
        prefacturas = enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), cobros)

    tab1, tab2 = st.tabs(["Listado", "Nuevo cliente"])

    with tab1:
        if not clientes:
            bloque_estado_vacio(
                "Sin clientes cargados",
                "Todavia no registraste ningun cliente fiscal. Usa la pestaña Nuevo cliente para agregar el primero.",
                "Luego vas a poder usarlos en presupuestos, pre-facturas y cobros.",
            )
        else:
            # Busqueda con boton (no filtra en cada tecla para mejor performance)
            sc1, sc2, sc3 = st.columns([2.5, 0.8, 0.8])
            with sc1:
                busqueda_input = st.text_input(
                    "Buscar cliente",
                    placeholder="Nombre, DNI/CUIT, email o telefono...",
                    key="cli_search_input",
                    value=st.session_state.get("cli_busqueda", ""),
                )
            with sc2:
                if st.button("🔍 Buscar", key="cli_buscar", use_container_width=True):
                    st.session_state["cli_busqueda"] = busqueda_input.strip().lower()
                    st.rerun()
            with sc3:
                if st.session_state.get("cli_busqueda"):
                    if st.button("✕ Limpiar", key="cli_limpiar", use_container_width=True):
                        st.session_state["cli_busqueda"] = ""
                        st.rerun()
                else:
                    st.empty()

            busqueda = st.session_state.get("cli_busqueda", "")
            filtrados = clientes
            if busqueda:
                filtrados = [
                    c
                    for c in clientes
                    if busqueda in str(c.get("nombre", "")).lower()
                    or busqueda in str(c.get("dni", "")).lower()
                    or busqueda in str(c.get("email", "")).lower()
                    or busqueda in str(c.get("telefono", "")).lower()
                ]
            st.metric("Clientes", len(filtrados))

            if XLSX_DISPONIBLE and filtrados:
                excel_data = exportar_clientes_excel(filtrados, empresa_nombre)
                st.download_button(
                    "Exportar Excel",
                    data=excel_data,
                    file_name=f"clientes_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            # Paginacion para soportar grandes volumenes
            _PAGE_SIZE = 20
            total_pages = max(1, (len(filtrados) + _PAGE_SIZE - 1) // _PAGE_SIZE)
            if len(filtrados) > _PAGE_SIZE:
                pg_cols = st.columns([3, 1])
                with pg_cols[0]:
                    page = st.selectbox("Pagina", options=list(range(1, total_pages + 1)), key="clientes_page") - 1
                with pg_cols[1]:
                    st.caption(f"Mostrando {min(_PAGE_SIZE, len(filtrados) - page * _PAGE_SIZE)} de {len(filtrados)}")
            else:
                page = 0

            paginated = filtrados[page * _PAGE_SIZE:(page + 1) * _PAGE_SIZE]

            with st.container(height=610, border=False):
                for cliente in paginated:
                    cliente_id = cliente.get("id")
                    with st.container(border=True):
                        c1, c2 = st.columns([4.2, 1.4])
                        with c1:
                            st.markdown(f"**{cliente.get('nombre', 'Sin nombre')}**")
                            st.caption(f"DNI/CUIT: {cliente.get('dni', '-')} | {cliente.get('condicion_fiscal', '-')}")
                            contacto = " | ".join(v for v in [cliente.get("email", ""), cliente.get("telefono", "")] if v)
                            if contacto:
                                st.caption(contacto)
                            cli_pres = [p for p in presupuestos if str(p.get("cliente_id", "")) == str(cliente_id)]
                            cli_pref = [p for p in prefacturas if str(p.get("cliente_id", "")) == str(cliente_id)]
                            cli_cobros = [c for c in cobros if str(c.get("cliente_id", "")) == str(cliente_id)]
                            with st.expander("Historial y saldo", expanded=False):
                                h1, h2, h3, h4 = st.columns(4)
                                pres_total = sum(money(p.get("total")) for p in cli_pres)
                                pref_total = sum(money(p.get("total")) for p in cli_pref)
                                cob_total = sum(money(c.get("monto")) for c in cli_cobros)
                                saldo_total = sum(money(p.get("saldo")) for p in cli_pref)
                                h1.metric("Presupuestado", fmt_moneda_corto(pres_total), help=fmt_moneda(pres_total))
                                h2.metric("Pre-facturado", fmt_moneda_corto(pref_total), help=fmt_moneda(pref_total))
                                h3.metric("Cobrado", fmt_moneda_corto(cob_total), help=fmt_moneda(cob_total))
                                h4.metric("Saldo", fmt_moneda_corto(saldo_total), help=fmt_moneda(saldo_total))
                                ultimos = sorted(
                                    [
                                        {"Fecha": p.get("fecha", ""), "Tipo": "Presupuesto", "Numero": p.get("numero", ""), "Monto": fmt_moneda(p.get("total", 0))}
                                        for p in cli_pres
                                    ]
                                    + [
                                        {"Fecha": p.get("fecha", ""), "Tipo": "Pre-factura", "Numero": p.get("numero", ""), "Monto": fmt_moneda(p.get("total", 0))}
                                        for p in cli_pref
                                    ]
                                    + [
                                        {"Fecha": c.get("fecha", ""), "Tipo": "Cobro", "Numero": c.get("concepto", ""), "Monto": fmt_moneda(c.get("monto", 0))}
                                        for c in cli_cobros
                                    ],
                                    key=lambda row: str(row.get("Fecha", "")),
                                    reverse=True,
                                )[:6]
                                if ultimos:
                                    st.dataframe(ultimos, use_container_width=True, hide_index=True, height=210)
                                else:
                                    st.caption("Sin movimientos todavia.")
                        with c2:
                            saldo_cliente = sum(money(p.get("saldo")) for p in cli_pref)
                            st.metric("Saldo", fmt_moneda(saldo_cliente))
                            # Saldo vencido
                            def _es_vencida(vencimiento):
                                try:
                                    return date.fromisoformat(str(vencimiento)[:10]) < date.today()
                                except Exception:
                                    return False

                            vencidas = [
                                p for p in cli_pref
                                if str(p.get("estado", "")) in ("Pendiente", "Parcial")
                                and str(p.get("vencimiento", ""))[:10]
                                and _es_vencida(p.get("vencimiento"))
                            ]
                            if vencidas:
                                monto_vencido = sum(money(p.get("saldo")) for p in vencidas)
                                st.error(f"⚠️ {len(vencidas)} vencida(s): {fmt_moneda(monto_vencido)}")

                        a1, a2, a3, a4, a5, a6 = st.columns([1.2, 1.2, 1.2, 1.1, 1.5, 1.1])
                        with a1:
                            if st.button("Presupuesto", key=f"pres_cli_{cliente_id}", use_container_width=True):
                                st.session_state["borrador_presupuesto_new"] = {"cliente_nombre": cliente.get("nombre", "")}
                                st.session_state["billing_modulo_activo"] = "Presupuestos"
                                st.rerun()
                        with a2:
                            if st.button("Pre-factura", key=f"fac_cli_{cliente_id}", use_container_width=True):
                                st.session_state["borrador_prefactura_new"] = {"cliente_nombre": cliente.get("nombre", "")}
                                st.session_state["billing_modulo_activo"] = "Pre-facturas"
                                st.rerun()
                        with a3:
                            if st.button("Cuenta", key=f"cc_cli_{cliente_id}", use_container_width=True):
                                st.session_state["cc_cliente_label"] = (
                                    f"{cliente.get('nombre', 'Sin nombre')} | {cliente.get('dni', '')}"
                                    if cliente.get("dni")
                                    else cliente.get("nombre", "Sin nombre")
                                )
                                st.session_state["billing_modulo_activo"] = "Cuenta corriente"
                                st.rerun()
                        with a4:
                            if st.button("Editar", key=f"edit_cli_{cliente_id}", use_container_width=True):
                                st.session_state["cli_editing"] = cliente_id
                                st.rerun()
                        with a5:
                            confirmar = st.checkbox("Confirmar borrado", key=f"confirm_del_cli_{cliente_id}")
                        with a6:
                            if st.button("Eliminar", key=f"del_cli_{cliente_id}", use_container_width=True, disabled=not confirmar):
                                if delete_cliente(cliente_id):
                                    st.toast("Cliente eliminado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("eliminar el cliente")

                        if st.session_state.get("cli_editing") == cliente_id:
                            st.divider()
                            data = _form_cliente(cliente, clientes)
                            if data:
                                if upsert_cliente(data):
                                    st.session_state.pop("cli_editing", None)
                                    st.toast("Cliente actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el cliente")

    with tab2:
        data = _form_cliente(clientes=clientes)
        if data:
            result = upsert_cliente(data)
            if result:
                st.toast("Cliente creado correctamente.")
                st.rerun()
            else:
                mostrar_error_db("guardar el cliente")

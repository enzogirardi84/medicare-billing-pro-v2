"""Vista de Cobros."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_cobro, get_clientes, get_cobros, get_prefacturas, upsert_cobro, upsert_prefactura
from core.excel_export import XLSX_DISPONIBLE, exportar_cobros_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_recibo_cobro_pdf, exportar_reporte_cobros_pdf
from core.billing_logic import (
    estado_prefactura_por_saldo,
    enriquecer_prefacturas_con_saldo,
    prefacturas_con_saldo,
    saldo_prefactura,
)
from core.utils import agrupar_por_mes, bloque_estado_vacio, calcular_total, fmt_fecha, fmt_moneda, generar_id, mostrar_error_db, sanitize_filename

METODOS_PAGO = ["Efectivo", "Transferencia", "Tarjeta de Credito", "Tarjeta de Debito", "Cheque", "Mercado Pago", "Otro"]
ESTADOS_COBRO = ["Cobrado", "Pendiente", "Parcial", "Anulado"]


def _parse_date(value: Any, default: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return default


def _sync_prefactura(prefactura_id: str) -> bool:
    if not prefactura_id:
        return True
    empresa_id = st.session_state.get("billing_empresa_id", "")
    prefacturas = get_prefacturas(empresa_id)
    cobros = get_cobros(empresa_id)
    prefactura = next((p for p in prefacturas if str(p.get("id", "")) == str(prefactura_id)), None)
    if not prefactura:
        return True
    updated = dict(prefactura)
    updated["estado"] = estado_prefactura_por_saldo(prefactura, cobros)
    return bool(upsert_prefactura(updated))


def _form_cobro(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    es_edicion = existing is not None
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    if not cliente_opts:
        st.warning("Primero carga un cliente fiscal para registrar cobros.")
        return None

    empresa_id = st.session_state.get("billing_empresa_id", "")
    prefacturas = get_prefacturas(empresa_id)
    cobros = get_cobros(empresa_id)
    prefacturas_pendientes = prefacturas_con_saldo(prefacturas, cobros)
    form_id = existing.get("id", "new") if existing else "new"
    borrador_key = f"borrador_cobro_{form_id}"
    borrador = st.session_state.get(borrador_key, {}) if not es_edicion else {}

    # Pre-factura pre-seleccionada desde otro modulo (ej: boton Cobrar en pre-facturas)
    preseleccion = st.session_state.pop("cobro_prefactura_preseleccionada", None)
    if preseleccion and not es_edicion:
        prefac = next(
            (p for p in prefacturas_pendientes if str(p.get("id")) == str(preseleccion.get("id"))),
            None,
        )
        if prefac:
            borrador = {
                **borrador,
                "cliente_nombre": prefac.get("cliente_nombre", ""),
                "concepto": f"Pago {prefac.get('numero', '')}",
                "monto": str(prefac.get("saldo", 0)),
                "prefactura_id": str(prefac.get("id", "")),
            }

    def _v(field: str, default: str = "") -> str:
        if es_edicion:
            return existing.get(field, default)  # type: ignore[union-attr]
        return borrador.get(field, default)

    with st.form(f"cobro_form_{form_id}", border=True):
        st.markdown(f"### {'Editar cobro' if existing else 'Nuevo cobro'}")
        c1, c2 = st.columns(2)
        names = list(cliente_opts.keys())
        with c1:
            default_cliente = _v("cliente_nombre")
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + names,
                index=names.index(default_cliente) + 1
                if default_cliente in cliente_opts
                else 0,
            )
        with c2:
            fecha = st.date_input("Fecha de cobro", value=_parse_date(_v("fecha"), date.today()))

        c3, c4 = st.columns(2)
        with c3:
            monto = st.number_input("Monto $ *", min_value=0.0, value=float(_v("monto", "0") or 0), step=100.0)
        with c4:
            default_metodo = _v("metodo_pago", "Efectivo")
            metodo = st.selectbox(
                "Metodo de pago",
                METODOS_PAGO,
                index=METODOS_PAGO.index(default_metodo) if default_metodo in METODOS_PAGO else 0,
            )

        concepto = st.text_input("Concepto", value=_v("concepto"), placeholder="Ej: Pago honorarios marzo 2026")
        # Incluir pre-factura vinculada actual (si existe) aunque ya no este pendiente
        fac_linked_id = str(existing.get("prefactura_id", "")) if existing else str(borrador.get("prefactura_id", ""))
        fac_linked = next((p for p in prefacturas if str(p.get("id")) == fac_linked_id), None)
        fac_opts = {
            (
                f"{p.get('numero', '')} | {p.get('cliente_nombre', '')} | "
                f"Saldo {fmt_moneda(p.get('saldo', 0))}"
            ): p
            for p in prefacturas_pendientes
        }
        if fac_linked and fac_linked_id not in {str(p.get("id")) for p in prefacturas_pendientes}:
            fac_opts[f"{fac_linked.get('numero', '')} | {fac_linked.get('cliente_nombre', '')} | Saldo {fmt_moneda(fac_linked.get('saldo', 0))} (vinculada)"] = fac_linked
        fac_keys = ["Ninguna"] + list(fac_opts.keys())
        default_fac = 0
        if existing and fac_linked:
            linked_label = f"{fac_linked.get('numero', '')} | {fac_linked.get('cliente_nombre', '')} | Saldo {fmt_moneda(fac_linked.get('saldo', 0))} (vinculada)"
            if linked_label in fac_keys:
                default_fac = fac_keys.index(linked_label)
            elif fac_linked in fac_opts.values():
                for k, v in fac_opts.items():
                    if str(v.get("id")) == fac_linked_id:
                        default_fac = fac_keys.index(k)
                        break
        fac_sel = st.selectbox("Vincular a pre-factura (opcional)", options=fac_keys, index=default_fac) if fac_opts else "Ninguna"
        if fac_sel != "Ninguna":
            fac_preview = fac_opts.get(fac_sel, {})
            st.caption(
                "Total: "
                f"{fmt_moneda(fac_preview.get('total', 0))} | "
                f"Cobrado: {fmt_moneda(fac_preview.get('cobrado', 0))} | "
                f"Saldo: {fmt_moneda(fac_preview.get('saldo', 0))}"
            )
        notas = st.text_area("Notas", value=_v("notas"), height=70)

        sc1, sc2 = st.columns([1, 1])
        with sc1:
            submitted = st.form_submit_button("Guardar cobro", use_container_width=True, type="primary")
        with sc2:
            guardar_borrador = st.form_submit_button("💾 Guardar borrador", use_container_width=True)
        if guardar_borrador:
            fac_data = fac_opts.get(fac_sel, {}) if fac_sel != "Ninguna" else {}
            st.session_state[borrador_key] = {
                "cliente_nombre": cliente_sel,
                "fecha": fecha.isoformat() if fecha else "",
                "monto": str(monto),
                "metodo_pago": metodo,
                "concepto": concepto,
                "notas": notas,
                "prefactura_id": str(fac_data.get("id", "")) if fac_data else "",
            }
            st.toast("Borrador guardado.")
            st.rerun()
        if submitted:
            if not cliente_sel:
                st.error("Selecciona un cliente.")
                return None
            if monto <= 0:
                st.error("El monto debe ser mayor a cero.")
                return None
            st.session_state.pop(borrador_key, None)
            cliente_data = cliente_opts.get(cliente_sel, {})
            data = {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "cliente_id": cliente_data.get("id", ""),
                "cliente_nombre": cliente_sel,
                "fecha": fecha.isoformat(),
                "monto": monto,
                "metodo_pago": metodo,
                "concepto": concepto.strip() or "Cobro",
                "estado": existing.get("estado", "Cobrado") if existing else "Cobrado",
                "notas": notas.strip(),
            }
            if fac_sel != "Ninguna":
                fac_data = dict(fac_opts.get(fac_sel, {}))
                if fac_data:
                    cobros_sin_actual = [c for c in cobros if str(c.get("id")) != str(data.get("id"))]
                    saldo = saldo_prefactura(fac_data, cobros_sin_actual)
                    if monto - saldo > 0.01:
                        st.error(f"El monto supera el saldo de la pre-factura ({fmt_moneda(saldo)}).")
                        return None
                    data["prefactura_id"] = fac_data.get("id")
                    projected_cobros = cobros_sin_actual + [data]
                    fac_data["estado"] = estado_prefactura_por_saldo(fac_data, projected_cobros)
                    if not upsert_prefactura(fac_data):
                        mostrar_error_db("actualizar la pre-factura vinculada")
                        return None
            return data
    return None


def render_cobros() -> None:
    st.markdown("## Cobros")
    st.caption("Registra pagos recibidos y mantiene trazabilidad por cliente, metodo y mes.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")

    with st.spinner("Cargando cobros..."):
        cobros = get_cobros(empresa_id)
        prefacturas_por_id = {
            str(p.get("id", "")): p
            for p in enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), cobros)
        }

    tab1, tab2 = st.tabs(["Historial", "Nuevo cobro"])

    with tab1:
        if not cobros:
            bloque_estado_vacio("Sin cobros registrados", "Registra tu primer cobro desde la pestaña Nuevo cobro.")
        else:
            # Busqueda con boton
            sc1, sc2, sc3 = st.columns([2.5, 0.8, 0.8])
            with sc1:
                busqueda_input = st.text_input(
                    "Buscar",
                    placeholder="Cliente o concepto...",
                    key="cob_search_input",
                    value=st.session_state.get("cob_busqueda", ""),
                )
            with sc2:
                if st.button("🔍 Buscar", key="cob_buscar", use_container_width=True):
                    st.session_state["cob_busqueda"] = busqueda_input.strip().lower()
                    st.rerun()
            with sc3:
                if st.session_state.get("cob_busqueda"):
                    if st.button("✕ Limpiar", key="cob_limpiar", use_container_width=True):
                        st.session_state["cob_busqueda"] = ""
                        st.rerun()
                else:
                    st.empty()

            cf1, cf2, cf4, cf5 = st.columns([1, 1, 1, 1])
            with cf1:
                metodo_filtro = st.selectbox("Metodo", ["Todos"] + METODOS_PAGO)
            with cf2:
                estado_filtro = st.selectbox("Estado", ["Todos"] + ESTADOS_COBRO)
            with cf4:
                fecha_desde = st.date_input("Desde", value=None, key="cob_fecha_desde")
            with cf5:
                fecha_hasta = st.date_input("Hasta", value=None, key="cob_fecha_hasta")

            busqueda = st.session_state.get("cob_busqueda", "")
            filtrados = cobros
            if metodo_filtro != "Todos":
                filtrados = [c for c in filtrados if c.get("metodo_pago") == metodo_filtro]
            if estado_filtro != "Todos":
                filtrados = [c for c in filtrados if c.get("estado") == estado_filtro]
            if fecha_desde:
                filtrados = [c for c in filtrados if str(c.get("fecha", ""))[:10] >= fecha_desde.isoformat()]
            if fecha_hasta:
                filtrados = [c for c in filtrados if str(c.get("fecha", ""))[:10] <= fecha_hasta.isoformat()]
            if busqueda:
                filtrados = [
                    c for c in filtrados
                    if busqueda in str(c.get("cliente_nombre", "")).lower()
                    or busqueda in str(c.get("concepto", "")).lower()
                ]

            total_cobrado = calcular_total(filtrados, "monto")
            st.metric("Total cobrado", fmt_moneda(total_cobrado))
            if XLSX_DISPONIBLE and filtrados:
                st.download_button(
                    "Exportar Excel",
                    data=exportar_cobros_excel(filtrados, empresa_nombre),
                    file_name=f"cobros_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            agrupados = agrupar_por_mes(filtrados)
            with st.container(height=650, border=False):
                for mes, items in agrupados.items():
                    mes_total = calcular_total(items, "monto")
                    with st.expander(f"{mes} | {len(items)} cobro(s) | {fmt_moneda(mes_total)}", expanded=len(agrupados) <= 2):
                        if FPDF_DISPONIBLE:
                            st.download_button(
                                "PDF del mes",
                                data=exportar_reporte_cobros_pdf(items, empresa_nombre, f"{mes}-01", f"{mes}-31"),
                                file_name=f"cobros_{sanitize_filename(mes)}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"pdf_cob_mes_{mes}",
                            )
                        for cobro in items:
                            cid = cobro.get("id")
                            with st.container(border=True):
                                cc1, cc2 = st.columns([4.2, 1.4])
                                with cc1:
                                    st.markdown(f"**{cobro.get('cliente_nombre', '-')}** | {fmt_moneda(cobro.get('monto', 0))}")
                                    st.caption(f"{fmt_fecha(cobro.get('fecha', ''))} | {cobro.get('metodo_pago', '')} | {cobro.get('concepto', '-')}")
                                    if cobro.get("prefactura_id"):
                                        pref = prefacturas_por_id.get(str(cobro.get("prefactura_id", "")), {})
                                        st.caption(f"Pre-factura vinculada: {pref.get('numero', cobro.get('prefactura_id'))}")
                                with cc2:
                                    nuevo_estado = st.selectbox(
                                        "Estado",
                                        ESTADOS_COBRO,
                                        index=ESTADOS_COBRO.index(cobro.get("estado", "Cobrado")) if cobro.get("estado") in ESTADOS_COBRO else 0,
                                        key=f"cob_est_{cid}",
                                        label_visibility="collapsed",
                                    )
                                    if nuevo_estado != cobro.get("estado"):
                                        updated = dict(cobro)
                                        updated["estado"] = nuevo_estado
                                        if upsert_cobro(updated):
                                            if updated.get("prefactura_id") and not _sync_prefactura(updated.get("prefactura_id", "")):
                                                mostrar_error_db("recalcular la pre-factura vinculada")
                                            else:
                                                st.toast("Estado actualizado.")
                                                st.rerun()
                                        else:
                                            mostrar_error_db("actualizar el cobro")
                                a1, a2, a3 = st.columns([1.25, 1.5, 1.1])
                                with a1:
                                    pref = prefacturas_por_id.get(str(cobro.get("prefactura_id", "")), {})
                                    if FPDF_DISPONIBLE:
                                        st.download_button(
                                            "Recibo PDF",
                                            data=exportar_recibo_cobro_pdf(
                                                cobro,
                                                empresa_nombre,
                                                pref,
                                                float(pref.get("saldo", 0) or 0) if pref else 0,
                                            ),
                                            file_name=f"recibo_{sanitize_filename(str(cid))}.pdf",
                                            mime="application/pdf",
                                            key=f"pdf_recibo_{cid}",
                                            use_container_width=True,
                                        )
                                with a2:
                                    confirm = st.checkbox("Confirmar borrado", key=f"confirm_del_cob_{cid}")
                                with a3:
                                    if st.button("Eliminar", key=f"del_cob_{cid}", use_container_width=True, disabled=not confirm):
                                        prefactura_id = cobro.get("prefactura_id", "")
                                        if delete_cobro(cid):
                                            if prefactura_id and not _sync_prefactura(prefactura_id):
                                                mostrar_error_db("recalcular la pre-factura vinculada")
                                            else:
                                                st.toast("Cobro eliminado.")
                                                st.rerun()
                                        else:
                                            mostrar_error_db("eliminar el cobro")

    with tab2:
        data = _form_cobro()
        if data:
            if upsert_cobro(data):
                st.toast("Cobro registrado.")
                st.rerun()
            else:
                mostrar_error_db("guardar el cobro")

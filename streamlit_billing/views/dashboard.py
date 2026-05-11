"""Dashboard ejecutivo de Medicare Billing Pro."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
from typing import Any, Dict, List
import time

import streamlit as st


def _parse_date(value: Any, default: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return default

from core.db_sql import get_clientes, get_cobros, get_prefacturas, get_presupuestos
from core.billing_logic import enriquecer_prefacturas_con_saldo, prefacturas_con_saldo, total_saldo_prefacturas
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda


MESES_ES = {
    "01": "enero",
    "02": "febrero",
    "03": "marzo",
    "04": "abril",
    "05": "mayo",
    "06": "junio",
    "07": "julio",
    "08": "agosto",
    "09": "septiembre",
    "10": "octubre",
    "11": "noviembre",
    "12": "diciembre",
}


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _month_label(month_key: str) -> str:
    if len(str(month_key)) < 7 or "-" not in str(month_key):
        return str(month_key or "-")
    year, month = month_key.split("-")
    return f"{MESES_ES.get(month, month).capitalize()} {year}"


def _set_module(label: str) -> None:
    st.session_state["billing_modulo_activo"] = label
    st.rerun()


def _total_prefacturas(prefacturas: List[Dict[str, Any]]) -> float:
    return sum(_money(p.get("total")) for p in prefacturas)


def _estado(value: Any) -> str:
    return str(value or "").strip().lower()


def _recent_activity(
    presupuestos: List[Dict[str, Any]],
    prefacturas: List[Dict[str, Any]],
    cobros: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in presupuestos:
        rows.append(
            {
                "fecha": str(item.get("fecha") or item.get("created_at") or "")[:10],
                "tipo": "Presupuesto",
                "cliente": item.get("cliente_nombre", ""),
                "detalle": item.get("numero", ""),
                "importe": _money(item.get("total")),
            }
        )
    for item in prefacturas:
        rows.append(
            {
                "fecha": str(item.get("fecha") or item.get("created_at") or "")[:10],
                "tipo": "Pre-factura",
                "cliente": item.get("cliente_nombre", ""),
                "detalle": item.get("numero", ""),
                "importe": _money(item.get("total")),
            }
        )
    for item in cobros:
        rows.append(
            {
                "fecha": str(item.get("fecha") or item.get("created_at") or "")[:10],
                "tipo": "Cobro",
                "cliente": item.get("cliente_nombre", ""),
                "detalle": item.get("medio_pago", ""),
                "importe": _money(item.get("monto")),
            }
        )
    return sorted(rows, key=lambda r: r.get("fecha") or "", reverse=True)[:30]


def render_dashboard() -> None:
    empresa_id = st.session_state.get("billing_empresa_id", "")

    # Reusar cache de billing_app.py si existe (misma empresa)
    _cache_key = f"billing_cache_{empresa_id}"
    _cache_ts_key = "billing_cache_ts"
    if _cache_key in st.session_state and _cache_ts_key in st.session_state:
        cached = st.session_state[_cache_key]
        clientes = cached.get("clientes", [])
        presupuestos = cached.get("presupuestos", [])
        prefacturas_raw = cached.get("prefacturas", [])
        cobros = cached.get("cobros", [])
    else:
        clientes = get_clientes(empresa_id)
        presupuestos = get_presupuestos(empresa_id)
        prefacturas_raw = get_prefacturas(empresa_id)
        cobros = get_cobros(empresa_id)

    prefacturas = enriquecer_prefacturas_con_saldo(prefacturas_raw, cobros)

    current_month = date.today().strftime("%Y-%m")
    cobros_mes = [c for c in cobros if str(c.get("fecha", ""))[:7] == current_month]
    prefacturas_mes = [p for p in prefacturas if str(p.get("fecha", ""))[:7] == current_month]
    prefacturas_pendientes = prefacturas_con_saldo(prefacturas_raw, cobros)
    presupuestos_abiertos = [
        p for p in presupuestos if _estado(p.get("estado")) in {"borrador", "enviado", "pendiente"}
    ]
    presupuestos_aceptados = [
        p for p in presupuestos if _estado(p.get("estado")) in {"aceptado", "convertido"}
    ]

    total_cobrado_mes = sum(_money(c.get("monto")) for c in cobros_mes)
    total_prefacturado_mes = _total_prefacturas(prefacturas_mes)
    total_pendiente = total_saldo_prefacturas(prefacturas_raw, cobros)
    conversion = (len(presupuestos_aceptados) / len(presupuestos) * 100) if presupuestos else 0
    cumplimiento = min(total_cobrado_mes / total_prefacturado_mes, 1.0) if total_prefacturado_mes else 0
    prefacturas_vencidas = [
        p
        for p in prefacturas_pendientes
        if str(p.get("vencimiento", ""))[:10] and str(p.get("vencimiento", ""))[:10] < date.today().isoformat()
    ]
    presupuestos_por_vencer = [
        p
        for p in presupuestos_abiertos
        if str(p.get("valido_hasta", ""))[:10] and str(p.get("valido_hasta", ""))[:10] >= date.today().isoformat()
    ]

    st.markdown("## 📊 Resumen ejecutivo")
    st.caption(f"Vista de control para {_month_label(current_month)}.")

    # KPI cards del dashboard
    k1, k2, k3, k4 = st.columns(4)
    for col, title, value, color in [
        (k1, "Cobrado este mes", fmt_moneda(total_cobrado_mes), "#14b8a6"),
        (k2, "Pendiente de cobro", fmt_moneda(total_pendiente), "#ef4444"),
        (k3, "Presupuestos abiertos", str(len(presupuestos_abiertos)), "#f59e0b"),
        (k4, "Conversion presupuestos", f"{conversion:.0f}%", "#8b5cf6"),
    ]:
        with col:
            with st.container(border=True):
                st.markdown(
                    f"<div style='text-align:center;'>"
                    f"<div style='font-size:0.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;'>{title}</div>"
                    f"<div style='font-size:1.45rem;font-weight:700;color:{color};'>{value}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)
    st.progress(cumplimiento, text=f"Cobrado sobre pre-facturado del mes: {cumplimiento * 100:.0f}%")
    if prefacturas_vencidas:
        monto_vencido = sum(_money(p.get('saldo')) for p in prefacturas_vencidas)
        st.error(
            f"⚠️ Hay **{len(prefacturas_vencidas)}** pre-factura(s) vencida(s) con saldo por "
            f"**{fmt_moneda(monto_vencido)}**."
        )
    elif total_pendiente > 0:
        st.info(f"ℹ️ Hay saldo pendiente por {fmt_moneda(total_pendiente)}, sin vencimientos atrasados.")
    else:
        st.success("✅ Cartera al dia: no hay saldos pendientes.")
    if presupuestos_por_vencer:
        st.caption(f"📋 Presupuestos abiertos vigentes: {len(presupuestos_por_vencer)}.")

    st.markdown("### ⚡ Accesos rapidos")
    c1, c2, c3, c4 = st.columns(4)
    acciones = [
        (c1, "Nuevo cliente", "Clientes fiscales", "#3b82f6"),
        (c2, "Nuevo presupuesto", "Presupuestos", "#8b5cf6"),
        (c3, "Nueva pre-factura", "Pre-facturas", "#f59e0b"),
        (c4, "Registrar cobro", "Cobros", "#14b8a6"),
    ]
    for col, label, target, color in acciones:
        with col:
            if st.button(label, use_container_width=True, type="secondary"):
                _set_module(target)

    st.divider()

    # Graficos del dashboard
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("### 📊 Evolucion mensual")
        with st.container(border=True):
            if not cobros and not prefacturas:
                bloque_estado_vacio("Sin datos", "Carga cobros y pre-facturas para ver la evolucion mensual.")
            else:
                meses_cobros: Dict[str, float] = {}
                meses_prefacturas: Dict[str, float] = {}
                for c in cobros:
                    key = str(c.get("fecha", ""))[:7]
                    if key:
                        meses_cobros[key] = meses_cobros.get(key, 0.0) + _money(c.get("monto"))
                for p in prefacturas_raw:
                    key = str(p.get("fecha", ""))[:7]
                    if key:
                        meses_prefacturas[key] = meses_prefacturas.get(key, 0.0) + _money(p.get("total"))
                all_months = sorted(set(list(meses_cobros.keys()) + list(meses_prefacturas.keys())))
                if all_months:
                    chart_data = [
                        {
                            "Mes": _month_label(m),
                            "Cobrado": meses_cobros.get(m, 0),
                            "Pre-facturado": meses_prefacturas.get(m, 0),
                        }
                        for m in all_months[-6:]
                    ]
                    st.bar_chart(chart_data, x="Mes", y=["Cobrado", "Pre-facturado"], height=260)
                else:
                    bloque_estado_vacio("Sin datos", "No hay cobros ni pre-facturas registradas.")

    with chart_right:
        st.markdown("### 📋 Estados de presupuestos")
        with st.container(border=True):
            if not presupuestos:
                bloque_estado_vacio("Sin presupuestos", "Carga presupuestos para ver el desglose por estado.")
            else:
                estado_counts: Dict[str, int] = {}
                for p in presupuestos:
                    est = str(p.get("estado", "Borrador")).strip() or "Borrador"
                    estado_counts[est] = estado_counts.get(est, 0) + 1
                estado_chart = [{"Estado": k, "Cantidad": v} for k, v in sorted(estado_counts.items(), key=lambda x: -x[1])]
                st.bar_chart(estado_chart, x="Estado", y="Cantidad", height=260)

    # Métricas avanzadas
    st.divider()
    st.markdown("### 📈 Métricas avanzadas")
    m1, m2, m3 = st.columns(3)
    with m1:
        with st.container(border=True):
            st.markdown("<div style='font-size:0.75rem;color:#94a3b8;text-transform:uppercase;'>Cliente principal (pre-facturado)</div>", unsafe_allow_html=True)
            cliente_pref: Dict[str, float] = {}
            for p in prefacturas_raw:
                nombre = p.get("cliente_nombre", "Sin nombre")
                cliente_pref[nombre] = cliente_pref.get(nombre, 0.0) + _money(p.get("total"))
            if cliente_pref:
                top_cliente = max(cliente_pref.items(), key=lambda x: x[1])
                st.markdown(f"<div style='font-size:1.2rem;font-weight:700;'>{escape(top_cliente[0])}</div>", unsafe_allow_html=True)
                st.caption(f"{fmt_moneda(top_cliente[1])} pre-facturado")
            else:
                st.caption("Sin datos")
    with m2:
        with st.container(border=True):
            st.markdown("<div style='font-size:0.75rem;color:#94a3b8;text-transform:uppercase;'>Dias promedio de cobro</div>", unsafe_allow_html=True)
            dias_cobro = []
            for p in prefacturas_raw:
                pid = str(p.get("id", ""))
                fecha_pref = _parse_date(p.get("fecha"), date.min)
                if fecha_pref == date.min:
                    continue
                # Primer cobro de esta pre-factura
                cobros_pref = [c for c in cobros if str(c.get("prefactura_id")) == pid]
                if cobros_pref:
                    fecha_primero = min(_parse_date(c.get("fecha"), date.max) for c in cobros_pref)
                    if fecha_primero != date.max:
                        dias = (fecha_primero - fecha_pref).days
                        if dias >= 0:
                            dias_cobro.append(dias)
            if dias_cobro:
                promedio = sum(dias_cobro) / len(dias_cobro)
                st.markdown(f"<div style='font-size:1.2rem;font-weight:700;'>{promedio:.0f} dias</div>", unsafe_allow_html=True)
                st.caption(f"Basado en {len(dias_cobro)} cobros")
            else:
                st.caption("Sin datos")
    with m3:
        with st.container(border=True):
            st.markdown("<div style='font-size:0.75rem;color:#94a3b8;text-transform:uppercase;'>Tasa de conversion (monto)</div>", unsafe_allow_html=True)
            total_pres = sum(_money(p.get("total")) for p in presupuestos)
            total_conv = sum(_money(p.get("total")) for p in presupuestos if _estado(p.get("estado")) in {"aceptado", "convertido"})
            tasa_monto = (total_conv / total_pres * 100) if total_pres else 0
            st.markdown(f"<div style='font-size:1.2rem;font-weight:700;'>{tasa_monto:.0f}%</div>", unsafe_allow_html=True)
            st.caption(f"{fmt_moneda(total_conv)} de {fmt_moneda(total_pres)}")

    # Top 5 clientes por cobros
    st.divider()
    st.markdown("### 🏆 Top 5 clientes por cobros")
    with st.container(border=True):
        if not cobros:
            bloque_estado_vacio("Sin cobros", "No hay datos suficientes.")
        else:
            cliente_cobros: Dict[str, float] = {}
            for c in cobros:
                nombre = c.get("cliente_nombre", "Sin nombre")
                cliente_cobros[nombre] = cliente_cobros.get(nombre, 0.0) + _money(c.get("monto"))
            top5 = sorted(cliente_cobros.items(), key=lambda x: -x[1])[:5]
            top5_chart = [{"Cliente": k, "Cobrado": v} for k, v in top5]
            st.bar_chart(top5_chart, x="Cliente", y="Cobrado", height=240)

    # Recordatorios de vencimiento
    st.markdown("### 🔔 Recordatorios")
    cols_r = st.columns(2)
    with cols_r[0]:
        presupuestos_por_vencer_3d = [
            p for p in presupuestos_abiertos
            if str(p.get("valido_hasta", ""))[:10]
            and date.today() <= _parse_date(p.get("valido_hasta"), date.max)
            <= date.today() + timedelta(days=3)
        ]
        if presupuestos_por_vencer_3d:
            st.warning(f"⚠️ {len(presupuestos_por_vencer_3d)} presupuesto(s) vence(n) en los proximos 3 dias")
        else:
            st.success("✅ No hay presupuestos por vencer en los proximos 3 dias")
    with cols_r[1]:
        if prefacturas_vencidas:
            monto_vencido = sum(_money(p.get('saldo')) for p in prefacturas_vencidas)
            st.error(f"⚠️ {len(prefacturas_vencidas)} pre-factura(s) vencida(s) con {fmt_moneda(monto_vencido)} pendiente")
        else:
            st.success("✅ No hay pre-facturas vencidas")

    st.divider()
    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.markdown("### 💰 Pendientes de cobro")
        with st.container(height=280, border=True):
            if not prefacturas_pendientes:
                bloque_estado_vacio(
                    "Sin pendientes",
                    "No hay pre-facturas pendientes o parciales para cobrar.",
                )
            else:
                rows = []
                for item in sorted(
                    prefacturas_pendientes,
                    key=lambda p: str(p.get("vencimiento") or p.get("fecha") or ""),
                ):
                    rows.append(
                        {
                            "Numero": item.get("numero", ""),
                            "Cliente": item.get("cliente_nombre", ""),
                            "Vence": fmt_fecha(item.get("vencimiento", "")),
                            "Estado": item.get("estado_calculado", item.get("estado", "")),
                            "Total": fmt_moneda(item.get("total", 0)),
                            "Saldo": fmt_moneda(item.get("saldo", 0)),
                        }
                    )
                st.dataframe(rows, use_container_width=True, hide_index=True, height=215)

        st.markdown("### 📈 Meses con cobros")
        with st.container(height=280, border=True):
            if not cobros:
                bloque_estado_vacio("Sin cobros", "Todavia no hay cobros registrados.")
            else:
                meses: Dict[str, float] = {}
                for cobro in cobros:
                    key = str(cobro.get("fecha", ""))[:7]
                    if key:
                        meses[key] = meses.get(key, 0.0) + _money(cobro.get("monto"))
                month_rows = [
                    {"Mes": _month_label(key), "Cobrado": fmt_moneda(value)}
                    for key, value in sorted(meses.items(), reverse=True)
                ]
                st.dataframe(month_rows, use_container_width=True, hide_index=True, height=155)
                chart_rows = [
                    {"Mes": _month_label(key), "Cobrado": value}
                    for key, value in sorted(meses.items())[-6:]
                ]
                if chart_rows:
                    st.bar_chart(chart_rows, x="Mes", y="Cobrado", height=180)

    with right:
        st.markdown("### 🔔 Actividad reciente")
        with st.container(height=520, border=True):
            recent = _recent_activity(presupuestos, prefacturas, cobros)
            if not recent:
                bloque_estado_vacio(
                    "Sin actividad",
                    "Cuando cargues clientes, presupuestos, pre-facturas o cobros, van a aparecer aca.",
                )
            else:
                for row in recent[:15]:
                    tipo_icon = {"Presupuesto": "📋", "Pre-factura": "📄", "Cobro": "💵"}.get(row.get("tipo", ""), "•")
                    with st.container(border=True):
                        st.caption(f"{fmt_fecha(row.get('fecha', ''))} | {tipo_icon} {row.get('tipo', '')}")
                        st.markdown(f"**{row.get('cliente') or 'Sin cliente'}**")
                        detail = str(row.get("detalle") or "").strip()
                        if detail:
                            st.caption(detail)
                        st.markdown(f"**{fmt_moneda(row.get('importe', 0))}**")

        st.markdown("### 🏷️ Calidad de datos")
        checks = [
            ("Clientes cargados", len(clientes) > 0, "#3b82f6"),
            ("Hay presupuestos", len(presupuestos) > 0, "#8b5cf6"),
            ("Hay pre-facturas", len(prefacturas) > 0, "#f59e0b"),
            ("Hay cobros", len(cobros) > 0, "#14b8a6"),
        ]
        for label, ok, color in checks:
            icon = "✅" if ok else "⏳"
            st.markdown(
                f"<span style='font-size:0.85rem;'>{icon} <strong>{label}</strong></span>",
                unsafe_allow_html=True,
            )

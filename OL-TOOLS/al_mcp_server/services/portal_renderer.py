# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
Renderizador de páginas de portal: funciones puras que convierten las especificaciones
de widgets en dicts listos para mostrar.

Cada función pública recibe:
  - env:            un Environment de Odoo (puede venir con with_user() por gobierno)
  - widget_spec:    el dict de un widget de la especificación de la página
  - filter_values:  dict nombre de filtro → valor tomado de la query string

Forma del resultado según el tipo de widget:

  KPI:
    {
      "type": "kpi",
      "title": str,
      "value": float|int,
      "formatted": str,        # p. ej. "$1,234.56"
      "icon": str,             # clase fa-*
      "color": str,            # color hexadecimal
      "error": str|None,       # se rellena si el cálculo falló
    }

  Chart:
    {
      "type": "chart",
      "title": str,
      "chart_type": str,
      "echarts_option": dict,  # opción ECharts completa, serializable a JSON
      "error": str|None,
    }

  Table:
    {
      "type": "table",
      "title": str,
      "headers": list[str],
      "rows": list[list],
      "error": str|None,
    }
"""

import logging
import re

_logger = logging.getLogger(__name__)

_FILTER_PLACEHOLDER_RE = re.compile(r"\{\{filters\.(\w+)\}\}")


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------


def compute_widget(env, widget_spec: dict, filter_values: dict) -> dict:
    """Calcula los datos de renderizado de un widget.

    Nunca lanza excepciones: los errores se guardan en result["error"] para que
    la página pueda seguir mostrando los demás widgets.
    """
    wtype = widget_spec.get("type", "")
    try:
        resolved_spec = _substitute_filters(widget_spec, filter_values)
        if wtype == "kpi":
            return _compute_kpi(env, resolved_spec)
        if wtype == "chart":
            return _compute_chart(env, resolved_spec)
        if wtype == "table":
            return _compute_table(env, resolved_spec)
        return {"type": wtype, "title": widget_spec.get("title", ""), "error": f"Tipo de widget desconocido: {wtype!r}"}
    except Exception as exc:
        _logger.warning("portal_renderer: falló el widget %r: %s", widget_spec.get("title"), exc, exc_info=True)
        return {
            "type": wtype,
            "title": widget_spec.get("title", ""),
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Indicador KPI
# ---------------------------------------------------------------------------


def _compute_kpi(env, spec: dict) -> dict:
    model_name = spec["model"]
    field = spec["field"]
    domain = spec.get("domain") or []
    aggregate = spec.get("aggregate", "sum")
    fmt = spec.get("format", "number")
    currency_code = spec.get("currency", "")

    _check_model(env, model_name)
    value = _aggregate_field(env, model_name, field, domain, aggregate)

    return {
        "type": "kpi",
        "title": spec.get("title", ""),
        "value": value,
        "formatted": _format_value(value, fmt, currency_code, env),
        "icon": spec.get("icon", "fa-bar-chart"),
        "color": spec.get("color", "#6366f1"),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Gráfico
# ---------------------------------------------------------------------------


def _compute_chart(env, spec: dict) -> dict:
    model_name = spec["model"]
    domain = spec.get("domain") or []
    groupby = spec.get("groupby") or []
    agg_fields = spec.get("fields") or []
    chart_type = spec.get("chart_type", "bar")
    limit = int(spec.get("limit", 50))

    _check_model(env, model_name)

    rows = _run_read_group(env, model_name, domain, groupby, agg_fields, limit=limit)
    echarts_option = _build_echarts_option(chart_type, groupby, agg_fields, rows, spec)

    return {
        "type": "chart",
        "title": spec.get("title", ""),
        "chart_type": chart_type,
        "echarts_option": echarts_option,
        "error": None,
    }


def _build_echarts_option(chart_type: str, groupby: list, agg_fields: list, rows: list, spec: dict) -> dict:
    """Construye el dict de opciones ECharts completo a partir de las filas agrupadas."""
    label_key = groupby[0].split(":")[0] if groupby else None
    value_key = agg_fields[0].split(":")[0] if agg_fields else None

    labels = []
    values = []
    for row in rows:
        raw_label = row.get(label_key) if label_key else ""
        if isinstance(raw_label, dict):
            raw_label = raw_label.get("display_name") or str(raw_label)
        elif raw_label is None:
            raw_label = "(ninguno)"
        labels.append(str(raw_label))

        raw_val = row.get(value_key, 0) if value_key else 0
        values.append(float(raw_val) if raw_val is not None else 0.0)

    color = spec.get("color", "#6366f1")

    if chart_type in ("bar",):
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 30}},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": values, "itemStyle": {"color": color}}],
        }

    if chart_type == "line":
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": labels},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "data": values, "smooth": True, "itemStyle": {"color": color}}],
        }

    if chart_type == "area":
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": labels},
            "yAxis": {"type": "value"},
            "series": [{
                "type": "line",
                "data": values,
                "smooth": True,
                "areaStyle": {},
                "itemStyle": {"color": color},
            }],
        }

    if chart_type == "pie":
        return {
            "tooltip": {"trigger": "item"},
            "legend": {"orient": "vertical", "left": "left"},
            "series": [{
                "type": "pie",
                "radius": "65%",
                "data": [{"name": l, "value": v} for l, v in zip(labels, values)],
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}},
            }],
        }

    if chart_type == "donut":
        return {
            "tooltip": {"trigger": "item"},
            "legend": {"orient": "vertical", "left": "left"},
            "series": [{
                "type": "pie",
                "radius": ["40%", "70%"],
                "data": [{"name": l, "value": v} for l, v in zip(labels, values)],
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}},
            }],
        }

    # Respaldo
    return {
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": values}],
    }


# ---------------------------------------------------------------------------
# Tabla
# ---------------------------------------------------------------------------


def _compute_table(env, spec: dict) -> dict:
    model_name = spec["model"]
    domain = spec.get("domain") or []
    groupby = spec.get("groupby") or []
    agg_fields = spec.get("fields") or []
    orderby = spec.get("orderby", "")
    limit = int(spec.get("limit", 20))

    _check_model(env, model_name)

    # Sin groupby se usa search_read (lista simple, sin agregados).
    # Con groupby se usa _read_group (filas agregadas).
    if not groupby:
        plain_fields = [f.split(":")[0] for f in agg_fields]
        kw = {"limit": limit}
        if orderby:
            kw["order"] = orderby
        records = env[model_name].search_read(domain, plain_fields, **kw)

        headers = [_field_label(env, model_name, f) for f in plain_fields]
        table_rows = []
        for rec in records:
            row = []
            for key in plain_fields:
                val = rec.get(key)
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    # Many2one devuelve [id, display_name]
                    val = val[1]
                elif val is None or val is False:
                    val = ""
                elif isinstance(val, float):
                    val = round(val, 2)
                row.append(val)
            table_rows.append(row)
    else:
        rows = _run_read_group(env, model_name, domain, groupby, agg_fields, limit=limit, orderby=orderby)

        headers = []
        for gb in groupby:
            headers.append(_field_label(env, model_name, gb.split(":")[0]))
        for af in agg_fields:
            parts = af.split(":")
            label = _field_label(env, model_name, parts[0])
            if len(parts) > 1:
                label = f"{label} ({parts[1].upper()})"
            headers.append(label)

        col_keys = [gb.split(":")[0] for gb in groupby] + [af.split(":")[0] for af in agg_fields]
        table_rows = []
        for row in rows:
            table_row = []
            for key in col_keys:
                val = row.get(key)
                if isinstance(val, dict):
                    val = val.get("display_name") or str(val)
                elif val is None:
                    val = ""
                elif isinstance(val, float):
                    val = round(val, 2)
                table_row.append(val)
            table_rows.append(table_row)

    return {
        "type": "table",
        "title": spec.get("title", ""),
        "headers": headers,
        "rows": table_rows,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Utilidades del ORM: usan _read_group para agregar (sin bucles de suma en Python)
# ---------------------------------------------------------------------------


def _field_label(env, model_name: str, fname: str) -> str:
    """Etiqueta del campo en el idioma del usuario (como las cabeceras de las
    listas de Odoo). Si el campo no existe, se deriva del nombre técnico."""
    field = env[model_name]._fields.get(fname)
    if field:
        return field._description_string(env) or fname
    return fname.replace("_", " ").capitalize()


def _aggregate_field(env, model_name: str, field: str, domain: list, aggregate: str) -> float:
    """Devuelve un único valor agregado de *field* en *model_name*."""
    agg_expr = f"{field}:{aggregate}"
    rows = env[model_name]._read_group(
        domain=domain,
        groupby=[],
        aggregates=[agg_expr],
    )
    if not rows:
        return 0.0
    row = rows[0]
    val = row[0] if row else 0
    return float(val) if val is not None else 0.0


def _run_read_group(env, model_name: str, domain: list, groupby: list, agg_fields: list,
                    limit: int = 80, orderby: str = "") -> list:
    """Ejecuta _read_group y devuelve una lista de dicts serializables."""
    kw = {"limit": limit}
    if orderby:
        # En Odoo 19 el parámetro de _read_group se llama ``order``.
        kw["order"] = orderby

    rows = env[model_name]._read_group(
        domain=domain,
        groupby=groupby,
        aggregates=agg_fields,
        **kw,
    )

    result = []
    gb_keys = [g.split(":")[0] for g in groupby]
    agg_keys = [a.split(":")[0] for a in agg_fields]

    for row in rows:
        row_dict = {}
        for i, key in enumerate(gb_keys):
            val = row[i]
            if hasattr(val, "_name"):
                row_dict[key] = {"id": val.id, "display_name": val.display_name}
            else:
                row_dict[key] = val
        for j, key in enumerate(agg_keys):
            raw = row[len(gb_keys) + j]
            row_dict[key] = float(raw) if isinstance(raw, (int, float)) and raw is not None else raw
        result.append(row_dict)

    return result


# ---------------------------------------------------------------------------
# Sustitución de filtros
# ---------------------------------------------------------------------------


def _substitute_filters(spec: dict, filter_values: dict) -> dict:
    """Devuelve una copia profunda de *spec* con los marcadores {{filters.<name>}} sustituidos."""
    if not filter_values:
        return spec
    import copy
    return _deep_substitute(copy.deepcopy(spec), filter_values)


def _deep_substitute(obj, filter_values: dict):
    if isinstance(obj, str):
        def _replacer(m):
            return filter_values.get(m.group(1), m.group(0))
        return _FILTER_PLACEHOLDER_RE.sub(_replacer, obj)
    if isinstance(obj, list):
        return [_deep_substitute(item, filter_values) for item in obj]
    if isinstance(obj, dict):
        return {k: _deep_substitute(v, filter_values) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Utilidades de formato
# ---------------------------------------------------------------------------


def _format_value(value: float, fmt: str, currency_code: str, env) -> str:
    """Formatea un valor numérico como texto legible."""
    if fmt == "integer":
        return f"{int(value):,}"
    if fmt == "percent":
        return f"{value:.1f}%"
    if fmt == "currency":
        symbol = _get_currency_symbol(env, currency_code)
        return f"{symbol}{value:,.2f}"
    # por defecto: number
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _get_currency_symbol(env, currency_code: str) -> str:
    """Devuelve el símbolo de *currency_code*; por defecto, el de la moneda de la compañía."""
    try:
        if currency_code:
            cur = env["res.currency"].search([("name", "=", currency_code)], limit=1)
            if cur:
                return cur.symbol or currency_code
        company_cur = env.company.currency_id
        return company_cur.symbol if company_cur else "$"
    except Exception:
        return "$"


# ---------------------------------------------------------------------------
# Protección
# ---------------------------------------------------------------------------


def _check_model(env, model_name: str) -> None:
    """Lanza ValueError si *model_name* no está en el registro."""
    if model_name not in env.registry:
        raise ValueError(f"Modelo {model_name!r} no encontrado en el registro de Odoo.")

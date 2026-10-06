import base64
import json
import logging

from markupsafe import Markup

from odoo.service.model import get_public_method

from . import schema_cache
from . import bi_tools
from . import job_tools
from . import portal_tools
from . import artifact_tools
from . import module_tools
from .json_utils import odoo_json_default  # noqa: F401 — se reexporta para quienes lo importan

_logger = logging.getLogger(__name__)

# Herramientas permitidas con el alcance 'read'; el resto exige alcance de escritura
_READ_ONLY_TOOLS = frozenset({
    # Core
    "odoo_get_models",
    "odoo_fields_get",
    "odoo_search_read",
    "odoo_count",
    "odoo_name_search",
    "odoo_read_group",
    "odoo_get_views",
    "odoo_default_get",
    "odoo_print_report",
    # Herramientas BI — todas de solo lectura
    "odoo_pivot",
    "odoo_time_series",
    "odoo_top_n",
    "odoo_cohort",
    "odoo_funnel",
    "odoo_export_csv",
    "odoo_export_xlsx",
    # Consulta de trabajos
    "odoo_job_status",
    "odoo_job_list",
    # Lectura del portal
    "odoo_list_portal_pages",
    # Lectura de artefactos
    "odoo_list_html_artifacts",
    "odoo_get_html_artifact",
    # Lectura del generador de módulos
    "odoo_validate_module_spec",
    "odoo_list_generated_modules",
    # Herramienta de contexto (disponible en todos los alcances)
    "odoo_get_context",
})

# Herramientas bloqueadas con el alcance 'write' (requieren admin)
_WRITE_SCOPE_BLOCKED_TOOLS = frozenset({
    "odoo_unlink",
    "odoo_call_method",   # call_method puede hacer cualquier cosa — solo admin
    "odoo_generate_module",
    "odoo_install_generated_module",
})

# Handlers de herramientas externas fusionados desde los módulos satélite.
# module_tools usa una única función despachadora (ver _MODULE_TOOL_NAMES más abajo).
_EXTERNAL_HANDLERS = {
    **bi_tools.TOOL_HANDLERS,
    **job_tools.TOOL_HANDLERS,
    **portal_tools.TOOL_HANDLERS,
    **artifact_tools.TOOL_HANDLERS,
}

_MODULE_TOOL_NAMES = frozenset(t["name"] for t in module_tools.TOOL_DEFINITIONS)


def execute_tool(env, tool_name: str, args: dict):
    """Despacha una llamada de herramienta a su implementación y devuelve un resultado serializable.

    El alcance se comprueba antes de despachar. Se lee de env.context['mcp_scope']
    (lo fija el controlador antes de llamar a process_message). Las restricciones
    de modelos y campos se leen de env.context['mcp_restrictions'].
    """
    _enforce_scope(env, tool_name)
    _enforce_model_access(env, tool_name, args)

    handlers = {
        "odoo_get_models": _get_models,
        "odoo_fields_get": _fields_get,
        "odoo_search_read": _search_read,
        "odoo_create": _create,
        "odoo_write": _write,
        "odoo_execute_wizard": _execute_wizard,
        "odoo_unlink": _unlink,
        "odoo_call_method": _call_method,
        # Herramientas de análisis
        "odoo_count": _count,
        "odoo_name_search": _name_search,
        "odoo_read_group": _read_group,
        # Herramientas de flujo de trabajo y formularios
        "odoo_message_post": _message_post,
        "odoo_default_get": _default_get,
        "odoo_get_views": _get_views,
        "odoo_onchange": _onchange,
        "odoo_print_report": _print_report,
        "odoo_create_attachment": _create_attachment,
        # Contexto y catálogo como herramientas — para clientes sin soporte de MCP Resources (p. ej. ChatGPT)
        "odoo_get_context": _get_context,
    }
    handler = handlers.get(tool_name)
    if handler:
        return handler(env, args)

    # Las herramientas del generador de módulos comparten un despachador (con flag de función y alcance dentro)
    if tool_name in _MODULE_TOOL_NAMES:
        return module_tools.execute_module_tool(env, tool_name, args)

    # Herramientas BI, de trabajos y de portal de los módulos satélite
    external = _EXTERNAL_HANDLERS.get(tool_name)
    if external:
        return external(env, args)

    raise ValueError(f"Herramienta desconocida: {tool_name!r}")


# ---------------------------------------------------------------------------
# Utilidades de gobierno
# ---------------------------------------------------------------------------


def _enforce_scope(env, tool_name: str) -> None:
    """Lanza PermissionError si el alcance MCP actual no permite *tool_name*."""
    scope = env.context.get("mcp_scope", "write")

    if scope == "admin":
        return  # admin puede llamar a todo

    if scope == "read":
        if tool_name not in _READ_ONLY_TOOLS:
            raise PermissionError(
                f"La herramienta {tool_name!r} requiere al menos el alcance 'write'. "
                f"Este token está restringido al alcance 'read' (solo lectura). "
                f"Contacte a su administrador para ampliar el alcance del token."
            )
        return

    # scope == 'write' (por defecto)
    if tool_name in _WRITE_SCOPE_BLOCKED_TOOLS:
        raise PermissionError(
            f"La herramienta {tool_name!r} requiere el alcance 'admin'. "
            f"Este token tiene el alcance 'write'. "
            f"Contacte a su administrador para ampliar el alcance del token."
        )


def _enforce_model_access(env, tool_name: str, args: dict) -> None:
    """Lanza PermissionError si las restricciones del token bloquean el modelo de *args*."""
    restrictions = env.context.get("mcp_restrictions")
    if not restrictions:
        return

    model_name = args.get("model")
    if not model_name:
        return  # herramientas como odoo_get_models no reciben el argumento model

    denied_models = restrictions.get("denied_models") or set()
    allowed_models = restrictions.get("allowed_models") or set()

    if denied_models and model_name in denied_models:
        raise PermissionError(
            f"El acceso al modelo {model_name!r} está denegado para este token."
        )
    if allowed_models and model_name not in allowed_models:
        raise PermissionError(
            f"El acceso al modelo {model_name!r} no está permitido por la lista de modelos permitidos de este token."
        )


def _get_field_restrictions(env, model_name: str) -> list | None:
    """Devuelve la lista de campos permitidos de *model_name* según las restricciones del contexto, o None."""
    restrictions = env.context.get("mcp_restrictions")
    if not restrictions:
        return None
    field_map = restrictions.get("field_restrictions") or {}
    return field_map.get(model_name)  # None si el modelo no está en el mapa


def _domain_field_names(domain) -> set:
    """Primer segmento de cada hoja del dominio (('partner_id.name', ...) -> 'partner_id')."""
    names = set()
    for leaf in domain or []:
        if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and isinstance(leaf[0], str):
            names.add(leaf[0].split(".")[0])
    return names


def _check_read_fields(env, model_name: str, domain=None, order=None, extra=None) -> None:
    """Rechaza dominios, órdenes o agrupaciones sobre campos fuera de la lista
    permitida del token: filtrar por un campo oculto también revela su valor."""
    allowed = _get_field_restrictions(env, model_name)
    if allowed is None:
        return
    used = _domain_field_names(domain)
    if order:
        for part in str(order).split(","):
            token = part.strip().split(" ")[0]
            if token:
                used.add(token)
    for name in extra or []:
        used.add(str(name).split(":")[0].split(".")[0])
    blocked = sorted(n for n in used if n != "id" and n not in allowed)
    if blocked:
        raise PermissionError(
            f"Los campos {blocked!r} del modelo {model_name!r} no están permitidos "
            f"por las restricciones de campos de este token."
        )


# Operación de trabajo asíncrono → herramienta síncrona equivalente, para aplicar
# exactamente el mismo alcance y las mismas restricciones en el cron.
_JOB_OPERATION_TOOLS = {
    "bulk_update": "odoo_write",
    "bulk_create": "odoo_create",
    "bulk_unlink": "odoo_unlink",
    "export_csv": "odoo_export_csv",
    "export_xlsx": "odoo_export_xlsx",
    "call_method": "odoo_call_method",
    "custom": "odoo_call_method",
}


def enforce_job_operation(env, operation: str, args: dict) -> None:
    """Aplica alcance y restricciones del token a un trabajo asíncrono.

    Se llama al enviar el trabajo y de nuevo al ejecutarlo en el cron. Puede
    ajustar ``args['fields']`` de las exportaciones a la lista permitida.
    """
    tool_name = _JOB_OPERATION_TOOLS.get(operation)
    if not tool_name:
        raise ValueError(f"Operación de trabajo desconocida: {operation!r}")
    _enforce_scope(env, tool_name)
    _enforce_model_access(env, tool_name, args)
    model_name = args.get("model")
    if not model_name:
        return
    if operation == "bulk_update":
        _check_write_fields(env, model_name, args.get("values") or {})
        _check_read_fields(env, model_name, domain=args.get("domain"))
    elif operation == "bulk_create":
        for vals in args.get("records") or []:
            if isinstance(vals, dict):
                _check_write_fields(env, model_name, vals)
    elif operation == "bulk_unlink":
        _check_read_fields(env, model_name, domain=args.get("domain"))
    elif operation in ("export_csv", "export_xlsx"):
        _check_read_fields(env, model_name, domain=args.get("domain"))
        allowed = _get_field_restrictions(env, model_name)
        if allowed is not None:
            requested = args.get("fields") or []
            args["fields"] = [f for f in requested if f in allowed] if requested else list(allowed)
    elif operation in ("call_method", "custom"):
        _check_call_method_restrictions(env, model_name, args.get("method") or "")


# ---------------------------------------------------------------------------
# Implementación de cada herramienta
# ---------------------------------------------------------------------------


def _get_models(env, args: dict):
    filter_kw = args.get("filter", "") or ""
    cache_key = schema_cache.scoped_key(env, f"get_models:{filter_kw}")

    if schema_cache._cache_enabled(env):
        ttl = schema_cache._cache_ttl(env)

        def _compute():
            domain = [("transient", "=", False)]
            if filter_kw:
                domain.append(("model", "ilike", filter_kw))
            rows = env["ir.model"].search_read(
                domain, ["model", "name"], order="model", limit=500
            )
            return {"count": len(rows), "models": rows}

        return schema_cache.get_or_compute(cache_key, ttl, _compute)

    domain = [("transient", "=", False)]
    if filter_kw:
        domain.append(("model", "ilike", filter_kw))
    rows = env["ir.model"].search_read(
        domain,
        ["model", "name"],
        order="model",
        limit=500,
    )
    return {"count": len(rows), "models": rows}


def _fields_get(env, args: dict):
    model_name = args["model"]
    attributes = args.get("attributes") or ["string", "type", "required", "readonly", "help"]
    attr_key = ",".join(sorted(attributes))
    cache_key = schema_cache.scoped_key(env, f"fields_get:{model_name}:{attr_key}")

    if schema_cache._cache_enabled(env):
        ttl = schema_cache._cache_ttl(env)

        def _compute():
            m = _resolve_model(env, model_name)
            return m.fields_get(attributes=attributes)

        raw = schema_cache.get_or_compute(cache_key, ttl, _compute)
    else:
        raw = _resolve_model(env, model_name).fields_get(attributes=attributes)

    result = dict(raw)

    # Descarta en silencio los campos fuera de la lista permitida (restricción por petición — nunca se cachea)
    allowed = _get_field_restrictions(env, model_name)
    if allowed is not None:
        result = {k: v for k, v in result.items() if k in allowed}

    return {"model": model_name, "fields": result}


def _search_read(env, args: dict):
    model_name = args["model"]
    domain = args.get("domain") or []
    fields = args.get("fields") or []
    limit = args.get("limit", 80)
    offset = args.get("offset", 0)
    order = args.get("order")

    # Intersecta en silencio los campos pedidos con la lista permitida
    allowed = _get_field_restrictions(env, model_name)
    if allowed is not None and fields:
        fields = [f for f in fields if f in allowed]
    elif allowed is not None and not fields:
        # Sin lista de campos explícita — se limita automáticamente a la lista permitida
        fields = list(allowed)

    _check_read_fields(env, model_name, domain=domain, order=order)

    model = _resolve_model(env, model_name)
    kw = {"limit": limit, "offset": offset}
    if order:
        kw["order"] = order

    records = model.search_read(domain, fields, **kw)
    total = model.search_count(domain)
    return {
        "model": model_name,
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": records,
    }


def _create(env, args: dict):
    model_name = args["model"]
    values = args["values"]

    # Rechaza escrituras en campos fuera de la lista permitida
    _check_write_fields(env, model_name, values)

    # Valida los campos obligatorios antes de ir a la base de datos
    _check_required_fields(env, model_name, values)

    record = _resolve_model(env, model_name).create(values)
    return {"id": record.id, "model": model_name}


_MAX_IDS = 200  # tope de seguridad: evita que la IA actualice o borre en masa en una sola llamada


def _write(env, args: dict):
    model_name = args["model"]
    ids = args["ids"]
    values = args["values"]
    if len(ids) > _MAX_IDS:
        raise ValueError(
            f"Demasiados registros: se proporcionaron {len(ids)} ids pero el máximo es {_MAX_IDS} por llamada. "
            f"Divida en varias llamadas o use un dominio más específico."
        )

    # Rechaza escrituras en campos fuera de la lista permitida
    _check_write_fields(env, model_name, values)

    _resolve_model(env, model_name).browse(ids).write(values)
    return {"updated": len(ids), "model": model_name, "ids": ids}


def _execute_wizard(env, args: dict):
    """Crea un asistente TransientModel y ejecuta en él un método de forma atómica."""
    model_name = args["model"]
    values = args.get("values") or {}
    method_name = args["method"]
    method_kwargs = args.get("kwargs") or {}

    model = _resolve_model(env, model_name)

    if not model._transient:
        raise ValueError(
            f"El modelo {model_name!r} no es un TransientModel (asistente). "
            f"Use odoo_create + odoo_call_method para modelos permanentes."
        )

    if method_name.startswith("_") or method_name in _CALL_METHOD_DENYLIST:
        raise ValueError(
            f"El método {method_name!r} es privado y no se puede llamar mediante MCP."
        )

    _check_write_fields(env, model_name, values)

    if not hasattr(model, method_name):
        available = sorted(
            m for m in dir(type(model))
            if not m.startswith("_")
            and callable(getattr(type(model), m, None))
            and m not in _CALL_METHOD_DENYLIST
        )[:15]
        raise ValueError(
            f"El método {method_name!r} no se encontró en el asistente {model_name!r}. "
            f"Métodos públicos disponibles: {available}"
        )

    # Mismas reglas que el RPC de Odoo: nada de métodos @api.private.
    get_public_method(model, method_name)
    wizard = model.create(values)
    result = getattr(wizard, method_name)(**method_kwargs)

    return {
        "wizard_id": wizard.id,
        "model": model_name,
        "method": method_name,
        "result": result,
    }


def _unlink(env, args: dict):
    model_name = args["model"]
    ids = args["ids"]
    if len(ids) > _MAX_IDS:
        raise ValueError(
            f"Demasiados registros: se proporcionaron {len(ids)} ids pero el máximo es {_MAX_IDS} por llamada. "
            f"Divida en varias llamadas o confirme cada lote explícitamente."
        )
    _resolve_model(env, model_name).browse(ids).unlink()
    return {"deleted": len(ids), "model": model_name, "ids": ids}


_CALL_METHOD_DENYLIST = frozenset({
    # Escalada de privilegios — saltaría las ACL o cambiaría el contexto de ejecución
    "sudo", "with_user", "with_company", "with_context", "with_env",
    # Acceso directo a la base de datos
    "execute", "execute_kw",
    # Use en su lugar las herramientas dedicadas (odoo_search_read, odoo_create, etc.)
    "search", "search_read", "search_count", "read", "create", "write", "unlink",
    "read_group", "_read_group", "name_search", "name_get", "default_get",
    # Internos del ORM
    "browse", "exists", "ensure_one", "mapped", "filtered", "sorted", "invalidate_recordset",
})


# Métodos genéricos de lectura/escritura que saltarían la lista de campos permitidos.
_FIELD_BYPASS_METHODS = frozenset({
    "export_data", "web_read", "web_search_read", "web_save", "web_read_group",
    "formatted_read_group", "search_fetch", "fetch", "copy_data", "copy",
    "read_group", "onchange", "web_override_translations", "update_field_translations",
    "get_field_translations",
})


def _check_call_method_restrictions(env, model_name: str, method_name: str) -> None:
    if method_name in _FIELD_BYPASS_METHODS and _get_field_restrictions(env, model_name) is not None:
        raise PermissionError(
            f"El método {method_name!r} no está disponible en {model_name!r} porque este token "
            f"tiene restricciones de campos para ese modelo."
        )


def _call_method(env, args: dict):
    model_name = args["model"]
    method_name = args["method"]
    ids = args.get("ids") or []
    method_args = args.get("args") or []
    method_kwargs = args.get("kwargs") or {}

    if method_name.startswith("_"):
        raise ValueError(
            f"El método {method_name!r} es privado (comienza con '_') y no se puede llamar mediante MCP."
        )
    if method_name in _CALL_METHOD_DENYLIST:
        raise ValueError(
            f"El método {method_name!r} está bloqueado. Use en su lugar la herramienta MCP dedicada "
            f"(odoo_search_read, odoo_create, odoo_write, odoo_unlink, etc.)."
        )

    model = _resolve_model(env, model_name)
    if not hasattr(model, method_name):
        raise ValueError(f"El método {method_name!r} no se encontró en el modelo {model_name!r}")
    # Mismas reglas que el RPC de Odoo: rechaza @api.private y atributos inseguros.
    get_public_method(model, method_name)
    _check_call_method_restrictions(env, model_name, method_name)

    target = model.browse(ids) if ids else model
    result = getattr(target, method_name)(*method_args, **method_kwargs)
    return {"result": result}


_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


def _create_attachment(env, args: dict):
    name = args["name"]
    content_b64 = args["content"]
    mimetype = args.get("mimetype", "application/octet-stream")
    res_model = args.get("model", "")
    res_id = int(args.get("record_id") or 0)

    try:
        raw = base64.b64decode(content_b64)
        file_size = len(raw)
    except Exception:
        raise ValueError("'content' debe ser datos válidos codificados en base64")

    if file_size > _MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"Archivo demasiado grande: {file_size / 1_048_576:.1f} MB. "
            f"El tamaño máximo permitido es {_MAX_ATTACHMENT_BYTES // 1_048_576} MB."
        )

    vals = {
        "name": name,
        "datas": content_b64,
        "mimetype": mimetype,
    }
    if res_model:
        if res_model not in env.registry:
            raise ValueError(f"El modelo {res_model!r} no se encontró en el registro de Odoo")
        vals["res_model"] = res_model
        vals["res_id"] = res_id

    attachment = env["ir.attachment"].create(vals)
    return {
        "id": attachment.id,
        "name": attachment.name,
        "mimetype": attachment.mimetype,
        "file_size": file_size,
        "model": attachment.res_model or None,
        "record_id": attachment.res_id or None,
        "download_url": f"/web/content/{attachment.id}?download=1",
        "preview_uri": f"odoo://attachment/{attachment.id}",
    }


def _print_report(env, args: dict):
    model_name = args["model"]
    ids = args["ids"]
    report_ref = args.get("report", "")

    Report = env["ir.actions.report"]

    if report_ref:
        # Busca por el report_name técnico (p. ej. "sale.report_saleorder")
        report = Report.search([("report_name", "=", report_ref)], limit=1)
        if not report:
            # Alternativa: probar como XML ID
            try:
                report = env.ref(report_ref)
            except Exception:
                report = None
        if not report:
            raise ValueError(
                f"El informe {report_ref!r} no se encontró. "
                f"Use odoo_get_views(model='{model_name}') para ver los informes disponibles, "
                f"o odoo_search_read(model='ir.actions.report', "
                f"domain=[['model','=','{model_name}']], fields=['name','report_name']) "
                f"para la lista completa."
            )
    else:
        # Detección automática: primer informe PDF de este modelo
        report = Report.search(
            [("model", "=", model_name), ("report_type", "in", ["qweb-pdf", "qweb-html"])],
            limit=1,
        )
        if not report:
            # Devuelve todos los informes disponibles para que Claude pueda sugerir uno
            available = Report.search_read(
                [("model", "=", model_name)],
                ["name", "report_name", "report_type"],
            )
            return {
                "error": f"No se encontró ningún informe PDF para {model_name!r}. Especifique el parámetro 'report'.",
                "available_reports": available,
            }

    ids_str = ",".join(str(i) for i in ids)
    download_url = f"/report/pdf/{report.report_name}/{ids_str}"

    # Lee los nombres de los registros para que Claude pueda confirmar el contenido al usuario
    model_obj = _resolve_model(env, model_name)
    records = model_obj.browse(ids)
    record_names = [
        {"id": r.id, "name": r.display_name}
        for r in records if r.exists()
    ]

    # Lista los demás informes disponibles de este modelo
    other_reports = Report.search_read(
        [("model", "=", model_name), ("id", "!=", report.id)],
        ["name", "report_name"],
        limit=10,
    )

    return {
        "model": model_name,
        "records": record_names,
        "report_name": report.report_name,
        "report_label": report.name,
        "download_url": download_url,
        "other_available_reports": other_reports,
        "note": (
            "Verifique que 'records' coincida con lo que el usuario espera antes de compartir el enlace. "
            "Abra download_url en un navegador con una sesión de Odoo activa para descargar."
        ),
    }


# ---------------------------------------------------------------------------
# Herramientas de análisis
# ---------------------------------------------------------------------------


def _count(env, args: dict):
    model_name = args["model"]
    domain = args.get("domain") or []
    _check_read_fields(env, model_name, domain=domain)
    model = _resolve_model(env, model_name)
    total = model.search_count(domain)
    return {"model": model_name, "domain": domain, "count": total}


def _name_search(env, args: dict):
    model_name = args["model"]
    name = args.get("name", "")
    limit = args.get("limit", 10)
    model = _resolve_model(env, model_name)
    results = model.name_search(name, limit=limit)
    return {
        "model": model_name,
        "query": name,
        "results": [{"id": r[0], "display_name": r[1]} for r in results],
    }


def _read_group(env, args: dict):
    model_name = args["model"]
    domain = args.get("domain") or []
    groupby = args.get("groupby") or []
    fields = args.get("fields") or []
    limit = args.get("limit", 80)
    orderby = args.get("orderby")

    _check_read_fields(env, model_name, domain=domain, extra=list(groupby) + [
        f for f in fields if not str(f).startswith("__count")
    ])

    model = _resolve_model(env, model_name)
    kw = {"limit": limit}
    if orderby:
        # En Odoo 19 el parámetro de _read_group se llama ``order``.
        kw["order"] = orderby

    rows = model._read_group(
        domain=domain,
        groupby=groupby,
        aggregates=fields,
        **kw,
    )

    # _read_group devuelve una lista de tuplas — se serializa a diccionarios
    def _serialize_group(row):
        result = {}
        for i, key in enumerate(groupby):
            field_name = key.split(":")[0]
            val = row[i]
            if hasattr(val, "_name"):
                result[field_name] = {"id": val.id, "display_name": val.display_name}
            else:
                result[field_name] = val
        for j, agg in enumerate(fields):
            field_name = agg.split(":")[0]
            result[field_name] = row[len(groupby) + j]
        return result

    return {
        "model": model_name,
        "groupby": groupby,
        "fields": fields,
        "rows": [_serialize_group(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Herramientas de flujo de trabajo y formularios
# ---------------------------------------------------------------------------


def _message_post(env, args: dict):
    model_name = args["model"]
    record_id = args["id"]
    body = args["body"]
    subtype_xmlid = args.get("subtype", "mail.mt_comment")
    partner_ids = args.get("partner_ids") or []

    record = _resolve_model(env, model_name).browse(record_id)
    if not record.exists():
        raise ValueError(f"El registro {model_name}#{record_id} no se encontró")
    if not hasattr(record, "message_post"):
        raise ValueError(f"El modelo {model_name!r} no admite chatter (no es mail.thread)")

    # Pasa siempre el cuerpo por el saneador de Odoo — nunca confíes en HTML en
    # bruto de un cliente de IA. bleach/html_sanitize elimina etiquetas y atributos peligrosos.
    from odoo.tools import html_sanitize
    if body and not body.strip().startswith("<"):
        # Plain text: se escapa al interpolar en el Markup (nunca f-string).
        safe_body = Markup("<p>%s</p>") % body
    else:
        # Entrada HTML: se pasa por el saneador de Odoo para quitar vectores XSS
        safe_body = Markup(html_sanitize(body))

    msg = record.message_post(
        body=safe_body,
        subtype_xmlid=subtype_xmlid,
        partner_ids=partner_ids,
    )
    return {
        "message_id": msg.id,
        "model": model_name,
        "record_id": record_id,
        "author": msg.author_id.name,
        "date": str(msg.date),
    }


def _default_get(env, args: dict):
    model_name = args["model"]
    field_names = args.get("fields") or []

    model = _resolve_model(env, model_name)
    if not field_names:
        # Descubre automáticamente los campos escalares si no se da una lista
        all_fields = model.fields_get(attributes=["type"])
        field_names = [
            fname for fname, fdef in all_fields.items()
            if fdef["type"] not in ("one2many", "binary")
        ][:60]

    defaults = model.default_get(field_names)

    # Serializa las tuplas o registros Many2one
    serialized = {}
    for k, v in defaults.items():
        if isinstance(v, tuple):
            serialized[k] = {"id": v[0], "display_name": v[1]}
        elif hasattr(v, "_name"):
            serialized[k] = {"id": v.id, "display_name": v.display_name}
        else:
            serialized[k] = v

    return {
        "model": model_name,
        "defaults": serialized,
    }


def _get_views(env, args: dict):
    model_name = args["model"]
    cache_key = schema_cache.scoped_key(env, f"get_views:{model_name}")

    if schema_cache._cache_enabled(env):
        ttl = schema_cache._cache_ttl(env)

        def _compute():
            return _get_views_raw(env, model_name)

        return schema_cache.get_or_compute(cache_key, ttl, _compute)

    return _get_views_raw(env, model_name)


def _get_views_raw(env, model_name: str) -> dict:
    model = _resolve_model(env, model_name)

    # Recorre el MRO para reunir los métodos action_* / button_* con su clase de origen.
    seen: set = set()
    callable_methods = []
    for cls in type(model).__mro__:
        if cls is object:
            continue
        module = getattr(cls, "__module__", "") or ""
        if module.split(".")[0] in ("builtins", "abc", "functools", "threading", "logging"):
            continue
        for name, attr in cls.__dict__.items():
            if name in seen:
                continue
            if name.startswith(("action_", "button_")) and callable(attr):
                seen.add(name)
                callable_methods.append({
                    "name": name,
                    "defined_in": f"{module}.{cls.__qualname__}",
                })

    callable_methods.sort(key=lambda m: m["name"])

    bound_actions = env["ir.actions.server"].search_read(
        [("binding_model_id.model", "=", model_name)],
        ["name", "state", "binding_type"],
        limit=50,
    )

    window_actions = env["ir.actions.act_window"].search_read(
        [("res_model", "=", model_name)],
        ["name", "view_mode"],
        limit=20,
    )

    reports = env["ir.actions.report"].search_read(
        [("model", "=", model_name)],
        ["name", "report_name", "report_type"],
        limit=20,
    )

    return {
        "model": model_name,
        "callable_methods": callable_methods,
        "action_menu_items": [
            {"name": a["name"], "type": a["state"], "binding": a["binding_type"]}
            for a in bound_actions
        ],
        "window_actions": [
            {"name": a["name"], "view_modes": a["view_mode"]}
            for a in window_actions
        ],
        "available_reports": [
            {"name": r["name"], "report_name": r["report_name"], "type": r["report_type"]}
            for r in reports
        ],
    }


def _onchange(env, args: dict):
    model_name = args["model"]
    values = args.get("values") or {}
    field_onchange = args.get("field_onchange") or []

    model = _resolve_model(env, model_name)

    _check_write_fields(env, model_name, values)

    # Odoo 19: fields_spec es {campo: {}}; incluye todos los campos del modelo
    # permitidos para recibir también los valores recalculados.
    allowed = _get_field_restrictions(env, model_name)
    # fields_get ya excluye los campos cuyo groups= no alcanza al usuario.
    onchange_spec = {
        fname: {} for fname, fdef in model.fields_get(attributes=["type"]).items()
        if fdef["type"] != "binary" and (allowed is None or fname in allowed)
    }
    result = model.onchange(values, field_onchange, onchange_spec)

    # Serializa el resultado — omite las listas de comandos one2many para no inflar el contexto
    raw_values = result.get("value", {})
    computed = {}
    for key, val in raw_values.items():
        if isinstance(val, list):
            computed[key] = f"[{len(val)} registros one2many — use odoo_search_read para leerlos]"
        elif isinstance(val, tuple) and len(val) == 2:
            computed[key] = {"id": val[0], "display_name": val[1]}
        elif isinstance(val, dict) and "id" in val:
            computed[key] = {"id": val["id"], "display_name": val.get("display_name")}
        else:
            computed[key] = val

    return {
        "model": model_name,
        "triggered_fields": field_onchange,
        "computed_values": computed,
        "domain_updates": result.get("domain", {}),
        "warning": result.get("warning"),
    }


# ---------------------------------------------------------------------------
# Herramientas de contexto y catálogo (para clientes sin soporte de MCP Resources)
# ---------------------------------------------------------------------------


def _get_context(env, _args: dict):
    """Devuelve el contexto de negocio de Odoo como diccionario (los mismos datos que el recurso odoo://context)."""
    from . import resource_service
    return {"context": json.loads(resource_service._context(env))}


# ---------------------------------------------------------------------------
# Utilidad de restricción de campos en escritura
# ---------------------------------------------------------------------------


def _check_write_fields(env, model_name: str, values: dict) -> None:
    """Lanza PermissionError si *values* contiene campos fuera de la lista permitida del token."""
    allowed = _get_field_restrictions(env, model_name)
    if allowed is None:
        return  # sin restricción
    blocked = [k for k in values if k not in allowed]
    if blocked:
        raise PermissionError(
            f"La escritura en el/los campo(s) {blocked!r} del modelo {model_name!r} no está permitida "
            f"por las restricciones de campos de este token."
        )


def _check_required_fields(env, model_name: str, values: dict) -> None:
    """Lanza ValueError con los campos obligatorios que faltan en *values* y no tienen valor por defecto.

    Llama a default_get() para que los campos con valor por defecto en el servidor
    (p. ej. secuencias, usuario actual) no se marquen como faltantes.
    """
    model = _resolve_model(env, model_name)
    field_defs = model.fields_get(attributes=["required"])
    required_names = [f for f, d in field_defs.items() if d.get("required")]

    if not required_names:
        return

    provided = set(values)

    try:
        defaults = model.default_get(required_names)
        has_default = set(defaults)
    except Exception:
        has_default = set()

    missing = [f for f in required_names if f not in provided and f not in has_default]
    if missing:
        raise ValueError(
            f"Falta(n) campo(s) obligatorio(s) para el modelo {model_name!r}: {missing}. "
            f"Llame a odoo_fields_get(model='{model_name}', "
            f"attributes=['required', 'string', 'relation']) para inspeccionar el esquema, "
            f"y reintente incluyendo los campos faltantes."
        )


# ---------------------------------------------------------------------------
# Utilidad
# ---------------------------------------------------------------------------


def _resolve_model(env, model_name: str):
    if model_name not in env.registry:
        raise ValueError(f"El modelo {model_name!r} no se encontró en el registro de Odoo")
    return env[model_name]

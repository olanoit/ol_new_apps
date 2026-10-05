"""
Ejecutor de trabajos asíncronos MCP: lógica de ejecución de cada tipo de operación.

Cada función pública recibe:
  env     — Environment de Odoo (ya lleva mcp_scope + mcp_restrictions en el contexto)
  args    — diccionario con los argumentos propios de la operación
  job     — recordset de mcp.job (un solo registro) para ir actualizando el progreso

Todas las funciones devuelven un diccionario que se serializa a JSON y se guarda en job.result.
Los errores por registro se acumulan en lugar de abortar todo el lote.
"""
import csv
import io
import json
import logging

from odoo import fields

_logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Utilidad de progreso
# ---------------------------------------------------------------------------

def _update_progress(job, processed: int, total: int):
    """Guarda el porcentaje de progreso en el registro del trabajo y hace commit.

    El commit es intencionado: los trabajos largos deben liberar los bloqueos de
    fila de la tabla del lote y hacer visible el progreso intermedio a los clientes
    que consultan el estado. Es aceptable en contexto de cron según CLAUDE.md.
    """
    if total > 0:
        pct = min(99, int(processed / total * 100))
    else:
        pct = 0
    try:
        job.write({"progress": pct, "processed_records": processed, "total_records": total})
        job.env.cr.commit()
    except Exception:
        _logger.debug("MCP job_runner: no se pudo actualizar el progreso del trabajo %s", job.id)


# ---------------------------------------------------------------------------
# Actualización masiva
# ---------------------------------------------------------------------------

def run_bulk_update(env, args: dict, job) -> dict:
    """args: {model, domain, values, batch_size=100}"""
    model_name = args.get("model")
    domain = args.get("domain") or []
    values = args.get("values") or {}
    batch_size = int(args.get("batch_size") or _DEFAULT_BATCH_SIZE)

    if not model_name:
        raise ValueError("bulk_update requiere 'model'")
    if not values:
        raise ValueError("bulk_update requiere 'values'")
    if model_name not in env.registry:
        raise ValueError(f"Modelo {model_name!r} no encontrado en el registro de Odoo")

    model = env[model_name]
    records = model.search(domain)
    total = len(records)
    processed = 0
    errors = []

    for i in range(0, total, batch_size):
        batch = records[i: i + batch_size]
        try:
            batch.write(values)
        except Exception as exc:
            _logger.warning("bulk_update: error en el lote (ids %s): %s", batch.ids, exc)
            errors.append({"ids": batch.ids, "error": str(exc)})
        processed += len(batch)
        _update_progress(job, processed, total)

    return {
        "model": model_name,
        "total": total,
        "updated": processed - sum(len(e["ids"]) for e in errors),
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Creación masiva
# ---------------------------------------------------------------------------

def run_bulk_create(env, args: dict, job) -> dict:
    """args: {model, records: [...]}"""
    model_name = args.get("model")
    records_data = args.get("records") or []

    if not model_name:
        raise ValueError("bulk_create requiere 'model'")
    if not records_data:
        raise ValueError("bulk_create requiere la lista 'records'")
    if model_name not in env.registry:
        raise ValueError(f"Modelo {model_name!r} no encontrado en el registro de Odoo")

    total = len(records_data)
    created_ids = []
    errors = []

    model = env[model_name]
    batch_size = _DEFAULT_BATCH_SIZE

    for i in range(0, total, batch_size):
        batch = records_data[i: i + batch_size]
        try:
            created = model.create(batch)
            created_ids.extend(created.ids)
        except Exception as exc:
            _logger.warning("bulk_create: error en el lote (desplazamiento %d): %s", i, exc)
            errors.append({"offset": i, "count": len(batch), "error": str(exc)})
        _update_progress(job, min(i + batch_size, total), total)

    return {
        "model": model_name,
        "total_requested": total,
        "created": len(created_ids),
        "created_ids": created_ids[:500],  # límite para no generar un resultado demasiado grande
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Eliminación masiva
# ---------------------------------------------------------------------------

def run_bulk_unlink(env, args: dict, job) -> dict:
    """args: {model, domain}"""
    model_name = args.get("model")
    domain = args.get("domain") or []

    if not model_name:
        raise ValueError("bulk_unlink requiere 'model'")
    if model_name not in env.registry:
        raise ValueError(f"Modelo {model_name!r} no encontrado en el registro de Odoo")

    model = env[model_name]
    records = model.search(domain)
    total = len(records)
    deleted = 0
    errors = []
    batch_size = _DEFAULT_BATCH_SIZE

    for i in range(0, total, batch_size):
        batch = records[i: i + batch_size]
        try:
            batch.unlink()
            deleted += len(batch)
        except Exception as exc:
            _logger.warning("bulk_unlink: error en el lote (ids %s): %s", batch.ids, exc)
            errors.append({"ids": batch.ids, "error": str(exc)})
        _update_progress(job, i + len(batch), total)

    return {
        "model": model_name,
        "total": total,
        "deleted": deleted,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Exportar CSV
# ---------------------------------------------------------------------------

def run_export_csv(env, args: dict, job) -> dict:
    """args: {model, domain, fields}
    Crea un ir.attachment y asigna job.attachment_id.
    Devuelve {attachment_id, row_count}.
    """
    model_name = args.get("model")
    domain = args.get("domain") or []
    field_names = args.get("fields") or []

    if not model_name:
        raise ValueError("export_csv requiere 'model'")
    if model_name not in env.registry:
        raise ValueError(f"Modelo {model_name!r} no encontrado en el registro de Odoo")

    model = env[model_name]

    if not field_names:
        all_fields = model.fields_get(attributes=["type"])
        field_names = [
            f for f, meta in all_fields.items()
            if meta["type"] not in ("binary", "one2many", "many2many")
        ][:80]

    records = model.search_read(domain, field_names)
    total = len(records)
    _update_progress(job, 0, total)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=field_names, extrasaction="ignore")
    writer.writeheader()
    for i, row in enumerate(records):
        # Serializa los valores que no son cadenas
        clean = {}
        for k, v in row.items():
            if isinstance(v, (list, tuple)) and len(v) == 2 and isinstance(v[0], int):
                clean[k] = v[1]  # Many2one: toma el nombre visible
            elif isinstance(v, list):
                clean[k] = ";".join(str(x) for x in v)
            elif v is None or v is False:
                clean[k] = ""
            else:
                clean[k] = v
        writer.writerow(clean)
        if (i + 1) % _DEFAULT_BATCH_SIZE == 0:
            _update_progress(job, i + 1, total)

    csv_bytes = buf.getvalue().encode("utf-8-sig")
    import base64
    ts = fields.Datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{model_name.replace('.', '_')}_{ts}.csv"

    attachment = env["ir.attachment"].sudo().create({
        "name": filename,
        "datas": base64.b64encode(csv_bytes).decode(),
        "mimetype": "text/csv",
        "res_model": "mcp.job",
        "res_id": job.id,
    })

    job.sudo().write({"attachment_id": attachment.id})

    return {
        "model": model_name,
        "row_count": total,
        "attachment_id": attachment.id,
        "filename": filename,
        "download_url": f"/web/content/{attachment.id}?download=1",
    }


# ---------------------------------------------------------------------------
# Exportar XLSX
# ---------------------------------------------------------------------------

def run_export_xlsx(env, args: dict, job) -> dict:
    """args: {model, domain, fields}
    Usa xlsxwriter si está disponible; si no, recurre a CSV.
    """
    try:
        import xlsxwriter  # noqa: F401 — solo comprueba que esté disponible
        return _export_xlsx_native(env, args, job)
    except ImportError:
        _logger.info("xlsxwriter no está disponible: se exporta a CSV")
        return run_export_csv(env, args, job)


def _export_xlsx_native(env, args: dict, job) -> dict:
    import xlsxwriter
    import base64

    model_name = args.get("model")
    domain = args.get("domain") or []
    field_names = args.get("fields") or []

    if not model_name:
        raise ValueError("export_xlsx requiere 'model'")
    if model_name not in env.registry:
        raise ValueError(f"Modelo {model_name!r} no encontrado en el registro de Odoo")

    model = env[model_name]

    if not field_names:
        all_fields = model.fields_get(attributes=["type"])
        field_names = [
            f for f, meta in all_fields.items()
            if meta["type"] not in ("binary", "one2many", "many2many")
        ][:80]

    records = model.search_read(domain, field_names)
    total = len(records)
    _update_progress(job, 0, total)

    buf = io.BytesIO()
    workbook = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = workbook.add_worksheet("Exportación")
    bold = workbook.add_format({"bold": True})

    for col, fname in enumerate(field_names):
        ws.write(0, col, fname, bold)

    for row_idx, record in enumerate(records):
        for col, fname in enumerate(field_names):
            val = record.get(fname)
            if isinstance(val, (list, tuple)) and len(val) == 2 and isinstance(val[0], int):
                val = val[1]
            elif isinstance(val, list):
                val = ";".join(str(x) for x in val)
            elif val is None or val is False:
                val = ""
            ws.write(row_idx + 1, col, val)
        if (row_idx + 1) % _DEFAULT_BATCH_SIZE == 0:
            _update_progress(job, row_idx + 1, total)

    workbook.close()
    xlsx_bytes = buf.getvalue()

    ts = fields.Datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{model_name.replace('.', '_')}_{ts}.xlsx"

    attachment = env["ir.attachment"].sudo().create({
        "name": filename,
        "datas": base64.b64encode(xlsx_bytes).decode(),
        "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "res_model": "mcp.job",
        "res_id": job.id,
    })

    job.sudo().write({"attachment_id": attachment.id})

    return {
        "model": model_name,
        "row_count": total,
        "attachment_id": attachment.id,
        "filename": filename,
        "download_url": f"/web/content/{attachment.id}?download=1",
    }


# ---------------------------------------------------------------------------
# Personalizado / call_method
# ---------------------------------------------------------------------------

def run_custom(env, args: dict, job) -> dict:
    """args: {model, method, ids, args, kwargs}
    Replica la lógica de tool_executor._call_method, pero en modo asíncrono.
    """
    model_name = args.get("model")
    method_name = args.get("method")
    ids = args.get("ids") or []
    method_args = args.get("args") or []
    method_kwargs = args.get("kwargs") or {}

    if not model_name:
        raise ValueError("call_method requiere 'model'")
    if not method_name:
        raise ValueError("call_method requiere 'method'")
    if model_name not in env.registry:
        raise ValueError(f"Modelo {model_name!r} no encontrado en el registro de Odoo")

    # Respeta la misma lista de bloqueo que la herramienta síncrona
    _DENYLIST = frozenset({
        "sudo", "with_user", "with_company", "with_context", "with_env",
        "execute", "execute_kw",
        "search", "search_read", "search_count", "read", "create", "write", "unlink",
        "read_group", "_read_group", "name_search", "name_get", "default_get",
        "browse", "exists", "ensure_one", "mapped", "filtered", "sorted",
        "invalidate_recordset",
    })
    if method_name.startswith("_"):
        raise ValueError(f"El método {method_name!r} es privado y no se puede llamar vía MCP.")
    if method_name in _DENYLIST:
        raise ValueError(f"El método {method_name!r} está bloqueado.")

    model = env[model_name]
    if not hasattr(model, method_name):
        raise ValueError(f"Método {method_name!r} no encontrado en el modelo {model_name!r}")
    # Mismas reglas que el RPC de Odoo: rechaza @api.private y atributos inseguros.
    from odoo.service.model import get_public_method
    get_public_method(model, method_name)

    target = model.browse(ids) if ids else model
    result = getattr(target, method_name)(*method_args, **method_kwargs)

    _update_progress(job, 1, 1)

    return {"result": result if isinstance(result, (dict, list, str, int, float, bool, type(None))) else str(result)}

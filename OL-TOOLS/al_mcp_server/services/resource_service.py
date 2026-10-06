"""
Recursos MCP — contexto de negocio expuesto como recursos de lectura.

Claude los lee una vez al iniciar la sesión para entender la instancia de Odoo
sin necesitar varias llamadas a herramientas para descubrir esquemas y datos de la compañía.

Recursos:
  odoo://context              compañía, usuario, módulos instalados, fecha del servidor
  odoo://catalog              todos los modelos instalados con sus nombres
  odoo://model/{name}         definiciones de campos de un modelo concreto
  odoo://chatter/{model}/{id} últimos 20 mensajes del chatter de un registro
  odoo://attachment/{id}      metadatos del adjunto y vista previa del contenido
"""

import base64
import json
import logging
import re
from datetime import date

from . import schema_cache

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Definiciones de recursos y plantillas (las devuelve resources/list)
# ---------------------------------------------------------------------------

RESOURCES = [
    {
        "uri": "odoo://context",
        "name": "Contexto de negocio de Odoo",
        "description": (
            "Información de la compañía (nombre, moneda, zona horaria), usuario actual, "
            "lista de módulos instalados y fecha del servidor. "
            "Lea esto siempre primero antes de responder preguntas de negocio."
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "odoo://catalog",
        "name": "Catálogo de modelos de Odoo",
        "description": (
            "Todos los modelos de Odoo disponibles con su nombre técnico y etiqueta para mostrar. "
            "Úselo para encontrar el nombre de modelo correcto antes de consultar."
        ),
        "mimeType": "application/json",
    },
]

RESOURCE_TEMPLATES = [
    {
        "uriTemplate": "odoo://model/{name}",
        "name": "Esquema de modelo de Odoo",
        "description": (
            "Definiciones de campos (etiqueta, tipo, obligatorio, valores de selección, modelo relacionado) "
            "para cualquier modelo de Odoo. Léalo antes de usar odoo_search_read u odoo_create "
            "para saber qué campos y valores son válidos."
        ),
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "odoo://chatter/{model}/{id}",
        "name": "Chatter de registro de Odoo",
        "description": (
            "Los últimos 20 mensajes del chatter de un registro específico — comentarios, correos, "
            "notas internas y registros de actividad. "
            "Léalo antes de responder a un cliente o actualizar un registro para ver el historial completo. "
            "Ejemplo: odoo://chatter/sale.order/201"
        ),
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "odoo://attachment/{id}",
        "name": "Adjunto de Odoo",
        "description": (
            "Metadatos y vista previa del contenido de un registro ir.attachment. "
            "Los archivos de texto, JSON, XML y CSV de menos de 50 KB incluyen vista previa completa del contenido. "
            "Los archivos binarios (PDF, imágenes) devuelven solo metadatos con una URL de descarga. "
            "Ejemplo: odoo://attachment/42"
        ),
        "mimeType": "application/json",
    },
]


# ---------------------------------------------------------------------------
# Distribuidor de recursos
# ---------------------------------------------------------------------------

def _enforce_model(env, model_name: str) -> None:
    """Aplica al recurso la misma lista de modelos permitidos/denegados que a las herramientas."""
    from .tool_executor import _enforce_model_access
    _enforce_model_access(env, "resources/read", {"model": model_name})


def read_resource(uri: str, env) -> str:
    """Resuelve la URI de un recurso y devuelve su contenido JSON como cadena."""
    if uri == "odoo://context":
        return _context(env)
    if uri == "odoo://catalog":
        return _catalog(env)
    if uri.startswith("odoo://model/"):
        model_name = uri[len("odoo://model/"):]
        _enforce_model(env, model_name)
        return _model_schema(model_name, env)
    if uri.startswith("odoo://chatter/"):
        rest = uri[len("odoo://chatter/"):]
        model_name, record_id = rest.rsplit("/", 1)
        _enforce_model(env, model_name)
        _enforce_model(env, "mail.message")
        return _chatter(model_name, record_id, env)
    if uri.startswith("odoo://attachment/"):
        attachment_id = uri[len("odoo://attachment/"):]
        _enforce_model(env, "ir.attachment")
        return _attachment(attachment_id, env)
    raise ValueError(f"URI de recurso desconocida: {uri!r}")


# ---------------------------------------------------------------------------
# Implementación de los recursos
# ---------------------------------------------------------------------------

def _context(env) -> str:
    company = env.company
    user = env.user

    installed = env["ir.module.module"].search_read(
        [("state", "=", "installed")],
        ["name", "shortdesc"],
        order="name",
        limit=500,
    )

    return json.dumps(
        {
            "company": {
                "name": company.name,
                "currency": company.currency_id.name,
                "country": company.country_id.name or "",
                "timezone": company.partner_id.tz or "UTC",
            },
            "user": {
                "id": user.id,
                "name": user.name,
                "login": user.login,
                "language": user.lang or "en_US",
            },
            "installed_modules": [
                {"name": m["name"], "label": m["shortdesc"]} for m in installed
            ],
            "server_date": str(date.today()),
        },
        ensure_ascii=False,
        indent=2,
    )


def _catalog(env) -> str:
    if schema_cache._cache_enabled(env):
        ttl = schema_cache._cache_ttl(env)

        def _compute():
            rows = env["ir.model"].search_read(
                [("transient", "=", False)],
                ["model", "name"],
                order="name",
                limit=1000,
            )
            return json.dumps({"total": len(rows), "models": rows}, ensure_ascii=False, indent=2)

        return schema_cache.get_or_compute(schema_cache.scoped_key(env, "catalog"), ttl, _compute)

    models = env["ir.model"].search_read(
        [("transient", "=", False)],
        ["model", "name"],
        order="name",
        limit=1000,
    )
    return json.dumps({"total": len(models), "models": models}, ensure_ascii=False, indent=2)


def _model_schema(model_name: str, env) -> str:
    if model_name not in env.registry:
        raise ValueError(f"No se encontró el modelo {model_name!r} en el registro de Odoo")
    from .tool_executor import _get_field_restrictions
    allowed = _get_field_restrictions(env, model_name)
    if allowed is not None:
        # Con lista de campos permitidos no se usa la caché compartida.
        flds = env[model_name].fields_get(
            allfields=list(allowed),
            attributes=["string", "type", "required", "readonly", "help", "selection", "relation"],
        )
        return json.dumps({"model": model_name, "fields": flds}, ensure_ascii=False, default=str, indent=2)

    if schema_cache._cache_enabled(env):
        ttl = schema_cache._cache_ttl(env)
        cache_key = schema_cache.scoped_key(env, f"model_schema:{model_name}")

        def _compute():
            m = env[model_name]
            flds = m.fields_get(
                attributes=["string", "type", "required", "readonly", "help", "selection", "relation"]
            )
            return json.dumps(
                {"model": model_name, "fields": flds},
                ensure_ascii=False,
                default=str,
                indent=2,
            )

        return schema_cache.get_or_compute(cache_key, ttl, _compute)

    model = env[model_name]
    fields = model.fields_get(
        attributes=["string", "type", "required", "readonly", "help", "selection", "relation"]
    )
    return json.dumps(
        {"model": model_name, "fields": fields},
        ensure_ascii=False,
        default=str,
        indent=2,
    )


def _chatter(model_name: str, record_id: str, env) -> str:
    if model_name not in env.registry:
        raise ValueError(f"No se encontró el modelo {model_name!r} en el registro de Odoo")

    rid = int(record_id)
    record = env[model_name].browse(rid)
    if not record.exists():
        raise ValueError(f"No se encontró el registro {model_name}#{rid}")

    if "mail.message" not in env.registry:
        raise ValueError("El módulo 'mail' no está instalado — el chatter no está disponible")

    messages = env["mail.message"].search_read(
        [
            ("model", "=", model_name),
            ("res_id", "=", rid),
            ("message_type", "in", ["comment", "email", "email_outgoing", "notification"]),
        ],
        ["author_id", "date", "body", "subtype_id", "message_type", "attachment_ids"],
        order="date desc",
        limit=20,
    )

    cleaned = []
    for msg in messages:
        cleaned.append({
            "id": msg["id"],
            "author": msg["author_id"][1] if msg["author_id"] else "Desconocido",
            "date": str(msg["date"]),
            "body": _strip_html(msg["body"])[:500],
            "type": msg["message_type"],
            "subtype": msg["subtype_id"][1] if msg["subtype_id"] else None,
            "attachment_ids": msg["attachment_ids"],
        })

    return json.dumps(
        {
            "model": model_name,
            "record_id": rid,
            "total_shown": len(cleaned),
            "note": "Mostrando los últimos 20 mensajes. Se omiten los mensajes más antiguos.",
            "messages": cleaned,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _attachment(attachment_id: str, env) -> str:
    rec = env["ir.attachment"].browse(int(attachment_id))
    if not rec.exists():
        raise ValueError(f"No se encontró el adjunto {attachment_id}")
    if rec.res_model:
        _enforce_model(env, rec.res_model)

    result = {
        "id": rec.id,
        "name": rec.name,
        "mimetype": rec.mimetype or "application/octet-stream",
        "file_size": rec.file_size,
        "model": rec.res_model,
        "record_id": rec.res_id,
        "create_date": str(rec.create_date),
        "download_url": rec.url or f"/web/content/{rec.id}?download=1",
    }

    # Solo se incluye vista previa del contenido en formatos de texto legibles
    _TEXT_MIMES = ("text/", "application/json", "application/xml",
                   "application/csv", "application/javascript")
    is_text = rec.mimetype and any(rec.mimetype.startswith(m) for m in _TEXT_MIMES)
    size_ok = rec.file_size and rec.file_size < 50 * 1024  # límite de 50 KB

    if is_text and size_ok and rec.datas:
        try:
            raw = base64.b64decode(rec.datas).decode("utf-8", errors="replace")
            result["content_preview"] = raw[:5000]
            if len(raw) > 5000:
                result["content_truncated"] = True
        except Exception:
            result["content_preview"] = "[No se pudo decodificar el contenido del adjunto]"
    elif is_text and not size_ok:
        result["content_preview"] = (
            f"[Archivo demasiado grande ({rec.file_size} bytes) — descárguelo mediante download_url]"
        )
    else:
        result["content_preview"] = (
            f"[Archivo binario ({rec.mimetype}) — descárguelo mediante download_url]"
        )

    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


# ---------------------------------------------------------------------------
# Utilidad HTML
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Quita las etiquetas HTML para mostrar limpio el cuerpo del chatter."""
    if not html:
        return ""
    html = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', '', html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'&nbsp;', ' ', html)
    html = re.sub(r'&amp;', '&', html)
    html = re.sub(r'&lt;', '<', html)
    html = re.sub(r'&gt;', '>', html)
    html = re.sub(r'&quot;', '"', html)
    return re.sub(r'\s+', ' ', html).strip()

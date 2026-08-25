# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
MCP tool definitions and handlers for portal page management.

These tools allow AI clients to create, list, and update shareable portal
pages that display live Odoo data via KPI tiles, charts, and tables.

Scope enforcement:
  - 'read'  → only odoo_list_portal_pages is permitted
  - 'write' → create + list + update
  - 'admin' → all (same as write for portal tools)

Handlers are called by the consolidation layer (tool_executor.py or its
replacement) via TOOL_HANDLERS dispatch table.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scope sets
# ---------------------------------------------------------------------------

_PORTAL_READ_TOOLS = frozenset({"odoo_list_portal_pages"})
_PORTAL_WRITE_TOOLS = frozenset({"odoo_create_portal_page", "odoo_update_portal_page"})

# ---------------------------------------------------------------------------
# Tool schema definitions (MCP tool manifest)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "odoo_create_portal_page",
        "description": (
            "Crea una página de portal compartible que muestra datos en vivo de Odoo mediante tarjetas KPI, "
            "gráficos y tablas. Devuelve la URL de la página y la URL de incrustación. "
            "La página es accesible inmediatamente después de su creación. "
            "Use esto cuando un usuario pida 'crear un tablero', 'crear una página de informe de ventas', "
            "'compartir una vista KPI' o solicitudes similares."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["name", "spec"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Título para mostrar de la página de portal (p. ej. 'Sales Dashboard Q1 2026').",
                },
                "description": {
                    "type": "string",
                    "description": "Descripción breve opcional que se muestra en la página.",
                },
                "is_public": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Si es true, cualquiera con la URL puede ver la página sin iniciar sesión. "
                        "Si es false (predeterminado), los espectadores necesitan un inicio de sesión de Odoo o el token de incrustación."
                    ),
                },
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "auto"],
                    "default": "light",
                    "description": "Tema visual de la página.",
                },
                "spec": {
                    "type": "object",
                    "description": (
                        "Especificación del diseño de la página. Debe incluir un arreglo 'widgets'. "
                        "Tipos de widget: 'kpi', 'chart', 'table'. "
                        "Ejemplo: {\"title\": \"Revenue\", \"widgets\": [{\"type\": \"kpi\", "
                        "\"title\": \"Total Revenue\", \"model\": \"sale.order\", "
                        "\"domain\": [[\"state\",\"in\",[\"sale\",\"done\"]]], "
                        "\"field\": \"amount_total\", \"aggregate\": \"sum\", "
                        "\"format\": \"currency\"}]}"
                    ),
                    "properties": {
                        "title": {"type": "string"},
                        "subtitle": {"type": "string"},
                        "filters": {"type": "array"},
                        "widgets": {"type": "array"},
                    },
                },
            },
        },
    },
    {
        "name": "odoo_list_portal_pages",
        "description": (
            "Lista las páginas de portal propiedad del usuario actual. "
            "Devuelve el ID, nombre, slug, URL, número de vistas y estado de activación de cada página. "
            "Use esto para encontrar tableros existentes antes de crear nuevos."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "enabled_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "Si es true, solo devuelve las páginas activadas (predeterminado: true).",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Número máximo de páginas a devolver.",
                },
            },
        },
    },
    {
        "name": "odoo_update_portal_page",
        "description": (
            "Actualiza el contenido o la configuración de una página de portal existente. "
            "Solo se cambiarán los campos que proporcione; los campos omitidos permanecen sin cambios. "
            "Use el 'id' de la página de odoo_list_portal_pages para identificar la página."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "El ID de registro de Odoo de la página de portal a actualizar.",
                },
                "name": {
                    "type": "string",
                    "description": "Nuevo título para mostrar.",
                },
                "description": {
                    "type": "string",
                    "description": "Nuevo texto de descripción.",
                },
                "spec": {
                    "type": "object",
                    "description": "Especificación de reemplazo de la página. Reemplaza la especificación completa si se proporciona.",
                },
                "is_public": {
                    "type": "boolean",
                    "description": "Actualiza el indicador de acceso público.",
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Activa o desactiva la página.",
                },
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "auto"],
                    "description": "Actualiza el tema visual.",
                },
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------


def _handle_create_portal_page(env, args: dict) -> dict:
    """Create a new mcp.portal.page record and return its URLs."""
    _check_scope(env, "odoo_create_portal_page")

    name = args.get("name", "").strip()
    if not name:
        raise ValueError("'name' es obligatorio y no puede estar vacío.")

    spec_obj = args.get("spec")
    if spec_obj is None:
        raise ValueError("'spec' es obligatorio.")
    if not isinstance(spec_obj, dict):
        raise ValueError("'spec' debe ser un objeto JSON.")

    spec_text = json.dumps(spec_obj, ensure_ascii=False, indent=2)

    # Validate spec via model method
    Page = env["mcp.portal.page"]
    Page.parse_spec(spec_text)

    vals = {
        "name": name,
        "spec": spec_text,
        "is_public": bool(args.get("is_public", False)),
        "theme": args.get("theme", "light"),
    }
    desc = args.get("description")
    if desc is not None:
        vals["description"] = desc

    page = Page.create(vals)

    base = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    return {
        "id": page.id,
        "name": page.name,
        "slug": page.slug,
        "url": f"{base}/mcp-page/{page.slug}",
        "embed_url": f"{base}/mcp-page/{page.slug}?token={page.access_token}",
        "is_public": page.is_public,
        "theme": page.theme,
        "message": (
            f"Página de portal '{page.name}' creada. "
            f"Comparta la URL con los espectadores: {base}/mcp-page/{page.slug}"
        ),
    }


def _handle_list_portal_pages(env, args: dict) -> dict:
    """Return a list of portal pages owned by the current user."""
    enabled_only = args.get("enabled_only", True)
    limit = min(int(args.get("limit", 20)), 100)

    domain = [("created_by", "=", env.uid)]
    if enabled_only:
        domain.append(("enabled", "=", True))

    pages = env["mcp.portal.page"].search(domain, limit=limit, order="create_date desc")
    base = env["ir.config_parameter"].sudo().get_param("web.base.url", "")

    result = []
    for p in pages:
        result.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "url": f"{base}/mcp-page/{p.slug}",
            "is_public": p.is_public,
            "enabled": p.enabled,
            "view_count": p.view_count,
            "last_viewed": p.last_viewed.isoformat() if p.last_viewed else None,
            "theme": p.theme,
        })

    return {"count": len(result), "pages": result}


def _handle_update_portal_page(env, args: dict) -> dict:
    """Update fields on an existing portal page."""
    _check_scope(env, "odoo_update_portal_page")

    page_id = int(args.get("id", 0))
    if not page_id:
        raise ValueError("'id' (ID de registro entero) es obligatorio.")

    page = env["mcp.portal.page"].browse(page_id)
    if not page.exists():
        raise ValueError(f"No se encontró la página de portal con id={page_id}.")

    vals = {}
    if "name" in args:
        vals["name"] = args["name"]
    if "description" in args:
        vals["description"] = args["description"]
    if "is_public" in args:
        vals["is_public"] = bool(args["is_public"])
    if "enabled" in args:
        vals["enabled"] = bool(args["enabled"])
    if "theme" in args:
        vals["theme"] = args["theme"]
    if "spec" in args:
        spec_obj = args["spec"]
        if not isinstance(spec_obj, dict):
            raise ValueError("'spec' debe ser un objeto JSON.")
        spec_text = json.dumps(spec_obj, ensure_ascii=False, indent=2)
        env["mcp.portal.page"].parse_spec(spec_text)
        vals["spec"] = spec_text

    if not vals:
        return {"id": page_id, "message": "No se proporcionaron campos para actualizar.", "updated": False}

    page.write(vals)

    base = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    return {
        "id": page.id,
        "name": page.name,
        "slug": page.slug,
        "url": f"{base}/mcp-page/{page.slug}",
        "updated": True,
        "message": f"Página de portal '{page.name}' actualizada correctamente.",
    }


# ---------------------------------------------------------------------------
# Scope guard
# ---------------------------------------------------------------------------


def _check_scope(env, tool_name: str) -> None:
    """Raise PermissionError if the current MCP scope does not allow *tool_name*."""
    scope = env.context.get("mcp_scope", "write")
    if scope == "admin" or scope == "write":
        return
    if scope == "read" and tool_name not in _PORTAL_READ_TOOLS:
        raise PermissionError(
            f"La herramienta {tool_name!r} requiere al menos alcance 'write'. "
            f"Este token está restringido al alcance 'read'."
        )


# ---------------------------------------------------------------------------
# Dispatch table — consumed by the consolidation layer
# ---------------------------------------------------------------------------

TOOL_HANDLERS = {
    "odoo_create_portal_page": _handle_create_portal_page,
    "odoo_list_portal_pages": _handle_list_portal_pages,
    "odoo_update_portal_page": _handle_update_portal_page,
}

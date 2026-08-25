# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
MCP tool definitions and handlers for HTML artifact management.

Artifacts are free-form interactive HTML snippets (HTML + optional CSS + JS)
served through a strictly sandboxed iframe. They differ from portal pages:
portal pages are spec-driven dashboards over live Odoo data, while artifacts
are opaque AI-generated markup (visualizations, mini-apps, prototypes).

Scope enforcement:
  - 'read'  → only odoo_list_html_artifacts, odoo_get_html_artifact
  - 'write' → create + list + get + update
  - 'admin' → all (same as write for artifact tools)
"""

import logging

_logger = logging.getLogger(__name__)


_ARTIFACT_READ_TOOLS = frozenset({"odoo_list_html_artifacts", "odoo_get_html_artifact"})
_ARTIFACT_WRITE_TOOLS = frozenset({"odoo_create_html_artifact", "odoo_update_html_artifact"})


TOOL_DEFINITIONS = [
    {
        "name": "odoo_create_html_artifact",
        "description": (
            "Crea un artefacto HTML interactivo renderizado dentro de un iframe estrictamente aislado (sandbox). "
            "Use esto cuando un usuario pida 'crear una mini-app', 'renderizar un gráfico', 'crear una "
            "calculadora', 'mostrar una visualización', 'hacer una demo interactiva' o desee cualquier "
            "página HTML interactiva de forma libre. Devuelve la URL pública y la URL de incrustación. "
            "Seguridad: el artefacto se ejecuta sin acceso a la página principal de Odoo (sin cookies, "
            "sin acceso al DOM). La red saliente está bloqueada. CDN permitidos para scripts/estilos: "
            "cdn.jsdelivr.net, unpkg.com, cdnjs.cloudflare.com, fonts.googleapis.com."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["name", "html"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Título para mostrar del artefacto (p. ej. 'Tip Calculator').",
                },
                "description": {
                    "type": "string",
                    "description": "Descripción breve opcional.",
                },
                "html": {
                    "type": "string",
                    "description": (
                        "Marcado HTML que se colocará dentro del <body> del documento aislado. "
                        "Puede incluir etiquetas <style> y <script> en línea."
                    ),
                },
                "css": {
                    "type": "string",
                    "description": "CSS opcional inyectado en una etiqueta <style> en <head>.",
                },
                "js": {
                    "type": "string",
                    "description": (
                        "JS opcional inyectado en una etiqueta <script> al final del <body>. "
                        "Se ejecuta dentro del sandbox sin acceso a la ventana principal."
                    ),
                },
                "is_public": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Si es true, cualquiera con la URL puede ver el artefacto sin iniciar sesión."
                    ),
                },
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "auto"],
                    "default": "light",
                    "description": "Tema visual de la página anfitriona que rodea el iframe.",
                },
            },
        },
    },
    {
        "name": "odoo_list_html_artifacts",
        "description": (
            "Lista los artefactos HTML propiedad del usuario actual. Devuelve el ID, nombre, "
            "slug, URL, número de vistas y estado de activación de cada artefacto. Use esto para "
            "encontrar artefactos existentes antes de crear nuevos."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "enabled_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "Si es true, solo devuelve los artefactos activados.",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Número máximo de artefactos a devolver.",
                },
            },
        },
    },
    {
        "name": "odoo_get_html_artifact",
        "description": (
            "Devuelve el contenido completo (html, css, js) de un artefacto HTML por id o slug. "
            "Use esto para inspeccionar o modificar un artefacto existente antes de llamar a update."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID de registro del artefacto."},
                "slug": {"type": "string", "description": "Slug del artefacto."},
            },
        },
    },
    {
        "name": "odoo_update_html_artifact",
        "description": (
            "Actualiza campos de un artefacto HTML existente. Solo se cambian los campos que "
            "proporcione; los campos omitidos permanecen sin cambios. Use el 'id' de odoo_list_html_artifacts."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer", "description": "El ID de registro del artefacto."},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "html": {"type": "string"},
                "css": {"type": "string"},
                "js": {"type": "string"},
                "is_public": {"type": "boolean"},
                "enabled": {"type": "boolean"},
                "theme": {"type": "string", "enum": ["light", "dark", "auto"]},
            },
        },
    },
]


def _check_scope(env, tool_name: str) -> None:
    scope = env.context.get("mcp_scope", "write")
    if scope in ("admin", "write"):
        return
    if scope == "read" and tool_name not in _ARTIFACT_READ_TOOLS:
        raise PermissionError(
            f"La herramienta {tool_name!r} requiere al menos alcance 'write'. "
            f"Este token está restringido al alcance 'read'."
        )


def _base_url(env) -> str:
    return env["ir.config_parameter"].sudo().get_param("web.base.url", "")


def _serialize(env, art) -> dict:
    base = _base_url(env)
    return {
        "id": art.id,
        "name": art.name,
        "slug": art.slug,
        "url": f"{base}/mcp-artifact/{art.slug}",
        "embed_url": f"{base}/mcp-artifact/{art.slug}?token={art.access_token}",
        "is_public": art.is_public,
        "enabled": art.enabled,
        "theme": art.theme,
        "view_count": art.view_count,
        "last_viewed": art.last_viewed.isoformat() if art.last_viewed else None,
    }


def _handle_create_html_artifact(env, args: dict) -> dict:
    _check_scope(env, "odoo_create_html_artifact")

    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("'name' es obligatorio y no puede estar vacío.")

    html = args.get("html")
    if not isinstance(html, str) or not html.strip():
        raise ValueError("'html' es obligatorio y debe ser una cadena no vacía.")

    vals = {
        "name": name,
        "html": html,
        "css": args.get("css") or False,
        "js": args.get("js") or False,
        "is_public": bool(args.get("is_public", False)),
        "theme": args.get("theme", "light"),
    }
    desc = args.get("description")
    if desc is not None:
        vals["description"] = desc

    art = env["mcp.html.artifact"].create(vals)
    result = _serialize(env, art)
    result["message"] = (
        f"Artefacto HTML '{art.name}' creado. Comparta la URL con los espectadores: {result['url']}"
    )
    return result


def _handle_list_html_artifacts(env, args: dict) -> dict:
    enabled_only = args.get("enabled_only", True)
    limit = min(int(args.get("limit", 20)), 100)

    domain = [("created_by", "=", env.uid)]
    if enabled_only:
        domain.append(("enabled", "=", True))

    arts = env["mcp.html.artifact"].search(domain, limit=limit, order="create_date desc")
    return {"count": len(arts), "artifacts": [_serialize(env, a) for a in arts]}


def _handle_get_html_artifact(env, args: dict) -> dict:
    art_id = args.get("id")
    slug = args.get("slug")
    if not art_id and not slug:
        raise ValueError("Debe proporcionar 'id' o 'slug'.")

    Artifact = env["mcp.html.artifact"]
    if art_id:
        art = Artifact.browse(int(art_id))
        if not art.exists():
            raise ValueError(f"No se encontró el artefacto HTML con id={art_id}.")
    else:
        art = Artifact.search([("slug", "=", slug)], limit=1)
        if not art:
            raise ValueError(f"No se encontró el artefacto HTML con slug={slug!r}.")

    if art.created_by.id != env.uid and not env.user.has_group("base.group_system"):
        raise PermissionError("No es propietario de este artefacto.")

    payload = _serialize(env, art)
    payload.update({
        "description": art.description or "",
        "html": art.html or "",
        "css": art.css or "",
        "js": art.js or "",
    })
    return payload


def _handle_update_html_artifact(env, args: dict) -> dict:
    _check_scope(env, "odoo_update_html_artifact")

    art_id = int(args.get("id", 0))
    if not art_id:
        raise ValueError("'id' (ID de registro entero) es obligatorio.")

    art = env["mcp.html.artifact"].browse(art_id)
    if not art.exists():
        raise ValueError(f"No se encontró el artefacto HTML con id={art_id}.")

    vals = {}
    for key in ("name", "description", "html", "css", "js", "theme"):
        if key in args:
            vals[key] = args[key]
    for key in ("is_public", "enabled"):
        if key in args:
            vals[key] = bool(args[key])

    if not vals:
        return {"id": art_id, "message": "No se proporcionaron campos para actualizar.", "updated": False}

    art.write(vals)
    result = _serialize(env, art)
    result["updated"] = True
    result["message"] = f"Artefacto HTML '{art.name}' actualizado correctamente."
    return result


TOOL_HANDLERS = {
    "odoo_create_html_artifact": _handle_create_html_artifact,
    "odoo_list_html_artifacts": _handle_list_html_artifacts,
    "odoo_get_html_artifact": _handle_get_html_artifact,
    "odoo_update_html_artifact": _handle_update_html_artifact,
}

# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
Controlador de páginas públicas del portal.

Rutas:
  GET /mcp-page/<slug>        — renderizado de la página completa (HTML)
  GET /mcp-page/<slug>/data   — datos en vivo de los widgets (JSON)
  GET /mcp-page/<slug>/embed  — renderizado incrustable en iframe (sin el marco de Odoo)

Reglas de autenticación (se aplican en orden):
  1. Si page.is_public → se permite a todos.
  2. Si la petición trae ?token=<access_token> que coincide con la página → se permite.
  3. Si el usuario con sesión es el dueño de la página o un administrador del sistema → se permite.
  4. Otros usuarios con sesión → 404; anónimos → redirección a /web/login.

Los datos de los widgets siempre se calculan con page.created_by como usuario de
ejecución, lo que limita el acceso a lo que puede ver el dueño de la página. Así una
página pública no filtra datos que el usuario que la mira no debería ver.
"""

import json
import logging

from markupsafe import Markup
from werkzeug.wrappers import Response

from odoo import http
from odoo.http import request
from odoo.tools import consteq
from odoo.tools.json import scriptsafe

from ..services.portal_renderer import compute_widget

_logger = logging.getLogger(__name__)


class McpPortalController(http.Controller):

    # ------------------------------------------------------------------
    # Renderizado de la página principal
    # ------------------------------------------------------------------

    @http.route(
        "/mcp-page/<string:slug>",
        type="http",
        auth="public",
        methods=["GET"],
        website=False,
        csrf=False,
    )
    def portal_page(self, slug, **kwargs):
        page = self._get_page_or_404(slug)
        if page is None:
            return request.not_found()

        auth_result = self._check_auth(page, kwargs.get("token", ""))
        if auth_result is not None:
            return auth_result

        widget_data = self._render_widgets(page, kwargs)
        spec = self._parse_spec_safe(page)
        page.sudo().write({
            "view_count": page.view_count + 1,
            "last_viewed": fields_now(),
        })

        qcontext = self._build_qcontext(page, spec, widget_data, kwargs.get("token", ""), embed=False)
        return request.render(
            "al_mcp_server.portal_page",
            qcontext,
            headers={"X-Frame-Options": "SAMEORIGIN"},
        )

    # ------------------------------------------------------------------
    # Ruta incrustable (sin el marco de Odoo, para iframes)
    # ------------------------------------------------------------------

    @http.route(
        "/mcp-page/<string:slug>/embed",
        type="http",
        auth="public",
        methods=["GET"],
        website=False,
        csrf=False,
    )
    def portal_page_embed(self, slug, **kwargs):
        page = self._get_page_or_404(slug)
        if page is None:
            return request.not_found()

        auth_result = self._check_auth(page, kwargs.get("token", ""))
        if auth_result is not None:
            return auth_result

        widget_data = self._render_widgets(page, kwargs)
        spec = self._parse_spec_safe(page)

        qcontext = self._build_qcontext(page, spec, widget_data, kwargs.get("token", ""), embed=True)
        return request.render(
            "al_mcp_server.portal_page",
            qcontext,
            headers={"X-Frame-Options": "ALLOWALL"},
        )

    # ------------------------------------------------------------------
    # Endpoint de datos JSON en vivo
    # ------------------------------------------------------------------

    @http.route(
        "/mcp-page/<string:slug>/data",
        type="http",
        auth="public",
        methods=["GET"],
        website=False,
        csrf=False,
    )
    def portal_page_data(self, slug, **kwargs):
        page = self._get_page_or_404(slug)
        if page is None:
            return _json_error("not_found", "Página no encontrada.", 404)

        auth_result = self._check_auth(page, kwargs.get("token", ""))
        if auth_result is not None:
            return _json_error("unauthorized", "Autenticación requerida.", 401)

        widget_data = self._render_widgets(page, kwargs)
        payload = json.dumps(
            {"slug": slug, "widgets": widget_data},
            default=_json_default,
            ensure_ascii=False,
        )
        return Response(
            payload,
            content_type="application/json; charset=utf-8",
            status=200,
        )

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _get_page_or_404(self, slug: str):
        """Devuelve el registro mcp.portal.page de *slug*, o None."""
        page = request.env["mcp.portal.page"].sudo().search(
            [("slug", "=", slug), ("enabled", "=", True)],
            limit=1,
        )
        return page or None

    def _check_auth(self, page, token: str):
        """Devuelve una respuesta de redirección o error si se deniega el acceso; si no, None."""
        if page.is_public:
            return None
        if token and page.access_token and consteq(token, page.access_token):
            return None
        if request.session and request.session.uid:
            # Los widgets se calculan como el dueño: una sesión cualquiera
            # (p. ej. un usuario portal) no basta para ver sus datos.
            user = request.env.user
            if page.created_by == user or user.has_group("base.group_system"):
                return None
            return request.not_found()
        # Redirige al inicio de sesión conservando la URL de retorno
        login_url = f"/web/login?redirect=/mcp-page/{page.slug}"
        if token:
            login_url += f"?token={token}"
        return request.redirect(login_url, code=302)

    def _render_widgets(self, page, filter_values: dict) -> list:
        """Calcula los datos de renderizado de cada widget de la especificación de la página."""
        spec = self._parse_spec_safe(page)
        widgets_spec = spec.get("widgets") or []

        # Calcula los valores por defecto de los filtros combinados con los de la query string
        resolved_filters = {}
        for f in spec.get("filters") or []:
            name = f.get("name", "")
            default = f.get("default", "")
            resolved_filters[name] = filter_values.get(name, default)

        # Se ejecuta como el usuario created_by — límite de gobierno
        env_as_owner = request.env["mcp.portal.page"].with_user(page.created_by.id).env

        result = []
        for ws in widgets_spec:
            data = compute_widget(env_as_owner, ws, resolved_filters)
            result.append(data)
        return result

    def _build_qcontext(self, page, spec: dict, widget_data: list, token: str, embed: bool) -> dict:
        """Arma el contexto de la plantilla, incluido el JSON de opciones de ECharts ya serializado."""
        charts_data = []
        for idx, w in enumerate(widget_data):
            if w.get("type") == "chart" and not w.get("error") and w.get("echarts_option"):
                charts_data.append({
                    "index": idx,
                    "option": w["echarts_option"],
                })
        return {
            "page": page,
            "spec": spec,
            "widgets": widget_data,
            "embed": embed,
            "token": token,
            "json_charts_data": charts_json(charts_data),
        }

    def _parse_spec_safe(self, page) -> dict:
        """Interpreta el JSON de page.spec; devuelve {} si hay un error."""
        try:
            return json.loads(page.spec or "{}")
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Utilidades de respuesta
# ---------------------------------------------------------------------------


def charts_json(charts_data) -> Markup:
    """JSON seguro dentro de <script>: escapa <, > y & como \\u003c... para que
    un nombre de registro con "</script>" no pueda cerrar la etiqueta."""
    return scriptsafe.dumps(charts_data, default=_json_default, ensure_ascii=False).__html__()


def _json_error(code: str, message: str, status: int) -> Response:
    body = json.dumps({"error": code, "message": message}, ensure_ascii=False)
    return Response(body, content_type="application/json; charset=utf-8", status=status)


def _json_default(obj):
    """Serializador de respaldo para los tipos del ORM que no son nativos de JSON."""
    import datetime
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    return str(obj)


def fields_now():
    """Devuelve la fecha y hora actual mediante fields de Odoo (evita importarlo a nivel de módulo)."""
    from odoo import fields
    return fields.Datetime.now()

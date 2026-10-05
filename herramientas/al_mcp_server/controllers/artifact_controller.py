# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
Controlador público de artefactos HTML.

Rutas:
  GET /mcp-artifact/<slug>        — página contenedora con iframe aislado (con marco completo)
  GET /mcp-artifact/<slug>/embed  — página contenedora con iframe aislado (sin marco)
  GET /mcp-artifact/<slug>/raw    — documento aislado en bruto (pensado solo para el srcdoc de un iframe)

El cuerpo del artefacto se arma en el servidor a partir de los campos html / css / js
y se sirve dentro de un iframe declarado con ``sandbox="allow-scripts"`` (sin
``allow-same-origin``). Se inyecta una etiqueta meta Content-Security-Policy estricta
que limita script-src / style-src a un pequeño conjunto de CDN de confianza y bloquea
``connect-src``.
"""

import html as html_lib
import logging

from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


_CSP_POLICY = (
    "default-src 'none'; "
    "script-src 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com "
    "https://cdnjs.cloudflare.com; "
    "style-src 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com "
    "https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com https://cdn.jsdelivr.net "
    "https://cdnjs.cloudflare.com data:; "
    "img-src data: blob: https:; "
    "media-src data: blob: https:; "
    "connect-src 'none'; "
    "frame-src 'none'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'"
)


def _build_sandbox_document(artifact) -> str:
    """Arma el documento HTML interno y aislado de un artefacto."""
    title = html_lib.escape(artifact.name or "Artefacto")
    css = artifact.css or ""
    js = artifact.js or ""
    body_html = artifact.html or ""
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\"/>\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>\n"
        f"<meta http-equiv=\"Content-Security-Policy\" content=\"{_CSP_POLICY}\"/>\n"
        f"<title>{title}</title>\n"
        "<style>\n"
        "html,body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"
        "'Segoe UI',Roboto,Oxygen,Ubuntu,Cantarell,sans-serif;}\n"
        f"{css}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body_html}\n"
        f"<script>{js}</script>\n"
        "</body>\n"
        "</html>\n"
    )


class McpArtifactController(http.Controller):

    @http.route(
        "/mcp-artifact/<string:slug>",
        type="http",
        auth="public",
        methods=["GET"],
        website=False,
        csrf=False,
    )
    def artifact_page(self, slug, **kwargs):
        return self._render_host(slug, kwargs, embed=False)

    @http.route(
        "/mcp-artifact/<string:slug>/embed",
        type="http",
        auth="public",
        methods=["GET"],
        website=False,
        csrf=False,
    )
    def artifact_embed(self, slug, **kwargs):
        return self._render_host(slug, kwargs, embed=True)

    @http.route(
        "/mcp-artifact/<string:slug>/raw",
        type="http",
        auth="public",
        methods=["GET"],
        website=False,
        csrf=False,
    )
    def artifact_raw(self, slug, **kwargs):
        """Sirve directamente el documento interno aislado.

        Pensado para casos avanzados de incrustación. Se prefiere el enfoque del
        iframe dentro de la página contenedora (ver ``artifact_page``) porque
        permite declarar el atributo sandbox en el iframe.
        """
        art = self._get_artifact_or_404(slug)
        if art is None:
            return request.not_found()

        auth_result = self._check_auth(art, kwargs.get("token", ""))
        if auth_result is not None:
            return auth_result

        self._bump_view_counter(art)
        body = _build_sandbox_document(art)
        # "sandbox allow-scripts" hace que el documento tenga un origen opaco
        # aunque se abra directamente: su JS no puede leer ni actuar sobre la
        # sesión de Odoo del visitante.
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Security-Policy", "sandbox allow-scripts; " + _CSP_POLICY),
            ("X-Frame-Options", "SAMEORIGIN"),
        ]
        return request.make_response(body, headers=headers)

    def _render_host(self, slug, kwargs, embed: bool):
        art = self._get_artifact_or_404(slug)
        if art is None:
            return request.not_found()

        auth_result = self._check_auth(art, kwargs.get("token", ""))
        if auth_result is not None:
            return auth_result

        self._bump_view_counter(art)
        srcdoc = _build_sandbox_document(art)
        qcontext = {
            "artifact": art,
            "srcdoc": Markup(html_lib.escape(srcdoc, quote=True)),
            "embed": embed,
            "token": kwargs.get("token", ""),
        }
        headers = {"X-Frame-Options": "ALLOWALL" if embed else "SAMEORIGIN"}
        return request.render("al_mcp_server.artifact_page", qcontext, headers=headers)

    def _get_artifact_or_404(self, slug: str):
        art = request.env["mcp.html.artifact"].sudo().search(
            [("slug", "=", slug), ("enabled", "=", True)],
            limit=1,
        )
        return art or None

    def _check_auth(self, art, token: str):
        if art.is_public:
            return None
        if token and art.access_token and consteq(token, art.access_token):
            return None
        if request.session and request.session.uid:
            user = request.env.user
            if art.created_by == user or user.has_group("base.group_system"):
                return None
            return request.not_found()
        login_url = f"/web/login?redirect=/mcp-artifact/{art.slug}"
        return request.redirect(login_url, code=302)

    def _bump_view_counter(self, art):
        from odoo import fields
        art.sudo().write({
            "view_count": art.view_count + 1,
            "last_viewed": fields.Datetime.now(),
        })

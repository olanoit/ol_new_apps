# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
MCP HTML Artifact model.

An artifact is a free-form interactive HTML snippet (HTML + optional CSS + JS)
produced by an AI client and served through a strictly sandboxed iframe. Unlike
mcp.portal.page, the content is opaque to the server: no spec, no widgets, just
raw markup that the client wants to render to a viewer.

Security model
--------------
* Content is wrapped in an iframe with ``sandbox="allow-scripts"`` (no
  same-origin), so script inside the artifact cannot read the parent page,
  cookies, or storage.
* A strict Content-Security-Policy is injected as a ``<meta http-equiv>`` tag
  inside the iframe srcdoc. ``connect-src`` defaults to ``'none'``, blocking
  any outbound network calls from the artifact.
* Only a small allowlist of CDNs is permitted for ``script-src`` and
  ``style-src`` (jsDelivr, unpkg, cdnjs, Google Fonts).
"""

import logging
import re
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_HTML_BYTES = 512 * 1024  # 512 KiB hard cap per artifact field


def _slugify(text: str) -> str:
    try:
        from odoo.tools import slugify as _odoo_slugify
        return _odoo_slugify(text, allow_slash=False)
    except (ImportError, TypeError):
        pass
    lowered = (text or "").lower().strip()
    return _SLUG_RE.sub("-", lowered).strip("-") or "artifact"


class McpHtmlArtifact(models.Model):
    _name = "mcp.html.artifact"
    _description = "Artefacto HTML MCP"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Título", required=True, tracking=True)
    slug = fields.Char(
        string="Slug",
        required=True,
        index=True,
        copy=False,
        help="Componente de la ruta URL: /mcp-artifact/<slug>. Se genera automáticamente a partir del título al crear.",
    )
    description = fields.Text(string="Descripción")
    enabled = fields.Boolean(string="Activado", default=True, tracking=True)

    is_public = fields.Boolean(
        string="Público",
        default=False,
        tracking=True,
        help="Si está activado, cualquiera puede ver el artefacto sin iniciar sesión. "
             "De lo contrario, se requiere una sesión de Odoo activa o un parámetro ?token= válido.",
    )
    access_token = fields.Char(
        string="Token de Incrustación",
        readonly=True,
        copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        help="Añada ?token=<valor> a la URL del artefacto para otorgar acceso de lectura sin iniciar sesión.",
    )
    created_by = fields.Many2one(
        "res.users",
        string="Creado Por",
        default=lambda self: self.env.uid,
        ondelete="restrict",
        index=True,
    )

    theme = fields.Selection(
        [("light", "Claro"), ("dark", "Oscuro"), ("auto", "Automático")],
        string="Tema",
        default="light",
    )

    html = fields.Text(
        string="Cuerpo HTML",
        required=True,
        default="<h1>Hello, world!</h1>",
        help="Marcado HTML colocado dentro del <body> del documento aislado. "
             "Puede contener etiquetas <style> y <script> en línea.",
    )
    css = fields.Text(
        string="CSS",
        help="CSS opcional insertado en una etiqueta <style> en <head>.",
    )
    js = fields.Text(
        string="JavaScript",
        help="JS opcional insertado en una etiqueta <script> al final de <body>. "
             "Se ejecuta dentro del aislamiento; sin acceso a la ventana principal.",
    )

    view_count = fields.Integer(string="Vistas", default=0, readonly=True)
    last_viewed = fields.Datetime(string="Última Visualización", readonly=True)

    artifact_url = fields.Char(string="URL del Artefacto", compute="_compute_urls")
    embed_url = fields.Char(string="URL de Incrustación", compute="_compute_urls")

    _slug_unique = models.Constraint(
        "UNIQUE(slug)",
        "Ya existe un artefacto HTML con este slug. Elija un slug diferente.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("slug") and vals.get("name"):
                vals["slug"] = self._unique_slug(vals["name"])
            if not vals.get("access_token"):
                vals["access_token"] = secrets.token_urlsafe(24)
            self._validate_size(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._validate_size(vals)
        return super().write(vals)

    @api.depends("slug", "access_token")
    def _compute_urls(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            rec.artifact_url = f"{base}/mcp-artifact/{rec.slug}" if rec.slug else ""
            rec.embed_url = (
                f"{base}/mcp-artifact/{rec.slug}?token={rec.access_token}"
                if rec.slug and rec.access_token
                else ""
            )

    def action_preview(self):
        self.ensure_one()
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        return {
            "type": "ir.actions.act_url",
            "url": f"{base}/mcp-artifact/{self.slug}",
            "target": "new",
        }

    def action_regenerate_token(self):
        for rec in self:
            rec.access_token = secrets.token_urlsafe(24)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Token Regenerado"),
                "message": _(
                    "El token de incrustación se ha regenerado. "
                    "Los enlaces de incrustación anteriores ya no son válidos."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _validate_size(self, vals: dict) -> None:
        for fname in ("html", "css", "js"):
            val = vals.get(fname)
            if val and len(val.encode("utf-8")) > _MAX_HTML_BYTES:
                raise UserError(
                    _("El campo %s supera el tamaño máximo de %d KiB.")
                    % (fname, _MAX_HTML_BYTES // 1024)
                )

    def _unique_slug(self, name: str) -> str:
        base = _slugify(name)
        candidate = base
        suffix = 1
        while self.search_count([("slug", "=", candidate)]):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
Modelo de artefacto HTML MCP.

Un artefacto es un fragmento HTML interactivo libre (HTML + CSS y JS opcionales)
generado por un cliente de IA y servido dentro de un iframe estrictamente
aislado. A diferencia de mcp.portal.page, el contenido es opaco para el
servidor: sin especificación ni widgets, solo el marcado en bruto que el
cliente quiere mostrar a quien lo vea.

Modelo de seguridad
-------------------
* El contenido se envuelve en un iframe con ``sandbox="allow-scripts"`` (sin
  same-origin), de modo que los scripts del artefacto no pueden leer la página
  principal, las cookies ni el almacenamiento.
* Se inyecta una Content-Security-Policy estricta como etiqueta
  ``<meta http-equiv>`` dentro del srcdoc del iframe. ``connect-src`` vale
  ``'none'`` por defecto y bloquea cualquier llamada de red saliente del artefacto.
* Solo se permite una pequeña lista de CDN en ``script-src`` y ``style-src``
  (jsDelivr, unpkg, cdnjs, Google Fonts).
"""

import logging
import re
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_HTML_BYTES = 512 * 1024  # Límite estricto de 512 KiB por campo del artefacto


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
        string="Token de incrustación",
        readonly=True,
        copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        help="Añada ?token=<valor> a la URL del artefacto para otorgar acceso de lectura sin iniciar sesión.",
    )
    created_by = fields.Many2one(
        "res.users",
        string="Creado por",
        default=lambda self: self.env.uid,
        ondelete="restrict",
        index=True,
        readonly=True,
    )

    theme = fields.Selection(
        [("light", "Claro"), ("dark", "Oscuro"), ("auto", "Automático")],
        string="Tema",
        default="light",
    )

    html = fields.Text(
        string="Cuerpo HTML",
        required=True,
        default="<h1>¡Hola, mundo!</h1>",
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
    last_viewed = fields.Datetime(string="Última visualización", readonly=True)

    artifact_url = fields.Char(string="URL del artefacto", compute="_compute_urls")
    embed_url = fields.Char(string="URL de incrustación", compute="_compute_urls")

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
        self._check_created_by_write(vals)
        self._validate_size(vals)
        return super().write(vals)

    def _check_created_by_write(self, vals):
        """El dueño determina con qué usuario se calculan los datos publicados:
        solo un administrador puede reasignarlo (las reglas solo se verifican
        antes del write, no sobre el valor nuevo)."""
        if "created_by" in vals and not self.env.su and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Solo un administrador puede cambiar el propietario."))


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
                "title": _("Token regenerado"),
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
        # sudo: el slug es único en toda la tabla, también entre registros de
        # otros usuarios que las reglas ocultan.
        records_sudo = self.sudo().with_context(active_test=False)
        while records_sudo.search_count([("slug", "=", candidate)]):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

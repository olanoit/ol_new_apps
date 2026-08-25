# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
"""
MCP Portal Page model.

Each portal page is defined by a JSON *spec* that drives server-side rendering.

Spec format
-----------
.. code-block:: json

    {
      "title": "Sales Dashboard",
      "subtitle": "Optional subtitle",
      "filters": [
        {"name": "date_from", "type": "date", "label": "From", "default": "2026-01-01"},
        {"name": "date_to",   "type": "date", "label": "To"}
      ],
      "widgets": [
        {
          "type": "kpi",
          "title": "Total Revenue",
          "model": "sale.order",
          "domain": [["state", "in", ["sale", "done"]]],
          "field": "amount_total",
          "aggregate": "sum",
          "format": "currency",
          "currency": "USD",
          "icon": "fa-money",
          "color": "#10b981"
        },
        {
          "type": "chart",
          "title": "Monthly Sales",
          "chart_type": "bar",
          "model": "sale.order",
          "domain": [["state", "=", "sale"]],
          "groupby": ["date_order:month"],
          "fields": ["amount_total:sum"]
        },
        {
          "type": "table",
          "title": "Top 10 Customers",
          "model": "sale.order",
          "domain": [],
          "groupby": ["partner_id"],
          "fields": ["amount_total:sum", "id:count"],
          "orderby": "amount_total desc",
          "limit": 10
        }
      ]
    }

Supported widget types: kpi, chart, table.
Supported chart_type:   bar, line, pie, area, donut.
Supported aggregate:    sum, count, avg, min, max.
Supported format:       currency, number, percent, integer.

Filter substitution
-------------------
Domain string values of the form ``{{filters.date_from}}`` are replaced with
the matching query-string parameter when the page is rendered. This allows
date-range pickers on the portal page to narrow widget data without rebuilding
the spec.
"""

import json
import logging
import re
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VALID_WIDGET_TYPES = frozenset({"kpi", "chart", "table"})
_VALID_CHART_TYPES = frozenset({"bar", "line", "pie", "area", "donut"})
_VALID_AGGREGATES = frozenset({"sum", "count", "avg", "min", "max"})
_VALID_FORMATS = frozenset({"currency", "number", "percent", "integer"})


def _slugify(text: str) -> str:
    """Convert *text* to a URL-safe lowercase slug."""
    try:
        from odoo.tools import slugify as _odoo_slugify
        return _odoo_slugify(text, allow_slash=False)
    except (ImportError, TypeError):
        pass
    lowered = text.lower().strip()
    return _SLUG_RE.sub("-", lowered).strip("-") or "page"


class McpPortalPage(models.Model):
    _name = "mcp.portal.page"
    _description = "Página de Portal MCP"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # ------------------------------------------------------------------
    # Core identity fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Título",
        required=True,
        tracking=True,
    )
    slug = fields.Char(
        string="Slug",
        required=True,
        index=True,
        copy=False,
        help="Componente de la ruta URL: /mcp-page/<slug>. Se genera automáticamente a partir del título al crear.",
    )
    description = fields.Text(string="Descripción")
    enabled = fields.Boolean(
        string="Activado",
        default=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Access control fields
    # ------------------------------------------------------------------

    is_public = fields.Boolean(
        string="Público",
        default=False,
        tracking=True,
        help="Si está activado, cualquiera puede ver esta página sin iniciar sesión. "
             "De lo contrario, se requiere una sesión de Odoo activa o un parámetro ?token= válido.",
    )
    access_token = fields.Char(
        string="Token de Incrustación",
        readonly=True,
        copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        help="Añada ?token=<valor> a la URL de la página para otorgar acceso de lectura sin iniciar sesión. "
             "Regenere para invalidar todos los enlaces de incrustación existentes.",
    )
    created_by = fields.Many2one(
        "res.users",
        string="Creado Por",
        default=lambda self: self.env.uid,
        ondelete="restrict",
        index=True,
    )

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------

    theme = fields.Selection(
        [("light", "Claro"), ("dark", "Oscuro"), ("auto", "Automático")],
        string="Tema",
        default="light",
    )

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    spec = fields.Text(
        string="Especificación de Página (JSON)",
        required=True,
        default='{\n  "title": "Mi Tablero",\n  "widgets": []\n}',
        help="Especificación JSON que define el diseño, los filtros y los widgets. "
             "Consulte el docstring del módulo para la referencia completa del formato.",
    )

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    view_count = fields.Integer(string="Vistas", default=0, readonly=True)
    last_viewed = fields.Datetime(string="Última Visualización", readonly=True)

    # ------------------------------------------------------------------
    # Computed / virtual fields
    # ------------------------------------------------------------------

    page_url = fields.Char(
        string="URL de la Página",
        compute="_compute_urls",
        help="URL pública de esta página de portal.",
    )
    embed_url = fields.Char(
        string="URL de Incrustación",
        compute="_compute_urls",
        help="URL autenticada por token para incrustar sin iniciar sesión.",
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    _slug_unique = models.Constraint(
        "UNIQUE(slug)",
        "Ya existe una página de portal con este slug. Elija un slug diferente.",
    )

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("slug") and vals.get("name"):
                vals["slug"] = self._unique_slug(vals["name"])
            if not vals.get("access_token"):
                vals["access_token"] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Computed field implementations
    # ------------------------------------------------------------------

    @api.depends("slug", "access_token")
    def _compute_urls(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            rec.page_url = f"{base}/mcp-page/{rec.slug}" if rec.slug else ""
            rec.embed_url = (
                f"{base}/mcp-page/{rec.slug}?token={rec.access_token}"
                if rec.slug and rec.access_token
                else ""
            )

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def action_preview(self):
        """Open the portal page in a new browser tab."""
        self.ensure_one()
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        url = f"{base}/mcp-page/{self.slug}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_regenerate_token(self):
        """Roll the embed access token, invalidating all existing embed links."""
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
    def parse_spec(self, spec_text: str) -> dict:
        """Validate and parse a page spec JSON string.

        Returns the parsed dict on success. Raises UserError with a descriptive
        message on any structural or JSON parse error.
        """
        if not spec_text or not spec_text.strip():
            raise UserError(_("La especificación de página no puede estar vacía."))
        try:
            spec = json.loads(spec_text)
        except json.JSONDecodeError as exc:
            raise UserError(_("JSON no válido en la especificación de página: %s") % str(exc)) from exc

        if not isinstance(spec, dict):
            raise UserError(_("La especificación de página debe ser un objeto JSON (dict), no una lista o escalar."))

        widgets = spec.get("widgets")
        if widgets is not None:
            if not isinstance(widgets, list):
                raise UserError(_("'widgets' debe ser un arreglo JSON."))
            for idx, widget in enumerate(widgets):
                self._validate_widget_spec(widget, idx)

        filters = spec.get("filters")
        if filters is not None:
            if not isinstance(filters, list):
                raise UserError(_("'filters' debe ser un arreglo JSON."))

        return spec

    @api.model
    def _validate_widget_spec(self, widget: dict, idx: int) -> None:
        """Raise UserError if a single widget spec is structurally invalid."""
        if not isinstance(widget, dict):
            raise UserError(_("El widget n.º %d debe ser un objeto JSON.") % idx)

        wtype = widget.get("type")
        if wtype not in _VALID_WIDGET_TYPES:
            raise UserError(
                _("Widget n.º %d: 'type' debe ser uno de %s, se obtuvo %r.")
                % (idx, sorted(_VALID_WIDGET_TYPES), wtype)
            )
        if not widget.get("model"):
            raise UserError(_("Widget n.º %d: 'model' es obligatorio.") % idx)

        if wtype == "kpi":
            if not widget.get("field"):
                raise UserError(_("Widget KPI n.º %d: 'field' es obligatorio.") % idx)
            agg = widget.get("aggregate", "sum")
            if agg not in _VALID_AGGREGATES:
                raise UserError(
                    _("Widget KPI n.º %d: 'aggregate' debe ser uno de %s.")
                    % (idx, sorted(_VALID_AGGREGATES))
                )
            fmt = widget.get("format", "number")
            if fmt not in _VALID_FORMATS:
                raise UserError(
                    _("Widget KPI n.º %d: 'format' debe ser uno de %s.")
                    % (idx, sorted(_VALID_FORMATS))
                )

        if wtype == "chart":
            ct = widget.get("chart_type", "bar")
            if ct not in _VALID_CHART_TYPES:
                raise UserError(
                    _("Widget de gráfico n.º %d: 'chart_type' debe ser uno de %s.")
                    % (idx, sorted(_VALID_CHART_TYPES))
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unique_slug(self, name: str) -> str:
        """Generate a slug from *name* that does not collide with existing slugs."""
        base = _slugify(name)
        candidate = base
        suffix = 1
        while self.search_count([("slug", "=", candidate)]):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

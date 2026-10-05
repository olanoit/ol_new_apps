from odoo import fields, models


class ResUsersMcp(models.Model):
    _inherit = "res.users"

    mcp_rate_limit = fields.Integer(
        string="Límite de Tasa MCP",
        default=0,
        help=(
            "Límite personalizado de solicitudes MCP por minuto para este usuario. "
            "0 = usar el valor predeterminado global de odoo.conf (mcp_rate_limit)."
        ),
    )

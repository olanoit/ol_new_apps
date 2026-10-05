from odoo import fields, models


class McpPatWizard(models.TransientModel):
    """Asistente de visualización única de un token de acceso personal recién generado.

    El token en claro solo se guarda en este registro transitorio y no se
    persiste en ningún otro sitio. Al cerrar el diálogo, el token en claro se pierde.
    """

    _name = "mcp.pat.wizard"
    _description = "PAT MCP: visualización única"

    token_id = fields.Many2one("mcp.token", string="Token", readonly=True, ondelete="cascade")
    raw_token = fields.Char(string="Token de acceso personal", readonly=True)
    user_id = fields.Many2one(related="token_id.user_id", string="Usuario", readonly=True)
    expires_at = fields.Datetime(related="token_id.expires_at", string="Caduca el", readonly=True)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    # Expone los campos nuevos de `pos.config` en Ajustes > Punto de Venta.
    # Sigue el mismo patrón que `pos_epson_printer_ip` en el core
    # (`point_of_sale/models/res_config_settings.py`): un campo
    # `pos_`-prefijado relacionado 1:1 con el campo real en `pos.config`.
    _inherit = "res.config.settings"

    pos_escpos_network_printer_enabled = fields.Boolean(
        related="pos_config_id.escpos_network_printer_enabled", readonly=False
    )
    pos_escpos_printer_ip = fields.Char(
        related="pos_config_id.escpos_printer_ip", readonly=False
    )
    pos_escpos_printer_port = fields.Char(
        related="pos_config_id.escpos_printer_port", readonly=False
    )
    pos_escpos_printer_mode = fields.Selection(
        related="pos_config_id.escpos_printer_mode", readonly=False
    )
    pos_escpos_agent_url = fields.Char(
        related="pos_config_id.escpos_agent_url", readonly=False
    )
    pos_escpos_agent_token = fields.Char(
        related="pos_config_id.escpos_agent_token", readonly=False
    )
    pos_escpos_require_agent_authorization = fields.Boolean(
        related="pos_config_id.escpos_require_agent_authorization", readonly=False
    )
    pos_escpos_auto_print = fields.Boolean(
        related="pos_config_id.escpos_auto_print", readonly=False
    )
    pos_escpos_retry_queue_enabled = fields.Boolean(
        related="pos_config_id.escpos_retry_queue_enabled", readonly=False
    )
    # Camino B (Fase 2) — de solo lectura acá a propósito, ver
    # pos.config.escpos_agent_channel: se genera solo, nunca se tipea.
    pos_escpos_agent_channel = fields.Char(
        related="pos_config_id.escpos_agent_channel", readonly=True
    )

    def action_regenerate_escpos_agent_channel(self):
        """Wrapper fino: los botones de esta pantalla solo pueden llamar
        métodos de res.config.settings (transient), no de pos.config
        directo — delega en el método real
        (pos.config.action_regenerate_escpos_agent_channel)."""
        self.ensure_one()
        self.pos_config_id.action_regenerate_escpos_agent_channel()
        return {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }

    def action_test_escpos_printer(self):
        """Wrapper fino, mismo criterio que
        action_regenerate_escpos_agent_channel de arriba — delega en
        pos.config.action_test_escpos_printer (botón "Probar impresora")."""
        self.ensure_one()
        return self.pos_config_id.action_test_escpos_printer()

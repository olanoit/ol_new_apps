from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_pos_network_printer.controllers.main import retry_print_receipt


class PosPrinter(models.Model):
    # `pos.printer` (core, `point_of_sale/models/pos_printer.py`) ya soporta
    # `iot` y `epson_epos`. Ninguno de los dos sirve para una impresora de
    # cocina/barra ESC/POS genérica sin IoT Box: `iot` requiere una IoT Box,
    # y `epson_epos` requiere que la impresora sea realmente una Epson.
    # `escpos_network` cubre ese tercer caso, reutilizando el mismo
    # controlador HTTP que la impresora de recibo principal (ver
    # controllers/main.py).
    _inherit = "pos.printer"

    printer_type = fields.Selection(
        selection_add=[("escpos_network", "Usar una impresora ESC/POS genérica de red")],
        ondelete={"escpos_network": "set default"},
    )
    escpos_printer_ip = fields.Char(
        string="IP de la impresora ESC/POS",
        help="Dirección IP o nombre de host de la impresora térmica ESC/POS genérica.",
    )
    escpos_printer_port = fields.Char(
        string="Puerto de la impresora ESC/POS",
        default="9100",
    )

    @api.constrains("printer_type", "escpos_printer_ip")
    def _constrains_escpos_printer_ip(self):
        # Misma forma que `_constrains_epson_printer_ip` del core: solo
        # exigir la IP cuando el tipo elegido realmente la necesita.
        for record in self:
            if record.printer_type == "escpos_network" and not record.escpos_printer_ip:
                raise ValidationError("La dirección IP de la impresora ESC/POS no puede estar vacía.")

    def _escpos_retry_print_receipt_job(self, ip, port, img_b64):
        """Cuerpo del job de `queue_job` encolado por
        `controllers/main.py::_enqueue_escpos_retry` cuando esta impresora
        de preparación (cocina/barra) falló al imprimir — mismo criterio
        que `pos.config._escpos_retry_print_receipt_job` (ver su
        docstring), delega en la misma función compartida."""
        self.ensure_one()
        retry_print_receipt(self.env, ip, port, img_b64)

    @api.model
    def _load_pos_data_fields(self, config):
        # Sin esto, el frontend nunca recibiría `escpos_printer_ip` /
        # `escpos_printer_port`, y `createPrinter()` (pos_store.js) no podría
        # instanciar `EscposNetworkPrinter` con los datos de conexión
        # correctos.
        fields_list = super()._load_pos_data_fields(config)
        return fields_list + ["escpos_printer_ip", "escpos_printer_port"]

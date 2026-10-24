# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Planchas enteras (paquete 1.11, M111-12). Se leen aquí porque el
    # requerimiento de obra y la fabricación del planificador las usan.
    construction_whole_sheet = fields.Boolean(
        string='Pedir tableros en planchas enteras',
        help='Los productos indivisibles se entregan, compran y despachan en planchas '
             'enteras; la fracción queda como necesidad.')
    construction_whole_sheet_tolerance = fields.Float(
        string='Tolerancia de redondeo', digits=(16, 2), default=0.0,
        help='Fracción de plancha que se redondea hacia abajo. 0 = toda fracción sube.')
    # Alcance (M111-19 D): dónde actúa el redondeo. Con la casilla principal
    # apagada no actúa en ninguna.
    construction_whole_sheet_production = fields.Boolean(
        string='Aplicar en el despacho a producción', default=True)
    construction_whole_sheet_request = fields.Boolean(
        string='Aplicar en el requerimiento de obra', default=True)
    construction_whole_sheet_purchase = fields.Boolean(
        string='Aplicar en compras', default=True,
        help='Compra masiva, tablero de abastecimiento y aviso de la orden de compra.')

    # Tarjetas del resumen de Inventario (paquete 1.11, M111-19 A).
    al_stock_overview_style = fields.Selection(
        [('standard', 'Estándar de Odoo'), ('compact', 'Compacta')],
        string='Estilo de las tarjetas', default='compact', required=True)
    al_stock_overview_graph = fields.Boolean(string='Mostrar el gráfico en las tarjetas')
    al_stock_overview_width = fields.Selection(
        [('narrow', 'Angosta (300 px)'), ('medium', 'Media (340 px)'), ('wide', 'Ancha (400 px)')],
        string='Ancho de las tarjetas', default='medium', required=True)

    @api.constrains('construction_whole_sheet_tolerance')
    def _check_construction_whole_sheet_tolerance(self):
        for company in self:
            if not 0.0 <= company.construction_whole_sheet_tolerance < 1.0:
                raise ValidationError(self.env._(
                    'La tolerancia de redondeo va de 0 a 0.99 plancha.'))

    def _construction_whole_sheet_in(self, scope):
        """¿El redondeo a plancha entera actúa en ``scope`` (production,
        request o purchase)?"""
        self.ensure_one()
        return bool(self.construction_whole_sheet
                    and self['construction_whole_sheet_%s' % scope])


# -*- coding: utf-8 -*-
from odoo import fields, models

BANCARIZATION_MODES = [
    ('none', 'No controlar'),
    ('warn', 'Avisar'),
    ('block', 'Bloquear'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Aprobaciones: importes en la moneda de la compañía (0 = sin aprobación).
    l10n_pe_treasury_plan_approval_amount = fields.Monetary(
        string='Aprobar programaciones desde', currency_field='currency_id',
        help='Las programaciones de pago con un total igual o mayor necesitan la aprobación de '
             'un aprobador de tesorería. 0: todas necesitan aprobación.')
    l10n_pe_treasury_plan_double_amount = fields.Monetary(
        string='Segunda aprobación desde', currency_field='currency_id',
        help='Desde este total, la programación necesita además la aprobación de un '
             'administrador de tesorería distinto del primero. 0: nunca.')
    l10n_pe_treasury_transfer_approval_amount = fields.Monetary(
        string='Aprobar transferencias desde', currency_field='currency_id',
        help='Las transferencias y operaciones de cambio con un importe (en soles) igual o '
             'mayor necesitan la aprobación de un aprobador de tesorería. 0: ninguna.')
    l10n_pe_treasury_notice_days = fields.Integer(
        string='Aviso de vencimientos (días)', default=15,
        help='Días antes del vencimiento de una línea de crédito, una cuota o una carta '
             'fianza en que su responsable recibe una actividad.')
    # Bancarización: art. 4 del TUO de la Ley 28194, montos del DL 1529.
    l10n_pe_bancarization_mode = fields.Selection(
        BANCARIZATION_MODES, string='Bancarización', default='warn', required=True,
        help='Qué hacer al confirmar un pago en efectivo desde el monto a partir del cual la '
             'ley obliga a usar medios de pago (sin ellos se pierde el gasto y el crédito fiscal).')
    l10n_pe_bancarization_amount_pen = fields.Float(
        string='Monto en soles', default=2000.0,
        help='Monto desde el que es obligatorio usar medios de pago: S/ 2 000 (DL 1529).')
    l10n_pe_bancarization_amount_usd = fields.Float(
        string='Monto en dólares', default=500.0,
        help='Monto desde el que es obligatorio usar medios de pago: US$ 500 (DL 1529).')

    def _get_company_root_delegated_field_names(self):
        # La bancarización es una obligación del contribuyente (RUC): las
        # sucursales siguen a su raíz.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_bancarization_mode', 'l10n_pe_bancarization_amount_pen',
            'l10n_pe_bancarization_amount_usd']

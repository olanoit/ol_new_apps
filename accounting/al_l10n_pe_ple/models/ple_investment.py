# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nPePleInvestment(models.Model):
    """Captura del PLE 3.8 — Libro de Inventarios y Balances, detalle del
    saldo de la cuenta 30 Inversiones mobiliarias al cierre del ejercicio.
    Odoo no modela títulos/valores, por lo que el detalle se captura aquí."""
    _name = 'l10n_pe.ple.investment'
    _description = 'PLE 3.8 - Inversión mobiliaria (cta. 30)'
    _order = 'date, id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(
        string='Fecha del saldo (EEFF)', required=True, index=True,
        help='Fecha de los estados financieros a la que corresponde el '
             'saldo (normalmente el 31/12). El wizard exporta los registros '
             'cuya fecha coincide con la fecha de balance elegida.')
    partner_id = fields.Many2one(
        'res.partner', string='Emisor',
        help='Emisor del título. Si el emisor no tiene documento peruano, '
             'déjelo vacío y use «Nombre del emisor».')
    issuer_name = fields.Char(
        string='Nombre del emisor',
        help='Solo si no se indica un contacto emisor.')
    title_code = fields.Char(
        string='Código del título (T15)', size=2, required=True,
        help='Tipo de título según la tabla 15 del Anexo 3 de SUNAT.')
    nominal_value = fields.Monetary(
        string='Valor nominal unitario', required=True)
    quantity = fields.Integer(string='Cantidad de títulos', required=True)
    book_cost = fields.Monetary(
        string='Costo total en libros', required=True)
    provision = fields.Monetary(
        string='Provisión total',
        help='En positivo: el TXT la emite en negativo (campo 11).')

    @api.constrains('provision')
    def _check_provision(self):
        for record in self:
            if record.provision < 0:
                raise ValidationError(self.env._(
                    'La provisión se captura en positivo; el signo lo '
                    'aplica el exportador PLE.'))

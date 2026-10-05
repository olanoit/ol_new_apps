# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nPePleWithholding(models.Model):
    """Registro de captura del PLE 4.1 — Libro de Retenciones incisos e) y
    f) del Art. 34 de la Ley del Impuesto a la Renta (rentas de 4ª/5ª
    categoría sin planilla). Odoo no tiene nómina peruana, por lo que las
    retenciones se capturan aquí (o se importan por XLSX estándar)."""
    _name = 'l10n_pe.ple.withholding'
    _description = 'PLE 4.1 - Retención Art. 34 LIR'
    _order = 'date, id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id')
    date = fields.Date(
        string='Fecha de pago / retención', required=True, index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Prestador del servicio', required=True,
        help='Persona que percibe la renta (inciso e) o f) del Art. 34 LIR).')
    partner_vat = fields.Char(
        related='partner_id.vat', string='Nº documento')
    gross_amount = fields.Monetary(
        string='Monto bruto', required=True,
        help='Retribución pagada o puesta a disposición (campo 8 del 4.1).')
    withheld_amount = fields.Monetary(
        string='Retención efectuada',
        help='Importe retenido, en positivo: el TXT lo emite en negativo '
             'según el Anexo 2 (campo 9).')

    @api.constrains('withheld_amount', 'gross_amount')
    def _check_amounts(self):
        for record in self:
            if record.gross_amount < 0 or record.withheld_amount < 0:
                raise ValidationError(self.env._(
                    'Los montos del registro 4.1 se capturan en positivo; '
                    'el signo lo aplica el exportador PLE.'))

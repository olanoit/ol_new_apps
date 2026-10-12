# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# UIT vigente en 2026 (D.S. 301-2025-EF). Si está instalada la planilla
# peruana, se toma la del año de su catálogo (``l10n_pe.hr.uit``).
DEFAULT_UIT = 5500.0


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_lce_igv_tax_id = fields.Many2one(
        'account.tax', string='IGV retenido en la liquidación de compra',
        check_company=True, domain=[('type_tax_use', '=', 'purchase'), ('amount', '<', 0)],
        help='Impuesto negativo con la tasa del IGV: el comprador retiene el IGV y lo paga '
             'con el formulario 1662. Se añade solo en las líneas gravadas.')
    l10n_pe_lce_ir_tax_id = fields.Many2one(
        'account.tax', string='Retención del impuesto a la renta (1,5 %)',
        check_company=True, domain=[('type_tax_use', '=', 'purchase'), ('amount', '<', 0)],
        help='R.S. 234-2005/SUNAT, art. 5: 1,5 % del importe de la operación, sin tributos. '
             'Se declara en el PDT 617 (tributo 3039).')
    l10n_pe_lce_ir_gold_tax_id = fields.Many2one(
        'account.tax', string='Retención del impuesto a la renta (oro, 4 %)',
        check_company=True, domain=[('type_tax_use', '=', 'purchase'), ('amount', '<', 0)],
        help='R.S. 028-2013/SUNAT: 4 % en la compra de minerales, amalgama, polvo y '
             'desperdicios de oro.')
    l10n_pe_lce_ir_min_amount = fields.Float(
        string='Importe mínimo para retener la renta (S/)', digits=(12, 2), default=700.0,
        help='R.S. 234-2005/SUNAT, art. 6: no se retiene cuando el importe de la operación '
             'es igual o inferior a S/ 700.')
    l10n_pe_lce_uit_amount = fields.Float(
        string='UIT (S/)', digits=(12, 2), default=DEFAULT_UIT,
        help='Valor de la UIT para el aviso de 75 UIT de ventas del vendedor. Con la '
             'planilla peruana instalada se usa la UIT del año de su catálogo.')
    l10n_pe_lce_send_on_post = fields.Boolean(
        string='Enviar al confirmar',
        help='Envía la liquidación de compra al confirmarla. SUNAT la recibe solo el día de '
             'emisión o el día siguiente (R.S. 097-2012/SUNAT, art. 12.1.b).')

    def _get_company_root_delegated_field_names(self):
        # El agente de retención es el RUC: las sucursales usan los mismos
        # impuestos y límites que su raíz.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_lce_igv_tax_id',
            'l10n_pe_lce_ir_tax_id',
            'l10n_pe_lce_ir_gold_tax_id',
            'l10n_pe_lce_ir_min_amount',
            'l10n_pe_lce_uit_amount',
        ]

    @api.constrains('l10n_pe_lce_igv_tax_id', 'l10n_pe_lce_ir_tax_id', 'l10n_pe_lce_ir_gold_tax_id')
    def _check_l10n_pe_lce_taxes(self):
        for company in self:
            taxes = (company.l10n_pe_lce_igv_tax_id | company.l10n_pe_lce_ir_tax_id
                     | company.l10n_pe_lce_ir_gold_tax_id)
            if any(tax.amount_type != 'percent' or tax.amount >= 0 for tax in taxes):
                raise ValidationError(self.env._(
                    'Los impuestos de la liquidación de compra deben ser porcentajes negativos '
                    '(retenciones).'))

    def _l10n_pe_lce_uit(self, year):
        """UIT del año: la del catálogo de la planilla si está instalada; si
        no, la de los ajustes."""
        self.ensure_one()
        if 'l10n_pe.hr.uit' in self.env:
            # La UIT es un valor público, pero el catálogo de planillas solo lo
            # leen los usuarios de nómina: el contable no tiene acceso.
            uit_sudo = self.env['l10n_pe.hr.uit'].sudo().search([('year', '=', year)], limit=1)
            if uit_sudo.amount:
                return uit_sudo.amount
        return self.l10n_pe_lce_uit_amount or DEFAULT_UIT

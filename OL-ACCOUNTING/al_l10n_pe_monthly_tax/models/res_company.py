# -*- coding: utf-8 -*-
from odoo import fields, models

# UIT vigente en 2026 (D.S. 301-2025-EF). Con la planilla peruana instalada se
# toma la del año de su parámetro de reglas nativo (``l10n_pe_uit``).
DEFAULT_UIT = 5500.0


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_tax_regime_ids = fields.One2many(
        'l10n_pe.tax.regime', 'company_id', string='Régimen tributario')
    l10n_pe_income_coefficient = fields.Float(
        string='Coeficiente (marzo a diciembre)', digits=(16, 4),
        help='Impuesto calculado del ejercicio anterior ÷ ingresos netos del mismo ejercicio, '
             'redondeado a 4 decimales (art. 85 de la Ley del Impuesto a la Renta). Sale de la '
             'declaración jurada anual.')
    l10n_pe_income_coefficient_jan_feb = fields.Float(
        string='Coeficiente (enero y febrero)', digits=(16, 4),
        help='Para enero y febrero se usa el coeficiente del ejercicio precedente al anterior '
             '(art. 85, inciso a).')
    l10n_pe_income_suspended = fields.Boolean(
        string='Pagos a cuenta suspendidos',
        help='Suspensión aprobada por SUNAT (art. 85, incisos i y ii): el pago a cuenta del '
             'Régimen General o MYPE (más de 300 UIT) es cero mientras esté marcada.')
    l10n_pe_tax_uit_amount = fields.Float(
        string='UIT para el límite MYPE (S/)', digits=(12, 2), default=DEFAULT_UIT,
        help='Con la planilla peruana instalada se usa la UIT del año de su catálogo.')
    l10n_pe_monthly_tax_journal_id = fields.Many2one(
        'account.journal', string='Diario del pago a cuenta', check_company=True,
        domain=[('type', '=', 'general')])
    l10n_pe_income_advance_account_id = fields.Many2one(
        'account.account', string='Cuenta de pagos a cuenta (activo)', check_company=True,
        help='Cuenta del impuesto a la renta pagado a cuenta (p. ej. 40171).')
    l10n_pe_income_payable_account_id = fields.Many2one(
        'account.account', string='Cuenta por pagar del pago a cuenta', check_company=True,
        help='Contrapartida del pago a cuenta hasta su pago (p. ej. 40179 u otra de tributos '
             'por pagar).')

    def _get_company_root_delegated_field_names(self):
        # El régimen, el coeficiente y las cuentas son del RUC: las sucursales
        # usan los de su compañía raíz.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_income_coefficient', 'l10n_pe_income_coefficient_jan_feb',
            'l10n_pe_income_suspended', 'l10n_pe_tax_uit_amount',
            'l10n_pe_monthly_tax_journal_id', 'l10n_pe_income_advance_account_id',
            'l10n_pe_income_payable_account_id',
        ]

    def _l10n_pe_tax_uit(self, year):
        self.ensure_one()
        if 'hr.rule.parameter' in self.env:
            # Odoo 20: con la nómina instalada, la UIT es el parámetro nativo
            # «l10n_pe_uit» (valor público; el contable no tiene acceso a la
            # nómina, de ahí el sudo).
            value_sudo = self.env['hr.rule.parameter.value'].sudo().search([
                ('code', '=', 'l10n_pe_uit'),
                ('date_from', '>=', '%s-01-01' % year), ('date_from', '<=', '%s-12-31' % year),
            ], limit=1)
            if value_sudo:
                return float(value_sudo.parameter_value)
        return self.l10n_pe_tax_uit_amount or DEFAULT_UIT

    def _l10n_pe_tax_regime_at(self, date):
        """Régimen vigente a la fecha (el último que empezó antes o ese día)."""
        self.ensure_one()
        root = self.root_id
        return self.env['l10n_pe.tax.regime'].search([
            ('company_id', '=', root.id), ('date_from', '<=', date)],
            order='date_from desc, id desc', limit=1)

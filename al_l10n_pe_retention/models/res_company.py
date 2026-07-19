# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_retention_agent = fields.Boolean(
        string='Agente de retención del IGV',
        help='La compañía fue designada agente de retención por SUNAT: '
             'retiene el 3% en los pagos a proveedores por operaciones '
             'gravadas mayores al monto mínimo.')
    l10n_pe_retention_rate = fields.Float(
        string='Tasa de retención (%)', digits=(5, 2), default=3.0,
        help='3% del importe total de la operación (R.S. 033-2014/SUNAT).')
    l10n_pe_retention_min_amount = fields.Float(
        string='Monto mínimo de retención (S/)', digits=(12, 2),
        default=700.0,
        help='La retención aplica a operaciones cuyo importe total supera '
             'este monto (S/ 700).')
    l10n_pe_retention_tax_id = fields.Many2one(
        'account.tax', string='Impuesto de retención IGV',
        check_company=True,
        domain=[('is_withholding_tax_on_payment', '=', True),
                ('type_tax_use', '=', 'purchase')],
        help='Impuesto negativo de retención en el pago (marco nativo): '
             'su cuenta debe ser «IGV – Retenciones por pagar» (4011x) y '
             'su secuencia numera los comprobantes de retención.')
    l10n_pe_retention_received_account_id = fields.Many2one(
        'account.account', string='Cuenta de retenciones sufridas',
        check_company=True,
        help='Cuenta 40114 «IGV – Régimen de retenciones» donde se '
             'acumula el crédito por retenciones que nos efectúan los '
             'clientes agentes.')
    l10n_pe_retention_received_journal_id = fields.Many2one(
        'account.journal', string='Diario de retenciones sufridas',
        check_company=True, domain=[('type', '=', 'general')])
    l10n_pe_retention_outstanding_account_id = fields.Many2one(
        'account.account', string='Cuenta transitoria (retenciones)',
        check_company=True,
        help='Cuenta transitoria de pagos que el wizard propone al '
             'registrar pagos con retención cuando el método de pago no '
             'tiene cuenta propia (el campo es obligatorio en el pago).')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_retention_agent = fields.Boolean(
        related='company_id.l10n_pe_retention_agent', readonly=False)
    l10n_pe_retention_rate = fields.Float(
        related='company_id.l10n_pe_retention_rate', readonly=False)
    l10n_pe_retention_min_amount = fields.Float(
        related='company_id.l10n_pe_retention_min_amount', readonly=False)
    l10n_pe_retention_tax_id = fields.Many2one(
        related='company_id.l10n_pe_retention_tax_id', readonly=False)
    l10n_pe_retention_received_account_id = fields.Many2one(
        related='company_id.l10n_pe_retention_received_account_id',
        readonly=False)
    l10n_pe_retention_received_journal_id = fields.Many2one(
        related='company_id.l10n_pe_retention_received_journal_id',
        readonly=False)
    l10n_pe_retention_outstanding_account_id = fields.Many2one(
        related='company_id.l10n_pe_retention_outstanding_account_id',
        readonly=False)

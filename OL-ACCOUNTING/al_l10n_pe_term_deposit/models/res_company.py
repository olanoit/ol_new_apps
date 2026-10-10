# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_term_deposit_notice_days = fields.Integer(
        string='Aviso de vencimiento (días)', default=7,
        help='Días antes del vencimiento de un depósito o garantía en que se crea la '
             'actividad de aviso para su responsable.')
    # ITF (Ley 28194): grava los débitos y créditos en cuentas del sistema
    # financiero. Hay exoneraciones (Apéndice de la ley, con declaración
    # jurada ante el banco), por eso es opcional y editable por depósito.
    l10n_pe_term_deposit_itf = fields.Boolean(
        string='Registrar el ITF de los depósitos',
        help='Propone el ITF del capital en la apertura, la cancelación y la liberación de '
             'los depósitos; los intereses y la renovación están exonerados. Cada depósito '
             'puede marcarse como no afecto.')
    l10n_pe_term_deposit_itf_rate = fields.Float(
        string='Tasa del ITF (%)', digits=(6, 4), default=0.005,
        help='Tasa del Impuesto a las Transacciones Financieras (art. 10 del TUO de la Ley 28194): 0,005 %.')
    l10n_pe_term_deposit_itf_account_id = fields.Many2one(
        'account.account', string='Cuenta del ITF', check_company=True,
        help='Gasto por el ITF (PCGE 6412). Vacía: se usa la 6412 del plan contable.')

    def _l10n_pe_term_deposit_itf_account(self):
        """Cuenta del ITF de la compañía o, si no hay, la 6412 del PCGE."""
        self.ensure_one()
        return self.l10n_pe_term_deposit_itf_account_id or self.env.ref(
            'account.%s_chart6412' % self.id, raise_if_not_found=False) or self.env['account.account']

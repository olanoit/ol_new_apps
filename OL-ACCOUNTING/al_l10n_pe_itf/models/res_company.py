from decimal import ROUND_FLOOR, Decimal

from odoo import fields, models

#: Alícuota del ITF (art. 10 del TUO de la Ley 28194), en porcentaje.
ITF_RATE = 0.005


def itf_amount(amount, rate=ITF_RATE):
    """ITF de una operación según el art. 13 de la Ley 28194: se suprime el
    tercer decimal y el segundo se ajusta a 0 (si es menor que 5) o a 5. El
    resultado es el múltiplo de 0,05 inmediatamente inferior: S/ 1 000 → 0,05;
    S/ 1 999 → 0,05; S/ 2 000 → 0,10; S/ 999 → 0,00."""
    tax = abs(Decimal(str(amount))) * Decimal(str(rate)) / 100
    return float((tax * 20).to_integral_value(rounding=ROUND_FLOOR) / 20)


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_itf_rate = fields.Float(
        string='Tasa del ITF (%)', digits=(6, 4), default=ITF_RATE,
        help='Impuesto a las Transacciones Financieras (art. 10 del TUO de la Ley 28194): 0,005 %.')
    l10n_pe_itf_account_id = fields.Many2one(
        'account.account', string='Cuenta del ITF', check_company=True,
        domain="[('account_type', 'in', ('expense', 'expense_other'))]",
        help='Gasto por el ITF (PCGE 6412). Vacía: se usa la 6412 del plan contable.')

    def _get_company_root_delegated_field_names(self):
        # El ITF lo retiene el banco al RUC: las sucursales usan la configuración de su raíz.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_itf_rate', 'l10n_pe_itf_account_id']

    def _l10n_pe_itf_account(self):
        """Cuenta del ITF de la compañía o, si no hay, la 6412 del PCGE."""
        self.ensure_one()
        company = self.root_id
        return company.l10n_pe_itf_account_id or self.env.ref(
            'account.%s_chart6412' % company.id, raise_if_not_found=False) or self.env['account.account']

    def _l10n_pe_itf_reconcile_model(self):
        """Regla de conciliación «ITF» (la crea si no existe): en el extracto, la
        línea del ITF va a la cuenta del ITF. La usan sobre todo los diarios sin
        cuenta de pagos pendientes, cuyos pagos no tienen asiento propio."""
        self.ensure_one()
        company = self.root_id
        Model = self.env['account.reconcile.model'].with_company(company)
        model = Model.search([('company_id', '=', company.id), ('name', '=', 'ITF')], limit=1)
        account = company._l10n_pe_itf_account()
        if not model and account:
            model = Model.create({
                'name': 'ITF',
                'company_id': company.id,
                'trigger': 'manual',
                'match_label': 'match_regex',
                'match_label_param': r'(?i)\bITF\b',
                'line_ids': [fields.Command.create({
                    'account_id': account.id, 'amount_type': 'percentage', 'amount_string': '100',
                    'label': 'ITF',
                })],
            })
        return model


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_itf_rate = fields.Float(related='company_id.l10n_pe_itf_rate', readonly=False)
    l10n_pe_itf_account_id = fields.Many2one(related='company_id.l10n_pe_itf_account_id', readonly=False)

    def action_l10n_pe_itf_reconcile_model(self):
        model = self.company_id._l10n_pe_itf_reconcile_model()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.reconcile.model',
            'res_id': model.id,
            'view_mode': 'form',
            'target': 'current',
        }

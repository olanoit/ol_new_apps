from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_collection_promise_tolerance = fields.Integer(
        string='Tolerancia de compromisos (días)', default=2,
        help='Días después de la fecha del compromiso antes de evaluarlo como incumplido.')
    l10n_pe_collection_promise_reminder_days = fields.Integer(
        string='Recordar el compromiso (días antes)', default=1,
        help='Días antes de la fecha del compromiso en que se envía el recordatorio al cliente; '
             '0 para no enviar.')
    l10n_pe_collection_promise_min_percent = fields.Float(
        string='Cumplido desde (%)', default=99.0, digits=(5, 1),
        help='Porcentaje del importe prometido que debe cobrarse para darlo por cumplido; por '
             'debajo, y con algún cobro, es parcial.')
    l10n_pe_collection_digest = fields.Boolean(
        string='Resumen diario a los gestores', default=True,
        help='Correo diario a cada gestor con sus compromisos del día, gestiones pendientes, '
             'documentos por vencer y nuevos vencidos.')
    l10n_pe_collection_history_months = fields.Integer(
        string='Historial de pago (meses)', default=12,
        help='Meses de facturas pagadas que se usan para calcular el atraso promedio de cada cliente.')

    def _get_company_root_delegated_field_names(self):
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_collection_promise_tolerance', 'l10n_pe_collection_promise_reminder_days',
            'l10n_pe_collection_promise_min_percent', 'l10n_pe_collection_digest',
            'l10n_pe_collection_history_months']

    def _l10n_pe_collection_excluded_accounts(self):
        """Cuentas por cobrar que no son cobranza: anticipos (se aplican a la
        factura) y detracciones por cobrar (van al Banco de la Nación)."""
        self.ensure_one()
        company = self.root_id
        accounts = self.env['account.account']
        if hasattr(company, '_l10n_pe_advance_accounts'):
            accounts |= company._l10n_pe_advance_accounts()
        if 'l10n_pe_detraction_receivable_account_id' in company._fields:
            accounts |= company.l10n_pe_detraction_receivable_account_id
        return accounts


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_collection_promise_tolerance = fields.Integer(
        related='company_id.l10n_pe_collection_promise_tolerance', readonly=False)
    l10n_pe_collection_promise_reminder_days = fields.Integer(
        related='company_id.l10n_pe_collection_promise_reminder_days', readonly=False)
    l10n_pe_collection_promise_min_percent = fields.Float(
        related='company_id.l10n_pe_collection_promise_min_percent', readonly=False)
    l10n_pe_collection_digest = fields.Boolean(related='company_id.l10n_pe_collection_digest', readonly=False)
    l10n_pe_collection_history_months = fields.Integer(
        related='company_id.l10n_pe_collection_history_months', readonly=False)

    def action_l10n_pe_collection_load_followup_levels(self):
        return self.env['account_followup.followup.line']._l10n_pe_load_levels(self.company_id)

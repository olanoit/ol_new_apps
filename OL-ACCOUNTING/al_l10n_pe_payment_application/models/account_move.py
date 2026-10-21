from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_advance_count = fields.Integer(
        string='Anticipos disponibles', compute='_compute_l10n_pe_advance_count',
        help='Anticipos del socio con saldo que se pueden aplicar a este comprobante.')

    def _l10n_pe_advance_lines(self):
        """Anticipos abiertos del socio en el sentido que cancela este comprobante:
        saldo acreedor en la 122 para una factura de cliente y deudor en la 422
        para una de proveedor."""
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'in_invoice') or not self.partner_id:
            return self.env['account.move.line']
        company = self.company_id.root_id
        if self.move_type == 'out_invoice':
            accounts = company.l10n_pe_advance_customer_account_id | company.l10n_pe_advance_customer_fc_account_id
            sign = '<'
        else:
            accounts = company.l10n_pe_advance_supplier_account_id | company.l10n_pe_advance_supplier_fc_account_id
            sign = '>'
        if not accounts:
            return self.env['account.move.line']
        return self.env['account.move.line'].search([
            ('company_id', 'child_of', company.id),
            ('partner_id', 'child_of', self.commercial_partner_id.id),
            ('account_id', 'in', accounts.ids),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('amount_residual', sign, 0.0),
        ])

    def _compute_l10n_pe_advance_count(self):
        for move in self:
            move.l10n_pe_advance_count = len(move._l10n_pe_advance_lines()) \
                if move.state == 'posted' and move.payment_state in ('not_paid', 'partial') else 0

    def action_l10n_pe_apply_advances(self):
        self.ensure_one()
        advances = self._l10n_pe_advance_lines()
        receivable = self.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
            and not line.reconciled)
        if not advances or not receivable:
            raise UserError(_('No hay anticipos del socio por aplicar a %s.', self.display_name))
        return self.env['l10n_pe.payment.application']._l10n_pe_open_new(
            self.partner_id, 'advance', receivable | advances)

    def _post(self, soft=True):
        posted = super()._post(soft)
        # Aviso, no bloqueo: el anticipo puede ser de otra compra del proveedor.
        for move in posted.filtered(lambda m: m.move_type in ('out_invoice', 'in_invoice')):
            advances = move._l10n_pe_advance_lines()
            if advances:
                move.message_post(body=_(
                    'El socio tiene %(count)s anticipo(s) sin aplicar por %(amount)s: use '
                    '«Aplicar anticipos».', count=len(advances),
                    amount=move.company_currency_id.format(abs(sum(advances.mapped('amount_residual'))))))
        return posted


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_application_line_id = fields.Many2one(
        'l10n_pe.payment.application.line', string='Línea de aplicación', copy=False,
        index='btree_not_null', readonly=True)

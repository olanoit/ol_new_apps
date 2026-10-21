from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_is_advance = fields.Boolean(
        string='Anticipo', copy=False,
        help='Pago a cuenta sin comprobante: va a la cuenta de anticipos de la compañía '
             '(122 clientes, 422 proveedores) y se aplica después a la factura.')

    @api.depends('l10n_pe_is_advance', 'currency_id')
    def _compute_destination_account_id(self):
        super()._compute_destination_account_id()
        for payment in self.filtered('l10n_pe_is_advance'):
            account = payment.company_id._l10n_pe_advance_account(
                payment.partner_type, payment.currency_id)
            if account:
                payment.destination_account_id = account

    def action_post(self):
        for payment in self.filtered('l10n_pe_is_advance'):
            if payment.destination_account_id not in payment.company_id._l10n_pe_advance_accounts():
                raise UserError(_(
                    'Configure la cuenta de anticipos de %(type)s en Ajustes ▸ Perú antes de '
                    'confirmar el anticipo %(payment)s.',
                    type=_('clientes') if payment.partner_type == 'customer' else _('proveedores'),
                    payment=payment.display_name))
        return super().action_post()

    def action_l10n_pe_apply_advance(self):
        """Abre la aplicación con este anticipo y las facturas abiertas del socio."""
        self.ensure_one()
        lines = self.move_id.line_ids.filtered(
            lambda line: line.account_id == self.destination_account_id and not line.reconciled)
        if not lines:
            raise UserError(_('El anticipo no tiene saldo por aplicar. Si el diario no tiene cuenta '
                              'de pendientes, concilie antes el extracto bancario.'))
        return self.env['l10n_pe.payment.application']._l10n_pe_open_new(
            self.partner_id, 'advance', lines, with_open_documents=True)

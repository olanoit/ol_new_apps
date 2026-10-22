from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _create_payment(self, **extra_create_values):
        """El pago del saldo (enlace de los avisos de cobranza) no trae facturas:
        se le asignan las más antiguas del cliente para que el pago nativo las
        concilie en vez de quedar como anticipo."""
        prefix = self.env['res.partner']._L10N_PE_COLLECTION_TX_PREFIX
        if not self.invoice_ids and (self.reference or '').startswith(prefix) and self.amount > 0:
            partner = self.partner_id.commercial_partner_id
            invoices = partner._l10n_pe_collection_fifo_invoices(self.amount, self.company_id)
            if invoices:
                self.invoice_ids = invoices
        return super()._create_payment(**extra_create_values)

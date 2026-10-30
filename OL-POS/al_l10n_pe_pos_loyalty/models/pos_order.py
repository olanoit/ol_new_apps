# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError
from odoo.fields import Command

from .product_product import PAYMENT_PROGRAM_TYPES


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    def _l10n_pe_pos_voucher_lines(self):
        """Líneas que no son venta de bienes (Informe SUNAT 097-2010): la venta
        de una tarjeta de regalo o recarga del monedero (importe positivo) y su
        canje (línea de recompensa negativa de un programa de pago)."""
        def is_voucher(line):
            if line.order_id.company_id.country_code != 'PE':
                return False
            if line.is_reward_line:
                # sudo: solo se lee el tipo del programa de la recompensa que
                # la venta ya aplicó; quien cierra la caja o factura puede no
                # tener acceso a los programas de fidelización.
                reward_sudo = line.reward_id.sudo()
                return reward_sudo.program_id.program_type in PAYMENT_PROGRAM_TYPES
            return line.product_id.l10n_pe_pos_is_voucher
        return self.filtered(is_voucher)

    def _prepare_tax_base_line_values(self):
        # El comprobante no las lleva: la venta del vale no es operación
        # gravada y su canje es una forma de pago, no un descuento.
        if self.env.context.get('invoicing'):
            lines = self - self._l10n_pe_pos_voucher_lines()
            return super(PosOrderLine, lines)._prepare_tax_base_line_values()
        return super()._prepare_tax_base_line_values()

    def _prepare_base_line_for_taxes_computation(self):
        """Venta y canje van sin impuestos a la cuenta de pasivo con el cliente,
        nunca a ingresos: en el cierre de caja la venta lo aumenta y el canje lo
        baja. El producto de descuento que Odoo crea para el canje trae el
        impuesto de venta por defecto y el TPV lo usa con el precio incluido:
        sin esto, el canje rebajaba el IGV de la venta."""
        base_line = super()._prepare_base_line_for_taxes_computation()
        if not self._l10n_pe_pos_voucher_lines():
            return base_line
        base_line.update({
            'tax_ids': self.env['account.tax'],
            'price_unit': self.price_subtotal_incl / self.qty if self.qty else 0.0,
            'discount': 0.0,
            'special_mode': False,
            'manual_total_excluded_currency': None,
            'manual_total_excluded': None,
            'manual_tax_amounts': None,
        })
        account = self.order_id.company_id.l10n_pe_pos_voucher_account_id
        if account:
            base_line['account_id'] = account
        return base_line


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _l10n_pe_pos_is_voucher_only(self):
        lines = self.lines.filtered(lambda line: not self.currency_id.is_zero(line.price_subtotal_incl))
        vouchers = lines._l10n_pe_pos_voucher_lines()
        return bool(vouchers) and not (lines - vouchers)

    def _process_saved_order(self, draft):
        # Una venta solo de tarjetas o recargas no lleva comprobante, aunque la
        # caja la haya marcado para facturar.
        if self.to_invoice and self._l10n_pe_pos_is_voucher_only():
            self.write({'to_invoice': False, 'l10n_pe_doc_type': 'recibo'})
        return super()._process_saved_order(draft)

    def _prepare_invoice_vals(self):
        if all(order._l10n_pe_pos_is_voucher_only() for order in self):
            raise UserError(_(
                'La venta de tarjetas de regalo y recargas del monedero no lleva comprobante '
                '(Informe SUNAT 097-2010): el comprobante se emite cuando el cliente las canjea.'))
        return super()._prepare_invoice_vals()

    def _reconcile_invoice_payments(self, invoice, payment_moves):
        super()._reconcile_invoice_payments(invoice, payment_moves)
        voucher_move = self._l10n_pe_pos_create_voucher_move(invoice)
        if not voucher_move:
            return
        receivable_account = self.env['res.partner']._find_accounting_partner(invoice.partner_id)\
            .with_company(self.company_id).property_account_receivable_id
        if not receivable_account.reconcile:
            return
        lines = (voucher_move.line_ids | invoice.line_ids
                 | payment_moves.pos_payment_ids._get_receivable_lines_for_invoice_reconciliation(receivable_account))
        lines.filtered(lambda line: line.account_id == receivable_account and not line.reconciled)\
            .sudo().with_company(invoice.company_id).reconcile()

    def _l10n_pe_pos_create_voucher_move(self, invoice):
        """Asiento del vale contra la cuenta por cobrar del comprobante. Canje:
        el vale paga el comprobante (débito al pasivo, crédito a la cuenta por
        cobrar). Tarjeta vendida en la misma venta: el cliente pagó en caja más
        que el comprobante y el exceso es pasivo con él."""
        voucher_lines = self.lines._l10n_pe_pos_voucher_lines()
        if not voucher_lines:
            return self.env['account.move']
        by_account = defaultdict(float)
        for line in voucher_lines:
            account = line._prepare_base_line_for_taxes_computation()['account_id']
            by_account[account] += line.price_subtotal_incl
        currency = self.currency_id
        voucher_total = sum(by_account.values())
        if currency.is_zero(voucher_total):
            return self.env['account.move']
        company = self.company_id
        rate = invoice.invoice_currency_rate or 1.0
        partner = self.env['res.partner']._find_accounting_partner(invoice.partner_id)
        receivable_account = partner.with_company(company).property_account_receivable_id

        def line_vals(account, amount_currency, name):
            return Command.create({
                'name': name,
                'account_id': account.id,
                'partner_id': partner.id,
                'currency_id': currency.id,
                'amount_currency': amount_currency,
                'balance': company.currency_id.round(amount_currency / rate),
            })

        line_commands = [
            line_vals(account, -currency.round(amount), _('Tarjeta de regalo y monedero'))
            for account, amount in by_account.items() if not currency.is_zero(amount)
        ]
        line_commands.append(line_vals(receivable_account, currency.round(voucher_total), invoice.name))
        # Cuadre de la conversión a la moneda de la compañía en el último apunte.
        balance = sum(command[2]['balance'] for command in line_commands)
        line_commands[-1][2]['balance'] -= balance
        # sudo: el cajero sincroniza la venta pero no crea asientos contables;
        # el asiento se arma solo con los importes de las líneas de la orden.
        move_sudo = self.env['account.move'].sudo().with_company(company).create({
            'journal_id': self.config_id.journal_id.id,
            'date': invoice.date,
            'ref': _('Tarjeta de regalo y monedero: %s', invoice.name),
            'move_type': 'entry',
            'line_ids': line_commands,
        })
        move_sudo._post()
        return move_sudo


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _get_sale_key(self, base_line):
        # El apunte de la venta del vale no lleva los impuestos del producto:
        # su base no debe aparecer en el registro de ventas.
        key = super()._get_sale_key(base_line)
        record = base_line['record']
        if isinstance(record, models.BaseModel) and record._name == 'pos.order.line' \
                and record._l10n_pe_pos_voucher_lines():
            key['tax_ids'] = ()
        return key

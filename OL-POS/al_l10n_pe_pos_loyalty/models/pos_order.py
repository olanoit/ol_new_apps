# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, fields, models
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

    def _l10n_pe_pos_voucher_account(self):
        """Cuenta de pasivo con el cliente del vale (o el ingreso del producto
        si la compañía aún no la tiene)."""
        self.ensure_one()
        return self.order_id.company_id.l10n_pe_pos_voucher_account_id \
            or self.product_id._get_product_accounts()['income']

    def _prepare_base_lines_for_taxes_computation(self):
        """Venta y canje van sin impuestos a la cuenta de pasivo con el cliente,
        nunca a ingresos: en el cierre de caja la venta lo aumenta y el canje lo
        baja. El producto de descuento que Odoo crea para el canje trae el
        impuesto de venta por defecto y el TPV lo usa con el precio incluido:
        sin esto, el canje rebajaba el IGV de la venta."""
        base_lines = super()._prepare_base_lines_for_taxes_computation()
        vouchers = self._l10n_pe_pos_voucher_lines()
        if not vouchers:
            return base_lines
        for base_line in base_lines:
            line = base_line['record']
            if line not in vouchers:
                continue
            base_line.update({
                'tax_ids': self.env['account.tax'],
                'price_unit': line.price_subtotal_incl / line.qty if line.qty else 0.0,
                'discount': 0.0,
                'special_mode': False,
                'manual_total_excluded_currency': None,
                'manual_total_excluded': None,
                'manual_tax_amounts': None,
            })
            account = line.order_id.company_id.l10n_pe_pos_voucher_account_id
            if account:
                base_line['account_id'] = account
        return base_lines


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

    def _l10n_pe_pos_voucher_total(self):
        return sum(self.lines._l10n_pe_pos_voucher_lines().mapped('price_subtotal_incl'))

    def _prepare_account_move_line_data_from_base_line(self, base_lines):
        """El comprobante no lleva la venta ni el canje del vale: la venta no
        es operación gravada y el canje es una forma de pago, no un
        descuento (Informe SUNAT 097-2010)."""
        data = super()._prepare_account_move_line_data_from_base_line(base_lines)
        vouchers = self.lines._l10n_pe_pos_voucher_lines()
        if not vouchers:
            return data
        return [item for item in data
                if item['metadata'].get('line') not in vouchers]

    def _prepare_invoice_extra_line_commands(self, payments=[]):
        """Odoo 20: el comprobante del TPV lleva los cobros. Lo que se canjeó
        con el vale (o, al revés, lo que se cobró de más por una tarjeta
        vendida en la misma venta) queda como un vencimiento en la cuenta por
        cobrar, que salda el asiento del vale (_l10n_pe_pos_create_voucher_move)."""
        commands = super()._prepare_invoice_extra_line_commands(payments)
        amount = -self.currency_id.round(self._l10n_pe_pos_voucher_total())
        if self.currency_id.is_zero(amount):
            return commands
        partner = self.env['res.partner']._find_accounting_partner(self.partner_id)
        receivable = partner.with_company(self.company_id).property_account_receivable_id
        commands.append(Command.create({
            'display_type': 'payment_term',
            'name': _('Tarjeta de regalo y monedero'),
            'account_id': receivable.id,
            'partner_id': partner.id,
            'date_maturity': fields.Date.context_today(self),
            'amount_currency': amount,
        }))
        return commands

    def _generate_pos_order_invoice(self):
        invoice = super()._generate_pos_order_invoice()
        for order in self:
            voucher_move = order._l10n_pe_pos_create_voucher_move(invoice)
            if not voucher_move:
                continue
            receivable_account = self.env['res.partner']._find_accounting_partner(invoice.partner_id)\
                .with_company(order.company_id).property_account_receivable_id
            if not receivable_account.reconcile:
                continue
            (voucher_move.line_ids | invoice.line_ids).filtered(
                lambda line: line.account_id == receivable_account and not line.reconciled
            ).sudo().with_company(invoice.company_id).with_context(skip_invoice_sync=True).reconcile()
        return invoice

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
            by_account[line._l10n_pe_pos_voucher_account()] += line.price_subtotal_incl
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
            # Odoo 20: el diario de la caja es el de los comprobantes (pide
            # tipo de documento); el asiento del vale va en operaciones varias.
            'journal_id': self.env['account.journal'].sudo().search([
                *self.env['account.journal']._check_company_domain(company),
                ('type', '=', 'general')], limit=1).id,
            'date': invoice.date,
            'ref': _('Tarjeta de regalo y monedero: %s', invoice.name),
            'move_type': 'entry',
            'line_ids': line_commands,
        })
        move_sudo._post()
        return move_sudo

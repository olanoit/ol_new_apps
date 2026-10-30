# -*- coding: utf-8 -*-
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPosPeVouchers(TestPoSCommon):
    """Ibuprofeno a S/ 50,00 + IGV 9,00 = 59,00. Tarjeta de regalo de S/ 50,00
    (Informe SUNAT 097-2010: su venta no lleva comprobante y su canje la paga)."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        # TestPoSCommon pisa el país de la compañía con uno ficticio.
        cls.company_data['company'].write({
            'country_id': cls.env.ref('base.pe').id, 'vat': '20512528458'})
        cls.config = cls.basic_config
        cls.igv = cls.env['account.tax'].create({
            'name': 'IGV 18 % (tarjetas)', 'amount': 18, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.env.company.id})
        cls.ibuprofen = cls.create_product('Ibuprofeno 400 mg', cls.categ_basic, 50.0,
                                           tax_ids=cls.igv.ids)
        # sudo: productos y programa compartidos que el usuario de prueba no
        # puede modificar.
        cls.gift_product = cls.env.ref('loyalty.gift_card_product_50').sudo()
        cls.gift_product.write({'available_in_pos': True, 'taxes_id': [Command.clear()]})
        cls.reward = cls.env.ref('loyalty.gift_card_program_reward').sudo()
        cls.reward.program_id.company_id = cls.env.company
        cls.customer = cls.env['res.partner'].create({
            'name': 'Rosa Huamán Ccori', 'additional_identifiers': {'PE_DNI': '44556677'}})
        cls.env['res.company']._l10n_pe_pos_setup_vouchers()
        cls.voucher_account = cls.env.company.l10n_pe_pos_voucher_account_id

    def _redemption(self, amount, taxes=None):
        """Línea de canje como la arma el TPV: con los impuestos del producto
        de descuento y el precio con impuestos incluidos."""
        values = {'product': self.reward.discount_line_product_id, 'quantity': 1,
                  'price_unit': -amount, 'price_subtotal': -amount, 'price_subtotal_incl': -amount,
                  'is_reward_line': True, 'reward_id': self.reward.id}
        if taxes:
            values.update({'tax_ids': [Command.set(taxes.ids)],
                           'price_subtotal': -round(amount / 1.18, 2)})
        return values

    def _sync(self, lines, payments, invoiced=False):
        data = self.create_ui_order_data(lines, customer=self.customer, is_invoiced=invoiced,
                                         payments=payments)
        result = self.env['pos.order'].with_context(generate_pdf=False).sync_from_ui([data])
        return self.env['pos.order'].browse(result['pos.order'][0]['id'])

    def _voucher_balance(self, moves):
        return sum(moves.line_ids.filtered(
            lambda line: line.account_id == self.voucher_account).mapped('balance'))

    def test_setup_account_and_no_unaffected_tax(self):
        self.assertTrue(self.voucher_account.code.startswith('496'))
        unaffected = self.env['account.tax'].search([
            ('company_id', '=', self.env.company.id), ('type_tax_use', '=', 'sale'),
            ('l10n_pe_edi_tax_code', '=', '9998')], limit=1)
        self.assertTrue(unaffected)
        self.gift_product.taxes_id = [Command.link(unaffected.id)]
        self.env['res.company']._l10n_pe_pos_setup_vouchers()
        self.assertNotIn(unaffected, self.gift_product.taxes_id)
        self.assertFalse(self.reward.discount_line_product_id.taxes_id.filtered(
            lambda tax: tax.company_id == self.env.company))
        new_reward = self.env['loyalty.reward'].sudo().create({
            'program_id': self.reward.program_id.id, 'reward_type': 'discount',
            'discount_mode': 'per_point', 'discount': 1, 'discount_applicability': 'order',
            'required_points': 1, 'description': 'Monedero'})
        self.assertFalse(new_reward.discount_line_product_id.taxes_id.filtered(
            lambda tax: tax.company_id == self.env.company))
        self.assertTrue(self.gift_product.l10n_pe_pos_is_voucher)
        self.assertFalse(self.ibuprofen.l10n_pe_pos_is_voucher)

    def test_redemption_is_a_payment_of_the_full_invoice(self):
        self.open_new_session()
        order = self._sync([(self.ibuprofen, 1), self._redemption(20.0, self.igv)],
                           [(self.cash_pm1, 39.0)], invoiced=True)
        invoice = order.account_move
        # El comprobante va por el importe completo, con todo su IGV.
        self.assertAlmostEqual(invoice.amount_total, 59.0)
        self.assertAlmostEqual(invoice.amount_tax, 9.0)
        self.assertEqual(invoice.invoice_line_ids.product_id, self.ibuprofen)
        # Caja 39,00 + vale 20,00: queda pagado.
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
        voucher_move = self.env['account.move'].search([
            ('ref', '=', f'Tarjeta de regalo y monedero: {invoice.name}')])
        self.assertEqual(voucher_move.state, 'posted')
        self.assertAlmostEqual(self._voucher_balance(voucher_move), 20.0)
        self.pos_session.action_pos_session_validate()
        self.assertEqual(self.pos_session.state, 'closed')

    def test_gift_card_sold_with_products_is_outside_the_invoice(self):
        self.open_new_session()
        order = self._sync([(self.ibuprofen, 1), (self.gift_product, 1)],
                           [(self.cash_pm1, 109.0)], invoiced=True)
        invoice = order.account_move
        self.assertAlmostEqual(invoice.amount_total, 59.0)
        self.assertEqual(invoice.invoice_line_ids.product_id, self.ibuprofen)
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
        voucher_move = self.env['account.move'].search([
            ('ref', '=', f'Tarjeta de regalo y monedero: {invoice.name}')])
        # Los 50,00 de la tarjeta son deuda con el cliente, no ingreso.
        self.assertAlmostEqual(self._voucher_balance(voucher_move), -50.0)
        self.pos_session.action_pos_session_validate()
        self.assertEqual(self.pos_session.state, 'closed')

    def test_gift_card_only_sale_has_no_invoice(self):
        self.open_new_session()
        order = self._sync([(self.gift_product, 1)], [(self.cash_pm1, 50.0)], invoiced=True)
        self.assertFalse(order.account_move)
        self.assertFalse(order.to_invoice)
        self.assertEqual(order.l10n_pe_doc_type, 'recibo')
        with self.assertRaises(UserError):
            order.action_pos_order_invoice()

    def test_session_without_invoice_books_the_liability(self):
        self.open_new_session()
        self._sync([(self.gift_product, 1)], [(self.cash_pm1, 50.0)])
        # Aunque el producto de descuento lleve el IGV, el canje no lo rebaja.
        self._sync([(self.ibuprofen, 1), self._redemption(20.0, self.igv)], [(self.cash_pm1, 39.0)])
        self.pos_session.action_pos_session_validate()
        move = self.pos_session.move_id
        tax_lines = move.line_ids.filtered(lambda line: line.tax_line_id == self.igv)
        self.assertAlmostEqual(-sum(tax_lines.mapped('balance')), 9.0)
        self.assertFalse(move.line_ids.filtered(
            lambda line: line.account_id == self.voucher_account and line.tax_ids))
        # Venta de la tarjeta (−50,00) y canje (+20,00): quedan 30,00 por canjear.
        self.assertAlmostEqual(self._voucher_balance(move), -30.0)
        income = move.line_ids.filtered(lambda line: self.igv in line.tax_ids)
        self.assertAlmostEqual(-sum(income.mapped('balance')), 50.0)

    def test_cash_rounding_with_redemption(self):
        rounding = self.env['account.cash.rounding'].create({
            'name': 'Redondeo 0,10', 'rounding': 0.10, 'strategy': 'add_invoice_line',
            'profit_account_id': self.company['default_cash_difference_income_account_id'].id,
            'loss_account_id': self.company['default_cash_difference_expense_account_id'].id,
            'rounding_method': 'HALF-UP'})
        self.config.write({'cash_rounding': True, 'rounding_method': rounding.id,
                           'only_round_cash_method': False})
        self.ibuprofen.lst_price = 10.01  # 11,81 con IGV
        self.open_new_session()
        order = self._sync([(self.ibuprofen, 1), self._redemption(5.0)],
                           [(self.cash_pm1, 6.80)], invoiced=True)
        invoice = order.account_move
        # Se redondea el comprobante (11,81 → 11,80), no lo cobrado en caja.
        self.assertAlmostEqual(invoice.amount_total, 11.80)
        rounding_line = invoice.line_ids.filtered(lambda line: line.display_type == 'rounding')
        self.assertAlmostEqual(rounding_line.balance, 0.01)
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))



@tagged('post_install', '-at_install')
class TestPosPeVouchersTour(TestPointOfSaleHttpCommon):

    def start_tour(self, url_path, tour_name, step_delay=None, **kwargs):
        # Los pasos de los tours del núcleo usan los textos en inglés; la base
        # de migración está en es_PE y los usuarios de prueba lo heredan.
        if kwargs.get('login'):
            self.env['res.users'].search([('login', '=', kwargs['login'])]).lang = 'en_US'
        return super().start_tour(url_path, tour_name, step_delay=step_delay, **kwargs)

    def _setup_pe_pos(self):
        config = self.main_pos_config
        config.company_id.country_id = self.env.ref('base.pe')
        journal = config.journal_id
        config.write({
            'l10n_pe_boleta_journal_id': journal.copy({'name': 'Boletas TPV', 'code': 'BTPV'}).id,
            'l10n_pe_factura_journal_id': journal.copy({'name': 'Facturas TPV', 'code': 'FTPV'}).id,
        })
        self.assertTrue(config.l10n_pe_cpe_enabled)
        LoyaltyProgram = self.env['loyalty.program']
        LoyaltyProgram.search([]).write({'pos_ok': False})
        self.env.ref('loyalty.gift_card_product_50').product_tmpl_id.write({'active': True})
        program = LoyaltyProgram.browse(LoyaltyProgram.create_from_template('gift_card')['res_id'])
        program.pos_report_print_id = self.env.ref('loyalty.report_gift_card')
        config.with_user(self.pos_user).open_ui()
        return config, program

    def test_gift_card_only_sale_is_a_ticket(self):
        config, program = self._setup_pe_pos()
        self.start_pos_tour('al_l10n_pe_pos_gift_card_ticket')
        order = self.env['pos.order'].search([('session_id', '=', config.current_session_id.id)], limit=1)
        self.assertEqual(order.l10n_pe_doc_type, 'recibo')
        self.assertFalse(order.to_invoice)
        self.assertFalse(order.account_move)
        self.assertEqual(len(program.coupon_ids), 1)

    def test_mixed_sale_receipt_shows_the_card_outside(self):
        self.env['res.partner'].create({
            'name': 'Rosa Huamán Ccori', 'additional_identifiers': {'PE_DNI': '44556677'}})
        config, program = self._setup_pe_pos()
        self.start_pos_tour('al_l10n_pe_pos_gift_card_mixed')
        order = self.env['pos.order'].search([('session_id', '=', config.current_session_id.id)], limit=1)
        self.assertTrue(order.account_move)
        self.assertNotIn(program.trigger_product_ids, order.account_move.invoice_line_ids.product_id)

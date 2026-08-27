# -*- coding: utf-8 -*-
"""Medio de pago SUNAT (catálogo 1) en pagos y en el asistente de registro.

Lo que se valida:

* la integridad del catálogo cargado (códigos del anexo, marca de
  detracción, nombre mostrado «código - descripción»);
* que el asistente ``account.payment.register`` traslade el medio de pago
  y el número de operación al pago creado, tanto por el camino normal
  (``_create_payment_vals_from_wizard``) como por el de lote
  (``_create_payment_vals_from_batch``), que es el que se usa al agrupar
  varias facturas del mismo partner en un solo pago.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPePaymentMethod(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Catalog = cls.env['pe.catalog.payment']
        cls.deposito = cls.env.ref('al_account_payments.pe_catalog_payment_001')
        cls.transferencia = cls.env.ref('al_account_payments.pe_catalog_payment_003')
        # El diario de venta de la base lleva EDI peruano: sin RUC ni
        # impuestos la factura no se puede publicar.
        cls.partner = cls.env['res.partner'].create({
            'name': 'CLIENTE PRUEBA SAC',
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.sale_journal = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.company.id)], limit=1)
        cls.bank_journal = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', cls.company.id)], limit=1)
        # v19: account.account ya no tiene company_id (es company_ids m2m).
        cls.product_account = cls.env['account.account'].search(
            [('account_type', '=', 'income')], limit=1)
        cls.tax_sale = cls.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.company.id),
            ('l10n_pe_edi_tax_code', '=', '1000'),
        ], limit=1) or cls.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'), ('company_id', '=', cls.company.id),
        ], limit=1)

    # ------------------------------------------------------------------
    # Catálogo
    # ------------------------------------------------------------------
    def test_catalog_data_loaded(self):
        """Los 20 medios del catálogo 1 de SUNAT están cargados."""
        self.assertGreaterEqual(
            self.Catalog.search_count([]), 20,
            'el data del catálogo 1 de SUNAT debe estar cargado')
        for code in ('001', '003', '007', '009', '011'):
            self.assertTrue(
                self.Catalog.search([('code', '=', code)], limit=1),
                'falta el medio de pago %s del catálogo SUNAT' % code)

    def test_catalog_display_name(self):
        """El nombre mostrado es «código - descripción»."""
        self.assertEqual(self.deposito.display_name, '001 - DEPÓSITO EN CUENTA')

    def test_catalog_display_name_without_code(self):
        """Sin código se muestra solo la descripción (no revienta)."""
        rec = self.Catalog.new({'name': 'SIN CÓDIGO'})
        rec._compute_display_name()
        self.assertEqual(rec.display_name, 'SIN CÓDIGO')

    def test_catalog_search_by_code(self):
        """``_rec_names_search`` permite buscar por código además de por nombre."""
        found = self.Catalog.name_search('003')
        self.assertIn(self.transferencia.id, [f[0] for f in found])

    def test_detraction_flag(self):
        """La transferencia de fondos es medio válido de detracción."""
        self.assertTrue(self.transferencia.is_detraction)
        self.assertTrue(
            self.Catalog.search_count([('is_detraction', '=', True)]),
            'al menos un medio debe estar marcado para detracción')

    # ------------------------------------------------------------------
    # Campos en el pago
    # ------------------------------------------------------------------
    def _invoice(self, amount=1180.0):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'invoice_date': '2026-03-15',
            'invoice_line_ids': [Command.create({
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': amount,
                'tax_ids': [Command.set(self.tax_sale.ids)],
                'account_id': self.product_account.id,
            })],
        })
        move.action_post()
        return move

    def test_payment_fields_exist(self):
        """El pago acepta medio de pago y número de operación."""
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'journal_id': self.bank_journal.id,
            'pe_payment_method_id': self.deposito.id,
            'bank_operation_number': '000123456',
        })
        self.assertEqual(payment.pe_payment_method_id, self.deposito)
        self.assertEqual(payment.bank_operation_number, '000123456')

    # ------------------------------------------------------------------
    # Asistente de registro de pagos
    # ------------------------------------------------------------------
    def test_register_wizard_propagates_to_payment(self):
        """El asistente traslada medio y nro. de operación al pago creado."""
        invoice = self._invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({
            'journal_id': self.bank_journal.id,
            'pe_payment_method_id': self.transferencia.id,
            'bank_operation_number': 'OP-778899',
        })
        payments = wizard._create_payments()
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments.pe_payment_method_id, self.transferencia)
        self.assertEqual(payments.bank_operation_number, 'OP-778899')

    def test_register_wizard_without_method_leaves_empty(self):
        """Sin medio de pago el campo queda vacío, no falla ni inventa uno."""
        invoice = self._invoice(500.0)
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'journal_id': self.bank_journal.id})
        payments = wizard._create_payments()
        self.assertFalse(payments.pe_payment_method_id)
        self.assertFalse(payments.bank_operation_number)

    def test_register_wizard_grouped_batch_propagates(self):
        """Al agrupar dos facturas en un solo pago también se traslada.

        Este es el camino ``_create_payment_vals_from_batch``: si solo se
        hubiese parcheado el método del asistente, el pago agrupado se
        crearía sin medio de pago.
        """
        invoices = self._invoice(300.0) | self._invoice(700.0)
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoices.ids,
        ).create({
            'journal_id': self.bank_journal.id,
            'pe_payment_method_id': self.deposito.id,
            'bank_operation_number': 'LOTE-001',
        })
        wizard.group_payment = True
        payments = wizard._create_payments()
        self.assertEqual(len(payments), 1, 'las dos facturas se agrupan en un pago')
        self.assertEqual(payments.pe_payment_method_id, self.deposito)
        self.assertEqual(payments.bank_operation_number, 'LOTE-001')

# -*- coding: utf-8 -*-
"""Vendedor por orden en el TPV.

Cubre las tres piezas de servidor del módulo (la parte OWL del selector se
prueba a mano):

* la lista blanca de vendedores por punto de venta y su efecto en
  ``_employee_domain``, que es lo que decide quién aparece en el selector;
* la carga de ``hr.employee`` en el TPV cuando se usan vendedores
  autorizados aunque ``module_pos_hr`` esté desactivado;
* el vendedor en la orden y su llegada a la vista de análisis de ventas
  (``report.pos.order``), donde se agrupa por vendedor.
"""
from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosSeller(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        # sudo: el usuario del entorno de TPV no tiene permisos de RR. HH.
        Employee = cls.env['hr.employee'].sudo()
        cls.vendedor_a = Employee.create({'name': 'ANA VENDEDORA'})
        cls.vendedor_b = Employee.create({'name': 'BRUNO VENDEDOR'})
        cls.ajeno = Employee.create({'name': 'CARLOS ALMACÉN'})

    # ------------------------------------------------------------------
    # Configuración del punto de venta
    # ------------------------------------------------------------------
    def test_seller_list_is_stored(self):
        """La lista blanca de vendedores se guarda en la configuración."""
        self.config.write({
            'authorized_seller': True,
            'seller_ids': [Command.set((self.vendedor_a | self.vendedor_b).ids)],
        })
        self.assertTrue(self.config.authorized_seller)
        self.assertEqual(self.config.seller_ids, self.vendedor_a | self.vendedor_b)

    def test_employee_domain_includes_authorized_sellers(self):
        """Los vendedores de la lista entran en el dominio aunque no sean pos_hr."""
        self.config.write({
            'authorized_seller': True,
            'seller_ids': [Command.set(self.vendedor_a.ids)],
        })
        domain = self.config._employee_domain(self.env.user.id)
        employees = self.env['hr.employee'].sudo().search(domain)
        self.assertIn(self.vendedor_a, employees,
                      'el vendedor autorizado debe aparecer en el selector')

    def test_employee_domain_untouched_without_flag(self):
        """Sin la marca, el dominio es el de serie (no se amplía nada)."""
        self.config.write({
            'authorized_seller': False,
            'seller_ids': [Command.set(self.vendedor_a.ids)],
        })
        base = super(type(self.config), self.config)._employee_domain(self.env.user.id)
        self.assertEqual(self.config._employee_domain(self.env.user.id), base)

    def test_employee_domain_untouched_with_empty_list(self):
        """Marca activa pero lista vacía: tampoco se amplía el dominio."""
        self.config.write({
            'authorized_seller': True,
            'seller_ids': [Command.clear()],
        })
        base = super(type(self.config), self.config)._employee_domain(self.env.user.id)
        self.assertEqual(self.config._employee_domain(self.env.user.id), base)

    # ------------------------------------------------------------------
    # Carga de datos en el TPV
    # ------------------------------------------------------------------
    def test_pos_data_models_include_employees(self):
        """Con vendedores autorizados el TPV carga hr.employee."""
        self.config.write({
            'authorized_seller': True,
            'seller_ids': [Command.set(self.vendedor_a.ids)],
        })
        models = self.env['pos.session']._load_pos_data_models(self.config)
        self.assertIn('hr.employee', models)

    def test_pos_data_models_no_duplicate(self):
        """hr.employee no se añade dos veces si ya venía de pos_hr."""
        self.config.write({
            'authorized_seller': True,
            'seller_ids': [Command.set(self.vendedor_a.ids)],
        })
        models = self.env['pos.session']._load_pos_data_models(self.config)
        self.assertEqual(models.count('hr.employee'), 1)

    # ------------------------------------------------------------------
    # Vendedor en la orden y en el análisis de ventas
    # ------------------------------------------------------------------
    def _paid_order(self, seller=None):
        """Orden cobrada en efectivo, con o sin vendedor.

        Se arma por ORM (sesión + líneas + ``pos.make.payment``) en lugar
        de por la interfaz: lo que se prueba es el campo del servidor y su
        llegada al análisis de ventas.
        """
        self.config.write({'authorized_seller': True,
                           'seller_ids': [Command.set(self.vendedor_a.ids)]})
        session = self.open_new_session()
        vals = {
            'company_id': self.env.company.id,
            'session_id': session.id,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
            'lines': [Command.create({
                'product_id': self.product_a.id,
                'qty': 1,
                'price_unit': self.product_a.lst_price,
                'price_subtotal': self.product_a.lst_price,
                'price_subtotal_incl': self.product_a.lst_price,
                'tax_ids': [Command.set(self.product_a.taxes_id.ids)],
            })],
        }
        if seller:
            vals['seller_id'] = seller.id
        order = self.env['pos.order'].create(vals)
        order.lines._onchange_amount_line_all()
        order._compute_prices()
        ctx = {'active_ids': order.ids, 'active_id': order.id}
        self.env['pos.make.payment'].with_context(**ctx).create({
            'payment_method_id': self.cash_pm1.id,
        }).with_context(**ctx).check()
        return order

    def test_order_keeps_seller(self):
        """La orden guarda el vendedor asignado."""
        order = self._paid_order(self.vendedor_a)
        self.assertEqual(order.seller_id, self.vendedor_a)

    def test_order_without_seller_is_valid(self):
        """El vendedor es opcional: sin él la orden se cobra igual."""
        order = self._paid_order()
        self.assertFalse(order.seller_id)
        self.assertEqual(order.state, 'paid')

    def test_report_exposes_seller(self):
        """El análisis de ventas trae el vendedor de la orden."""
        order = self._paid_order(self.vendedor_a)
        rows = self.env['report.pos.order'].search_read(
            [('order_id', '=', order.id)], ['seller_id'])
        self.assertTrue(rows, 'la orden debe aparecer en el análisis de ventas')
        self.assertEqual(rows[0]['seller_id'][0], self.vendedor_a.id)

    def test_report_groups_by_seller(self):
        """La vista SQL agrupa por vendedor sin romper el GROUP BY."""
        self._paid_order(self.vendedor_a)
        groups = self.env['report.pos.order']._read_group(
            [('seller_id', '=', self.vendedor_a.id)],
            groupby=['seller_id'], aggregates=['price_total:sum'])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], self.vendedor_a)

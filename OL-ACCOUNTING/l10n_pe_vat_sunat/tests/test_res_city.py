# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResCity(TransactionCase):
    """La unicidad de ciudades solo rige en Perú (no bloquea datos oficiales
    de otros países con ciudades homónimas)."""

    def test_unique_only_in_peru(self):
        City = self.env['res.city']
        pe = self.env.ref('base.pe')
        state_pe = self.env['res.country.state'].search([('country_id', '=', pe.id)], limit=1)
        City.create({'name': 'Ciudad Test PE', 'country_id': pe.id, 'state_id': state_pe.id})
        with self.assertRaises(ValidationError):
            City.create({'name': 'Ciudad Test PE', 'country_id': pe.id, 'state_id': state_pe.id})
        us = self.env.ref('base.us')
        state_us = self.env['res.country.state'].search([('country_id', '=', us.id)], limit=1)
        City.create({'name': 'Springfield Test', 'country_id': us.id, 'state_id': state_us.id})
        City.create({'name': 'Springfield Test', 'country_id': us.id, 'state_id': state_us.id})

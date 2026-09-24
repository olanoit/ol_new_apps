# -*- coding: utf-8 -*-
"""Datos geográficos del Perú (res.city) y su enganche con las direcciones.

El módulo activa ``enforce_cities`` en el país, lo que convierte la ciudad
en un desplegable dependiente del departamento en todas las direcciones.
Si el dato estuviera incompleto o mal enlazado, el formulario de contacto
dejaría de ofrecer ciudades — de ahí las comprobaciones de integridad.
"""
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPeCity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.peru = cls.env.ref('base.pe')
        cls.City = cls.env['res.city']

    def test_country_enforces_cities(self):
        """El país tiene activado el desplegable de ciudades."""
        self.assertTrue(self.peru.enforce_cities)

    def test_cities_loaded(self):
        """Están cargadas las ciudades del data del módulo."""
        self.assertGreaterEqual(
            self.City.search_count([('country_id', '=', self.peru.id)]), 421)

    def test_every_city_has_state(self):
        """Ninguna ciudad queda huérfana de departamento."""
        orphans = self.City.search([
            ('country_id', '=', self.peru.id), ('state_id', '=', False)])
        self.assertFalse(orphans, 'ciudades sin departamento: %s'
                         % orphans.mapped('name'))

    def test_city_state_belongs_to_peru(self):
        """El departamento de cada ciudad es peruano (no cruza países)."""
        mismatched = self.City.search([
            ('country_id', '=', self.peru.id),
            ('state_id.country_id', '!=', self.peru.id)])
        self.assertFalse(mismatched, 'ciudades con departamento de otro país: %s'
                         % mismatched.mapped('name'))

    def test_departments_covered(self):
        """Los departamentos con ciudades son los del país."""
        states = self.City.search(
            [('country_id', '=', self.peru.id)]).mapped('state_id')
        self.assertGreaterEqual(
            len(states), 24,
            'deben cubrirse los 24 departamentos + Callao/Lima Metropolitana')
        for state in states:
            self.assertEqual(state.country_id, self.peru)

    def test_reference_cities_present(self):
        """Capitales de referencia presentes (control del dato cargado)."""
        for name in ('Lima', 'Arequipa', 'Trujillo', 'Cusco', 'Chiclayo'):
            self.assertTrue(
                self.City.search_count([
                    ('country_id', '=', self.peru.id), ('name', '=', name)]),
                'falta la ciudad %s' % name)

    def test_partner_city_id_resolves_state(self):
        """Al elegir ciudad en el formulario se copian departamento y nombre.

        Con ``Form`` porque la sincronización ``city_id`` → ``city`` la
        hace un onchange de ``base_address_extended``: en un ``create``
        por ORM el campo de texto se queda vacío.
        """
        city = self.City.search([('country_id', '=', self.peru.id)], limit=1)
        form = Form(self.env['res.partner'])
        form.name = 'CONTACTO CIUDAD PE'
        form.country_id = self.peru
        form.state_id = city.state_id
        form.city_id = city
        partner = form.save()
        self.assertEqual(partner.city_id.state_id, partner.state_id)
        self.assertEqual(partner.city, city.name,
                         'el nombre de la ciudad se copia al campo de texto')

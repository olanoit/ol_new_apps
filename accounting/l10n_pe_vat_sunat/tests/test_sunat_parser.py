# -*- coding: utf-8 -*-
"""Regresión del parser del scraper SUNAT oficial.

SUNAT intercala etiquetas ("Número de RUC:") entre los <h4>, por lo que la
cabecera "RUC - RAZÓN SOCIAL" no está en una posición fija. El parser debe
localizarla por su patrón, no por índice.
"""
from odoo.tests import TransactionCase, tagged

from ..services import sunat_oficial

# Estructura real del portal (jul-2026): el h4 con el nombre va DESPUÉS de la
# etiqueta "Número de RUC:".
FIXTURE_HTML = """
<div class="list-group">
  <h4 class="list-group-item-heading">Número de RUC:</h4>
  <h4 class="list-group-item-heading">20608151771 - ANGEL DIVINO BUS S.A.C.</h4>
  <h4 class="list-group-item-heading">Tipo Contribuyente:</h4>
  <h4 class="list-group-item-heading">Nombre Comercial:</h4>
  <p class="list-group-item-text">SOCIEDAD ANONIMA CERRADA</p>
  <p class="list-group-item-text">ANGEL DIVINO</p>
  <p class="list-group-item-text">24/06/2021</p>
  <p class="list-group-item-text">01/07/2021</p>
  <p class="list-group-item-text">ACTIVO</p>
  <p class="list-group-item-text">HABIDO</p>
  <p class="list-group-item-text">CAL.NICOLAS DE PIEROLA NRO. 720 - LAMBAYEQUE - CHICLAYO - CHICLAYO</p>
</div>
"""


@tagged('post_install', '-at_install')
class TestSunatParser(TransactionCase):

    def test_name_not_label(self):
        r = sunat_oficial._parse_ruc_html(FIXTURE_HTML, '20608151771')
        # El bug era que name salía 'Número de RUC:'.
        self.assertEqual(r.name, 'ANGEL DIVINO BUS S.A.C.')
        self.assertNotIn('Número de RUC', r.name)
        self.assertEqual(r.ruc, '20608151771')

    def test_other_fields_ok(self):
        r = sunat_oficial._parse_ruc_html(FIXTURE_HTML, '20608151771')
        self.assertEqual(r.commercial_name, 'ANGEL DIVINO')
        self.assertEqual(r.state, 'ACTIVO')
        self.assertEqual(r.condition, 'HABIDO')
        self.assertTrue(r.address.startswith('CAL.NICOLAS'))

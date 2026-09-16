# -*- coding: utf-8 -*-
"""Contraste del catálogo de detracciones con la página de SUNAT.

La página de ejemplo reproduce la estructura de la real: una tabla de
códigos y tablas de porcentajes por fecha, sin código y con las notas
«(3) y (13)» pegadas al nombre.
"""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.detraction_check import L10nPeDetractionCheck
from ..tools import sunat_spot_page

CODES = [
    ('1', 'Azúcar y melaza de caña (1)'), ('3', 'Alcohol etílico (1)'),
    ('4', 'Recursos hidrobiológicos'), ('5', 'Maíz amarillo duro'),
    ('7', 'Caña de azúcar (1)'), ('8', 'Madera'), ('9', 'Arena y piedra.'),
    ('10', 'Residuos, subproductos, desechos, recortes, desperdicios y formas primarias'),
    ('12', 'Intermediación laboral y tercerización'), ('13', 'Animales vivos'),
    ('14', 'Carnes y despojos comestibles'),
    ('17', 'Harina, polvo y “pellets” de pescado, crustáceos, moluscos'),
    ('19', 'Arrendamiento de bienes'),
    ('20', 'Mantenimiento y reparación de bienes muebles'),
    ('21', 'Movimiento de carga'), ('22', 'Otros servicios empresariales'),
    ('24', 'Comisión mercantil'), ('25', 'Fabricación de bienes por encargo'),
    ('26', 'Servicio de transporte de personas'), ('30', 'Contratos de construcción'),
    ('31', 'Oro gravado con el IGV'), ('34', 'Minerales metálicos no auríferos'),
    ('35', 'Bienes exonerados del IGV'),
    ('36', 'Oro y demás minerales metálicos exonerados del IGV'),
    ('37', 'Demás servicios gravados con el IGV'), ('39', 'Minerales no metálicos'),
    ('40', 'Bien inmueble gravado con el IGV'), ('41', 'Plomo (4)'),
]
ANNEX_1 = [('1', 'Azúcar y melaza de caña', '10%'), ('2', 'Alcohol etílico', '10%')]
ANNEX_2 = [
    ('1', 'Recursos hidrobiológicos', '4%'), ('2', 'Maíz amarillo duro', '4%'),
    ('3', 'Arena y piedra', '10%'),
    ('4', 'Residuos, subproductos, desechos, recortes, desperdicios y formas primarias derivadas', '15%'),
    ('5', 'Carnes y despojos comestibles (2)', '4%'),
    ('6', 'Harina, polvo y "pellets" de pescado, crustáceos, moluscos y demás', '4%'),
    ('7', 'Madera', '4%'), ('8', 'Oro gravado con el IGV(3)', '10%'),
    ('9', 'Minerales metálicos no auríferos', '10%'),
    ('10', 'Bienes exonerados del IGV', '1.5%'),
    ('11', 'Oro y demás minerales metálicos exonerados del IGV', '1.5%'),
    ('12', 'Minerales no metálicos', '10%'),
]
ANNEX_3_2015 = [
    ('1', 'Intermediación laboral y tercerización(3) y (13)', '10%'),
    ('2', 'Arrendamiento de bienes(3) y (13)', '10%'),
    ('3', 'Mantenimiento y reparación de bienes muebles(8) y (13)', '10%'),
    ('4', 'Movimiento de carga(5) (7) y (13)', '10%'),
    ('5', 'Otros Servicios Empresariales(5) (7) y (12)', '10%'),
    ('6', 'Comisión mercantil(3) y 13)', '10%'),
    ('7', 'Fabricación de bienes por encargo(3), (5) y (13)', '10%'),
    ('8', 'Servicio de transporte de personas(3) y (13)', '10%'),
    ('9', 'Contratos de Construcción(2) y (11)', '4%'),
    ('10', 'Demás servicios gravados con el IGV(4), (6), (7) y (12)', '10%'),
]
ANNEX_3_2018 = [
    ('1', 'Intermediación laboral y tercerización(3) y (13)', '12%'),
    ('3', 'Mantenimiento y reparación de bienes muebles(8) y (13)', '12%'),
    ('5', 'Otros Servicios Empresariales(5) (7) y (12)', '12%'),
    ('10', 'Demás servicios gravados con el IGV(4), (6), (7) y (12)', '12%'),
]


def _table(header, rows):
    head = ''.join('<td>%s</td>' % cell for cell in header)
    body = ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % cell for cell in row)
                   for row in rows)
    return '<table><tr>%s</tr>%s</table>' % (head, body)


def build_page(codes=CODES, extra=''):
    return ('<html><body><h1>Anexos</h1>%s%s%s%s%s%s%s%s</body></html>' % (
        _table(['Último dígito del RUC', 'Fecha de vencimiento'], [('0', '26/03/2025')]),
        _table(['', 'DEFINICIÓN', 'DESCRIPCIÓN', 'PORCENTAJE'],
               [(n, d, 'Bienes…', p) for n, d, p in ANNEX_1]),
        _table(['DEFINICIÓN', 'DESCRIPCIÓN', '% Desde el 01.01.2015'],
               [(n, d, 'Bienes…', p) for n, d, p in ANNEX_2]),
        # Como en la página real: sin fecha y con la comilla de cierre de la
        # norma pegada al porcentaje.
        _table(['', 'DEFINICIÓN', 'DESCRIPCIÓN', 'PORCENTAJE'],
               [('4', 'Caña de azúcar', 'Bienes…', '10%”')]),
        _table(['DEFINICIÓN', 'DESCRIPCIÓN', 'Porcentaje (%) aplicable desde el 01.08.2019'],
               [('Plomo', 'Solo los bienes…', '15%')]),
        _table(['DEFINICIÓN', 'DESCRIPCIÓN', '% Desde el 01.01.2015'],
               [(n, d, 'A lo siguiente…', p) for n, d, p in ANNEX_3_2015]),
        _table(['DEFINICIÓN', 'DESCRIPCIÓN', '% Desde el 01.04.2018'],
               [(n, d, 'A lo siguiente…', p) for n, d, p in ANNEX_3_2018] + [('', '', '', '')]),
        _table(['CÓDIGO', 'TIPO DE BIEN O SERVICIO'], codes) + extra,
    )).encode()


@tagged('post_install', '-at_install')
class TestDetractionCheck(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Check = cls.env['l10n_pe.detraction.check']
        cls.dtype_012 = cls.env.ref('al_l10n_pe_detraction.detraction_012')
        cls.dtype_037 = cls.env.ref('al_l10n_pe_detraction.detraction_037')

    def _check(self, page=None, **kwargs):
        with patch.object(L10nPeDetractionCheck, '_l10n_pe_download',
                          return_value=page or build_page()):
            return self.Check._l10n_pe_check(**kwargs)

    def _drop_codes(self, *codes):
        """El módulo ya trae todos los códigos de la página de ejemplo;
        sin algunos se prueba el estado «Nuevo en SUNAT»."""
        for code in codes:
            self.env.ref('al_l10n_pe_detraction.detraction_%s' % code).unlink()

    @staticmethod
    def _line(check, code):
        return check.line_ids.filtered(lambda l: l.code == code)

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def test_normalize_drops_notes_and_accents(self):
        normalize = sunat_spot_page.normalize
        self.assertEqual(normalize('Demás servicios gravados con el IGV(4), (6), (7) y (12)'),
                         'demas servicios gravados con el igv')
        self.assertEqual(normalize('Comisión mercantil(3) y 13)'), 'comision mercantil')
        self.assertEqual(normalize('Arena y piedra.'), 'arena y piedra')

    def test_parse_takes_the_latest_rate(self):
        data = sunat_spot_page.parse_html(build_page())
        self.assertEqual(data['codes']['037'][0], 'Demás servicios gravados con el IGV')
        self.assertEqual(data['rates']['037'], (12.0, date(2018, 4, 1)))
        self.assertEqual(data['rates']['019'], (10.0, date(2015, 1, 1)))
        self.assertEqual(data['rates']['001'], (10.0, None))
        self.assertEqual(data['rates']['041'], (15.0, date(2019, 8, 1)))
        self.assertEqual(data['rates']['010'][0], 15.0, 'nombre cortado: coincide por prefijo')
        self.assertEqual(data['rates']['035'][0], 1.5)
        self.assertEqual(data['rates']['036'][0], 1.5)
        self.assertTrue(data['codes']['007'][1], 'la nota (1) marca el Anexo 1')
        self.assertFalse(data['codes']['041'][1], 'la nota (4) no es el Anexo 1')
        self.assertNotIn('013', data['rates'])

    def test_page_without_codes_is_rejected(self):
        with self.assertRaises(sunat_spot_page.SpotPageError):
            sunat_spot_page.parse_html(build_page(codes=CODES[:5]))
        with self.assertRaisesRegex(UserError, 'no trae el catálogo'):
            self._check(page=build_page(codes=[]))

    # ------------------------------------------------------------------
    # Comparación
    # ------------------------------------------------------------------
    def test_compare_statuses(self):
        self._drop_codes('007', '041')
        self.dtype_012.percentage = 10.0
        check = self._check()
        self.assertEqual(self._line(check, '037').status, 'match')
        diff = self._line(check, '012')
        self.assertEqual(diff.status, 'rate_diff')
        self.assertEqual((diff.odoo_percentage, diff.sunat_percentage), (10.0, 12.0))
        self.assertEqual(diff.sunat_since, date(2018, 4, 1))
        self.assertEqual(self._line(check, '041').status, 'new')
        self.assertEqual(self._line(check, '007').status, 'new')
        self.assertEqual(self._line(check, '013').status, 'no_rate')
        self.assertEqual(self._line(check, '040').status, 'no_rate')
        self.assertEqual(self._line(check, '027').status, 'missing')
        # 012 distinto + 007 y 041 nuevos.
        self.assertEqual(check.difference_count, 3)
        self.assertEqual(check.pending_count, 3)

    def test_catalog_matches_sunat(self):
        """El catálogo del módulo ya no tiene diferencias con SUNAT."""
        check = self._check()
        self.assertEqual(check.difference_count, 0)
        self.assertEqual(self._line(check, '041').status, 'match')
        self.assertEqual(self._line(check, '007').type_id,
                         self.env.ref('al_l10n_pe_detraction.detraction_007'))

    # ------------------------------------------------------------------
    # Aplicación
    # ------------------------------------------------------------------
    def test_apply_updates_rate_and_products(self):
        self._drop_codes('007', '041')
        self.dtype_012.percentage = 10.0
        product = self.env['product.template'].create({
            'name': 'Servicio de intermediación DEMO',
            'l10n_pe_detraction_type_id': self.dtype_012.id,
        })
        check = self._check()
        self._line(check, '012').to_apply = True
        check.action_apply()
        self.assertEqual(self.dtype_012.percentage, 12.0)
        self.assertEqual(product.l10n_pe_withhold_percentage, 12.0)
        self.assertTrue(self._line(check, '012').applied)
        self.assertFalse(self._line(check, '041').applied, 'solo lo marcado')
        self.assertEqual(check.pending_count, 2)
        self.assertIn('012', check.message_ids[:1].body)

    def test_apply_creates_new_codes(self):
        self._drop_codes('007', '041')
        check = self._check()
        self._line(check, '007').to_apply = True
        self._line(check, '041').to_apply = True
        check.action_apply()
        cane = self._line(check, '007').type_id
        lead = self._line(check, '041').type_id
        self.assertEqual((cane.code, cane.name, cane.percentage), ('007', 'Caña de azúcar', 10.0))
        annex1_min = self.env.ref('al_l10n_pe_detraction.detraction_001').min_amount
        self.assertEqual(cane.min_amount, annex1_min, 'Anexo 1: el mínimo de los otros bienes del anexo')
        self.assertEqual(lead.min_amount, 700.0)
        self.assertEqual(lead.percentage, 15.0)

    def test_apply_on_a_stale_check(self):
        """Un contraste antiguo no duplica códigos creados después ni pisa un
        porcentaje ya corregido: se resuelve contra el catálogo de ahora."""
        cane = self.env.ref('al_l10n_pe_detraction.detraction_007')
        lead = self.env.ref('al_l10n_pe_detraction.detraction_041')
        self._drop_codes('007', '041')
        self.dtype_012.percentage = 10.0
        stale = self._check()
        # Después del contraste el catálogo cambia: vuelven 007 (archivado)
        # y 041, y alguien corrige el 012 a mano.
        restored_cane = self.env['l10n_pe.detraction.type'].create(
            {'code': '007', 'name': 'Caña', 'percentage': 10.0, 'active': False})
        restored_lead = self.env['l10n_pe.detraction.type'].create(
            {'code': '041', 'name': 'Plomo', 'percentage': 12.0})
        self.dtype_012.percentage = 12.0
        self.assertFalse(cane.exists() or lead.exists())
        stale.line_ids.filtered(lambda l: l.actionable).write({'to_apply': True})
        stale.action_apply()
        self.assertEqual(self._line(stale, '007').type_id, restored_cane)
        self.assertEqual(self._line(stale, '041').type_id, restored_lead)
        self.assertEqual(restored_lead.percentage, 15.0, 'porcentaje de SUNAT')
        self.assertEqual(self.dtype_012.percentage, 12.0)
        self.assertEqual(self.env['l10n_pe.detraction.type'].with_context(
            active_test=False).search_count([('code', 'in', ('007', '041'))]), 2)
        self.assertEqual(stale.pending_count, 0)
        body = stale.message_ids[:1].body
        self.assertIn('007: ya estaba', body)
        self.assertIn('012: ya estaba', body)
        self.assertIn('041: 12.0 % → 15.0 %', body)

    def test_activity_closes_only_when_nothing_is_pending(self):
        self._drop_codes('007', '041')
        check = self._check()
        check._l10n_pe_schedule_review()
        self.assertTrue(check.activity_ids)
        self._line(check, '007').to_apply = True
        check.action_apply()
        self.assertTrue(check.activity_ids, 'queda el 041 por aplicar')
        self._line(check, '041').to_apply = True
        check.action_apply()
        self.assertFalse(check.activity_ids)

    def test_apply_needs_a_marked_line(self):
        self._drop_codes('041')
        check = self._check()
        with self.assertRaisesRegex(UserError, 'Marque'):
            check.action_apply()

    # ------------------------------------------------------------------
    # Botón y acción planificada
    # ------------------------------------------------------------------
    def test_button_opens_the_check(self):
        with patch.object(L10nPeDetractionCheck, '_l10n_pe_download',
                          return_value=build_page()):
            action = self.Check.action_check_now()
        self.assertEqual(action['res_model'], 'l10n_pe.detraction.check')
        self.assertTrue(self.Check.browse(action['res_id']).line_ids)

    def test_cron_only_when_differences_change(self):
        manager = self.env['res.users'].create({
            'name': 'Contador jefe SPOT', 'login': 'contador.spot',
            'group_ids': [(4, self.env.ref('account.group_account_manager').id)],
        })
        before = self.Check.search_count([])
        with patch.object(L10nPeDetractionCheck, '_l10n_pe_download',
                          return_value=build_page()):
            self._drop_codes('041')
            self.Check._cron_l10n_pe_check_sunat()
            self.Check._cron_l10n_pe_check_sunat()
            self.assertEqual(self.Check.search_count([]), before + 1, 'sin cambios no repite')
            check = self.Check.search([], limit=1)
            activity = check.activity_ids.filtered(lambda a: a.user_id == manager)
            self.assertEqual(activity.summary, 'Revisar diferencias de detracciones con SUNAT')
            self.dtype_012.percentage = 10.0
            self.Check._cron_l10n_pe_check_sunat()
        self.assertEqual(self.Check.search_count([]), before + 2)

    def test_cron_survives_a_download_error(self):
        with patch.object(L10nPeDetractionCheck, '_l10n_pe_download',
                          side_effect=UserError('404')):
            self.Check._cron_l10n_pe_check_sunat()

    def test_cron_is_registered(self):
        cron = self.env.ref('al_l10n_pe_detraction.ir_cron_detraction_check_sunat')
        self.assertEqual(cron.interval_type, 'months')
        self.assertEqual(self.Check._l10n_pe_source_url(),
                         'https://orientacion.sunat.gob.pe/apendices-del-sistema-de-detracciones')

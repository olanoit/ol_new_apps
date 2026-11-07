# -*- coding: utf-8 -*-
"""La obra en el portal del residente (paquete 6, entrega 3: CR-58 y CR-54).
Datos ficticios."""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .test_resident import ResidentCommon


@tagged('post_install', '-at_install')
class TestSiteOverview(ResidentCommon):

    def _today(self):
        return fields.Date.context_today(self._service(self.resident_user))

    def test_summary_matches_desktop_board(self):
        """Los números del Resumen son los del tablero de obra del escritorio
        (P18) y sin montos si la compañía no los permite."""
        progress = self._report(40.0, 'p6-ov-1')
        progress.with_context(construction_portal_resident_projects=[self.project.id]).with_user(
            self.resident_user).sudo().action_validate()
        site = self._service(self.resident_user).sync(self.project.id)['site']
        project = self.project.sudo()
        self.assertTrue(site['has_plan'])
        self.assertAlmostEqual(site['summary']['real'], round(project.construction_board_progress, 4))
        self.assertEqual(site['summary']['to_validate'],
                         project.construction_progress_to_validate_count)
        self.assertFalse(site['summary']['amounts'])
        self.company.construction_portal_show_amounts = True
        site = self._service(self.resident_user).sync(self.project.id)['site']
        self.assertAlmostEqual(site['summary']['amounts']['planned'],
                               project.construction_board_planned)
        # Solo el residente (con usuario y clave) recibe la obra.
        self.assertNotIn('site', self._service(self.foreman_user).sync(self.project.id))
        self.assertNotIn('site', self._service(self.resident_user, login='qr').sync(
            self.project.id))

    def test_tasks_columns_week_and_late(self):
        today = self._today()
        week_start, week_end = self.project._construction_period(today)
        # La partida del tabique vence ayer sin avance: atrasada.
        self.wall.date_needed = today - timedelta(days=1)
        site = self._service(self.resident_user).sync(self.project.id)['site']
        wall = next(t for t in site['tasks'] if t['id'] == self.wall.task_id.id)
        self.assertTrue(wall['late'])
        self.assertIn(wall['column'], ('doing', 'ending'))
        self.assertEqual(wall['expected'], 1.0)
        self.assertGreaterEqual(site['summary']['late'], 1)
        self.assertGreater(site['summary']['programmed'], 0.0)
        self.assertTrue(site['curve'])
        self.assertTrue(site['specialties'])
        # Termina esta semana con poco avance: en riesgo en la Semana.
        self.wall.date_needed = week_end if week_end >= today else today
        site = self._service(self.resident_user).sync(self.project.id)['site']
        ending = [t for t in site['week']['ending'] if t['id'] == self.wall.task_id.id]
        self.assertTrue(ending)
        self.assertIn('riesgo', ending[0]['warning'])
        # Empieza la semana próxima: «Por iniciar».
        self.wall.date_needed = week_end + timedelta(days=3)
        site = self._service(self.resident_user).sync(self.project.id)['site']
        wall = next(t for t in site['tasks'] if t['id'] == self.wall.task_id.id)
        self.assertEqual(wall['column'], 'todo')
        self.assertFalse(wall['late'])

    def test_expected_fraction_matches_site_days(self):
        """El programado por días hábiles da lo mismo que el conteo de días
        hábiles de la obra, con la tabla acumulada compartida."""
        company = self.company
        service = self.env['construction.portal.service']
        cache = {}
        base = self._today() - timedelta(days=60)
        for offset, length, probe in [(0, 20, 5), (40, 0, 40), (10, 35, -3), (3, 60, 70),
                                      (-20, 15, 2), (25, 9, 30), (-40, 80, 41)]:
            start = base + timedelta(days=offset)
            end = start + timedelta(days=length)
            day = start + timedelta(days=probe)
            got = service._expected_fraction(company, (start, end), day, cache)
            if day < start:
                want = 0.0
            elif day >= end:
                want = 1.0
            else:
                want = min(1.0, company._construction_count_site_days(start, day)
                           / (company._construction_count_site_days(start, end) or 1))
            self.assertAlmostEqual(got, want, places=9)

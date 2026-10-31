# -*- coding: utf-8 -*-
"""Revisión de feriados en Odoo 20 (31/10/2026).

Cada test reproduce un hallazgo de la revisión (#9, #18) y falla con el
código anterior a su corrección.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReviewHolidays(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Holiday = cls.env['pe.public.holiday']
        cls.Leaves = cls.env['resource.calendar.leaves']

    # ------------------------------------------------------------------
    # #9 Calendario compartido entre compañías
    # ------------------------------------------------------------------
    def test_09_shared_calendar_gets_one_leave_per_company(self):
        """Cada pasada del cron (una por compañía) cambiaba la compañía del
        único descanso del calendario compartido: el feriado dejaba de
        existir para las demás compañías."""
        first = self.env['res.company'].create(
            {'name': 'Feriados A SAC', 'tz': 'America/Lima'})
        second = self.env['res.company'].create(
            {'name': 'Feriados B SAC', 'tz': 'America/Lima'})
        shared = self.env['resource.calendar'].create({
            'name': 'Calendario compartido', 'company_id': False})
        holiday = self.Holiday.create(
            {'name': 'Feriado compartido', 'date': date(2042, 7, 28)})
        for company in (first, second, first):
            holiday.with_company(company).with_context(
                allowed_company_ids=company.ids).action_apply_to_calendars()
        leaves = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', shared.id)])
        self.assertEqual(len(leaves), 2, 'uno por compañía, sin duplicar')
        for company in (first, second):
            self.assertTrue(self.Leaves.search_count([
                ('pe_public_holiday_id', '=', holiday.id),
                ('calendar_id', '=', shared.id),
                ('company_id', 'in', (False, company.id))]),
                'el feriado existe para %s' % company.name)

    # ------------------------------------------------------------------
    # #18 Calendarios creados durante el año
    # ------------------------------------------------------------------
    def test_18_cron_runs_every_month(self):
        """El cron es idempotente y corre cada mes: un calendario o una
        obra creados en el año reciben los feriados sin esperar a enero."""
        cron = self.env.ref(
            'al_hr_pe_public_holidays.ir_cron_apply_yearly_holidays')
        self.assertEqual((cron.interval_number, cron.interval_type),
                         (1, 'months'))

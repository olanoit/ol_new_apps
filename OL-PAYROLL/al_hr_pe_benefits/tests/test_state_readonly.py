# -*- coding: utf-8 -*-
"""Campos editables según el estado y botones de listas solo con datos."""
from datetime import date

from lxml import etree

from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestStateReadonly(BenefitsCaseBase):

    def _arch(self, model, view_type, xmlid=None):
        view_id = self.env.ref(xmlid).id if xmlid else None
        return etree.fromstring(self.env[model].get_view(view_id, view_type)['arch'])

    def _cts(self):
        cts = self.env['hr.cts'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '05',
            'payslip_run_id': self.batch.id, 'deposit_date': date(2026, 5, 15)})
        cts.action_process()
        return cts

    def test_views_tie_edition_to_state(self):
        """CTS: cabecera y líneas solo en borrador; el formulario de la línea
        se bloquea con la cabecera cerrada y el botón de detalle depende de
        que haya histórico."""
        cts_form = self._arch('hr.cts', 'form')
        for fname in ('payslip_run_id', 'deposit_date', 'line_ids'):
            node = cts_form.xpath("//field[@name='%s']" % fname)[0]
            self.assertIn('state', node.get('readonly') or '', fname)
        line_form = self._arch('hr.cts.line', 'form', 'al_hr_pe_benefits.hr_cts_line_view_form')
        for fname in ('months', 'days', 'commission', 'cts_interest'):
            node = line_form.xpath("//field[@name='%s']" % fname)[0]
            self.assertIn('l10n_pe_locked', node.get('readonly') or '', fname)
        self.assertIn('l10n_pe_locked', line_form.xpath(
            "//button[@name='action_compute']")[0].get('invisible'))
        line_list = self._arch('hr.cts.line', 'list', 'al_hr_pe_benefits.hr_cts_line_view_list')
        self.assertEqual(line_list.xpath("//button[@name='action_show_details']")[0].get('invisible'),
                         'not l10n_pe_has_history')

    def test_line_locked_follows_header(self):
        cts = self._cts()
        line = cts.line_ids[:1]
        self.assertTrue(line)
        self.assertFalse(line.l10n_pe_locked)
        cts.state = 'exported'
        self.assertTrue(line.l10n_pe_locked)

    def test_history_flag_matches_payslips(self):
        """Hay histórico si el trabajador tiene boletas BASE en los 6 meses
        previos al depósito; sin boletas el botón no se muestra."""
        cts = self._cts()
        line = cts.line_ids.filtered(lambda l: l.employee_id == self.employee)
        expected = bool(self.env['hr.main.parameter'].get_salary_history(
            self.employee, self.company, cts.deposit_date))
        self.assertEqual(line.l10n_pe_has_history, expected)

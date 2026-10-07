# -*- coding: utf-8 -*-
"""Página «Planilla PE» del empleado y de la nómina, y nombres legibles.

Los datos peruanos del trabajador van en una página con pestañas internas
(en vez de repartirse por «Personal» y «Nómina»); los registros de planilla
sin campo ``name`` muestran un nombre legible y no «hr.cts.line,5».
"""
from datetime import date

from lxml import etree

from odoo import models
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Modelos de la suite sin campo «name» que definen su display_name.
DISPLAY_NAME_MODELS = (
    'l10n_pe.hr.uit', 'l10n_pe.hr.rmv', 'hr.work.suspension',
    'l10n_pe.hr.employee.education', 'l10n_pe.hr.attendance.monitor',
    'hr.loan.line', 'hr.cts.line', 'hr.cts.line.detalle', 'hr.rate.limit',
    'hr.fifth.category.line', 'hr.fifth.category.line.excluidos',
    'hr.gratification.line', 'hr.gratification.line.detalle',
    'hr.liquidation.vacation.line', 'hr.liquidation.extra_concepts',
    'hr.extra.concept.line', 'hr.provisiones', 'hr.provisiones.cts.line',
    'hr.provisiones.grati.line', 'hr.provisiones.vaca.line',
    'hr.provisiones.concepto', 'hr.subsidies.lot', 'hr.subsidies',
    'hr.subsidies.line', 'hr.subsidies.total', 'hr.subsidies.periodo',
    'hr.vacation.line', 'hr.leave.vacation.line', 'hr.vacation.rest',
    'hr.accrual.vacation', 'l10n_pe.hr.conafovicer.line',
    'l10n_pe.hr.construction.wage.line', 'hr.automate.multipayment.line',
)


@tagged('post_install', '-at_install')
class TestPayrollFormPages(TransactionCase):

    def _arch(self, model, xmlid):
        view = self.env[model].get_view(self.env.ref(xmlid).id, 'form')
        return etree.fromstring(view['arch'])

    def test_employee_pe_page(self):
        arch = self._arch('hr.employee', 'hr.view_employee_form')
        page = arch.xpath("//page[@name='l10n_pe_payroll']")
        self.assertEqual(len(page), 1)
        inner = page[0].xpath("./notebook[@name='l10n_pe_payroll_notebook']/page/@name")
        for name in ('l10n_pe_identification', 'l10n_pe_address', 'l10n_pe_tregistro'):
            self.assertIn(name, inner)
        # Nada PE queda suelto en las pestañas nativas.
        for native in ('personal_information', 'payroll_information'):
            fields = arch.xpath("//page[@name='%s']//field/@name" % native)
            self.assertFalse([f for f in fields if f.startswith('l10n_pe_')], native)

    def test_payslip_pe_page(self):
        arch = self._arch('hr.payslip', 'hr_payroll.view_hr_payslip_form')
        inner = arch.xpath("//page[@name='l10n_pe']/notebook"
                           "[@name='l10n_pe_payslip_notebook']/page/@name")
        self.assertIn('l10n_pe_calculation', inner)

    def test_models_define_display_name(self):
        base = models.BaseModel._compute_display_name
        for model in DISPLAY_NAME_MODELS:
            if model not in self.env:
                continue
            with self.subTest(model=model):
                self.assertIsNot(type(self.env[model])._compute_display_name, base)

    def test_display_name_values(self):
        uit = self.env['l10n_pe.hr.uit'].search([], limit=1)
        if uit:
            self.assertEqual(uit.display_name, 'UIT %s' % uit.year)
        employee = self.env['hr.employee'].create({'name': 'Trabajador nombre legible'})
        suspension_type = self.env['hr.suspension.type'].search([], limit=1)
        if not suspension_type:
            self.skipTest('sin tipos de suspensión')
        suspension = self.env['hr.work.suspension'].new({
            'employee_id': employee.id, 'suspension_type_id': suspension_type.id,
            'date_from': date(2026, 7, 1), 'date_to': date(2026, 7, 3)})
        self.assertTrue(suspension.display_name.startswith('Trabajador nombre legible · '))
        self.assertIn(' – ', suspension.display_name)

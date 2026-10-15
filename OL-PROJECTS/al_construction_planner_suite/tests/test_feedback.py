# -*- coding: utf-8 -*-
"""Correcciones de la prueba integral de ALTA (obra ZZMOMEN-98-26)."""
import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import file_open

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestFeedback(PlannerCommon):

    def _without_listed_ml(self):
        """La tipología como la importa MOMEN: sin actividades por ML en sus
        actividades por ambiente, solo con su ML bajo y alto."""
        self.typology.activity_line_ids.filtered(lambda l: l.activity_id.ml_based).unlink()

    def test_ml_from_typology_when_modules_have_no_width(self):
        self._without_listed_ml()
        preview = self._wizard()._collect()
        self.assertEqual(preview['line_kinds']['contract_space'][0], 8,
                         'la vista previa cuenta las líneas por ML del ambiente')
        self._generate()
        low = self.plan.line_ids.filtered(lambda l: l.activity_id == self.act_inst_low)
        high = self.plan.line_ids.filtered(lambda l: l.activity_id == self.act_inst_high)
        self.assertEqual(low.task_id, self.space_501 | self.space_502)
        self.assertEqual(set(low.mapped('qty_planned')), {2.12})
        self.assertEqual(set(high.mapped('qty_planned')), {2.10})
        self.assertEqual(set(low.mapped('price_unit_planned')), {18.0}, 'tarifa de la obra')

    def test_ml_goes_to_modules_with_widths(self):
        self._without_listed_ml()
        for template in self.typology.module_line_ids:
            if template.module_type in ('low', 'high'):
                template.write({'width_mm': 600, 'ml_group': template.module_type})
        self._generate()
        low = self.plan.line_ids.filtered(lambda l: l.activity_id == self.act_inst_low)
        self.assertTrue(low)
        self.assertEqual(set(low.task_id.mapped('construction_level')), {'module'})
        self.assertEqual(set(low.mapped('qty_planned')), {0.6})

    def test_listed_ml_activities_keep_their_quantity(self):
        """Una tipología que lista sus actividades por ML no recibe otras."""
        self._generate()
        ml_lines = self.plan.line_ids.filtered(lambda l: l.activity_id.ml_based)
        self.assertEqual(len(ml_lines), 4)

    def test_peru_public_holidays_move_income_dates(self):
        if 'pe.public.holiday' not in self.env:
            self.skipTest('al_hr_pe_public_holidays no está instalado')
        company = self.env.company
        day = date(2031, 12, 25)  # jueves
        self.env['pe.public.holiday'].search([('date', '=', day)]).unlink()
        self.assertFalse(company._construction_is_holiday(day))
        self.env.cr.cache.pop('al_construction_holidays', None)
        self.env['pe.public.holiday'].create({'name': 'Navidad (test)', 'date': day})
        self.assertTrue(company._construction_is_holiday(day))
        self.assertGreater(company._construction_next_working_day(day), day)

    def test_calendar_leave_invalidates_holiday_cache(self):
        company = self.env.company
        day = date(2031, 7, 3)
        self.assertFalse(company._construction_is_holiday(day))
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado (test)', 'calendar_id': company.resource_calendar_id.id,
            'date_from': '2031-07-03 05:00:00', 'date_to': '2031-07-03 22:00:00'})
        self.assertTrue(company._construction_is_holiday(day))

    def test_site_created_from_sale(self):
        service = self.env['product.product'].create({
            'name': 'Muebles de cocina (test)', 'type': 'service',
            'service_tracking': 'project_only', 'construction_creates_site': True})
        order = self.env['sale.order'].create({
            'partner_id': self.contractor.id,
            'order_line': [(0, 0, {'product_id': service.id, 'price_unit': 1000.0})]})
        order.action_confirm()
        project = order.order_line.project_id
        self.assertTrue(project.is_construction_site)
        self.assertEqual(project.construction_sale_order_id, order)

    def test_site_marked_later_takes_its_sale(self):
        service = self.env['product.product'].create({
            'name': 'Servicio sin obra (test)', 'type': 'service',
            'service_tracking': 'project_only'})
        order = self.env['sale.order'].create({
            'partner_id': self.contractor.id,
            'order_line': [(0, 0, {'product_id': service.id, 'price_unit': 500.0})]})
        order.action_confirm()
        project = order.order_line.project_id
        self.assertFalse(project.construction_sale_order_id)
        project.is_construction_site = True
        self.assertEqual(project.construction_sale_order_id, order)

    def test_approval_issues_grouped_by_product(self):
        self._generate()
        unstaged = next(i for i in self.plan._get_approval_issues()
                        if i.startswith('Líneas sin etapa'))
        self.assertEqual(unstaged.count(self.p_rh.display_name), 1)
        issues = unstaged
        self.assertIn('2 líneas (Dpto 501, Dpto 502)', issues)

    def test_import_reads_file_with_bin_size(self):
        with file_open('al_construction_planner_furniture/static/examples/maestro_planificacion_ejemplo.xlsx',
                       'rb') as handle:
            content = base64.b64encode(handle.read())
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': self.project.id, 'file': content,
            'filename': 'maestro_planificacion_ejemplo.xlsx'})
        sheets, errors = wizard.with_context(bin_size=True)._read_workbook()
        self.assertFalse(errors)
        self.assertTrue(sheets)

    def test_sites_menu_stays_in_the_app(self):
        menu = self.env.ref('al_construction_planner.menu_planner_sites')
        self.assertEqual(menu.action, self.env.ref('al_construction_planner.action_planner_construction_sites'))

    def test_batched_company_check_rejects_other_company(self):
        other = self.env['res.company'].create({'name': 'Otra compañía (test)'})
        foreign = self.env['product.product'].create({
            'name': 'Producto ajeno (test)', 'type': 'consu', 'company_id': other.id})
        Line = self.env['construction.resource.plan.line'].with_context(
            construction_plan_generating=True)
        with self.assertRaises(UserError):
            Line.create({'plan_id': self.plan.id, 'task_id': self.space_501.id,
                         'resource_type': 'material', 'product_id': foreign.id,
                         'product_uom_id': self.unit.id, 'qty_planned': 1.0})

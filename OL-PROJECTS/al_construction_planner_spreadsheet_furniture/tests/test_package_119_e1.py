# -*- coding: utf-8 -*-
"""Paquete 1.19, entrega 1. M119-03: la hoja de planificación toma del horario
de obra los días de trabajo, la jornada completa y los jornales por semana."""
import re

from odoo.tests import tagged

from odoo.addons.al_construction_planner.tests.test_package_119_schedule import site_calendar

from ..models.construction_sheet_parameter import PARAMETERS_SHEET
from .test_worksheet_v18 import TestWorksheetV18


@tagged('post_install', '-at_install')
class TestPackage119Schedule(TestWorksheetV18):

    def _parameters(self):
        data = self.site._construction_spreadsheet_data(10)
        cells = next(sheet for sheet in data['sheets'] if sheet['name'] == PARAMETERS_SHEET)['cells']
        rows = {cells[ref]: ref[1:] for ref in cells
                if re.fullmatch(r'G\d+', ref) and ref != 'G1'}
        return {key: (cells.get('C%s' % row), cells.get('F%s' % row))
                for key, row in rows.items()}

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])

    def test_without_schedule_nothing_changes(self):
        company = self.site.company_id or self.env.company
        company.construction_site_calendar_id = False
        company.construction_workday_hours = 8.0
        values = self._parameters()
        self.assertEqual(values['dias_semana'], ('5', '5'))
        self.assertEqual(values['horas_jornada'], ('8', '8'))
        self.assertEqual(values['jornales_semana'], ('5', '5'))
        metadata = self._document()._get_spreadsheet_metadata()
        self.assertEqual(metadata['construction_parameter_forced'], {})

    def test_schedule_writes_days_and_hours(self):
        company = self.site.company_id or self.env.company
        company.construction_site_calendar_id = site_calendar(self.env, company)
        values = self._parameters()
        self.assertEqual(values['dias_semana'], ('6', '6'))
        self.assertEqual(values['horas_jornada'], ('8', '8'))
        self.assertEqual(values['jornales_semana'], ('5.625', '5.625'))
        # Una hoja ya creada los recibe al abrirse y al validar.
        document = self._document()
        forced = {'dias_semana': '6', 'horas_jornada': '8', 'jornales_semana': '5.625'}
        self.assertEqual(document._get_spreadsheet_metadata()['construction_parameter_forced'],
                         forced)
        self.assertEqual(document._get_spreadsheet_metadata()[
            'construction_parameter_current']['jornales_semana'], '5.625')

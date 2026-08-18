# -*- coding: utf-8 -*-
from odoo.tests.common import tagged

from .common import GanttCommon
from ..models.gantt_field_map import CONFIG_PARAM, DEFAULT_DURATION_HOURS, DEFAULT_DURATION_PARAM


@tagged('post_install', '-at_install')
class TestGanttFieldMap(GanttCommon):

    def setUp(self):
        super().setUp()
        self.FieldMap = self.env['al.gantt.field.map']
        self.task_fields = self.env['project.task']._fields

    def _set_param(self, value):
        self.env['ir.config_parameter'].sudo().set_param(CONFIG_PARAM, value)

    def test_auto_detection_matches_registry(self):
        """La detección automática elige el primer candidato que exista."""
        field_map = self.FieldMap.get_map()
        self.assertEqual(field_map['source'], 'auto')

        expected_start = 'planned_date_begin' if 'planned_date_begin' in self.task_fields else None
        self.assertEqual(field_map['date_start'], expected_start)
        self.assertEqual(field_map['date_end'], 'date_deadline')
        expected_progress = 'progress' if 'progress' in self.task_fields else None
        self.assertEqual(field_map['progress'], expected_progress)
        self.assertEqual(field_map['mode'], 'planned' if expected_start else 'deadline_only')

    def test_override_with_valid_field(self):
        """Un campo existente sobreescribe la detección y marca source=config."""
        self._set_param('{"date_start": "create_date"}')
        field_map = self.FieldMap.get_map()
        self.assertEqual(field_map['date_start'], 'create_date')
        self.assertEqual(field_map['source'], 'config')
        self.assertEqual(field_map['date_end'], 'date_deadline')

    def test_override_with_unknown_field_is_ignored(self):
        """Un campo inexistente no rompe: se mantiene la detección automática."""
        self._set_param('{"date_end": "campo_que_no_existe"}')
        field_map = self.FieldMap.get_map()
        self.assertEqual(field_map['date_end'], 'date_deadline')
        self.assertEqual(field_map['source'], 'auto')

    def test_override_can_disable_a_concept(self):
        """Poner null desactiva el concepto y cambia el modo resultante."""
        self._set_param('{"date_start": null}')
        field_map = self.FieldMap.get_map()
        self.assertIsNone(field_map['date_start'])
        self.assertEqual(field_map['mode'], 'deadline_only')

        self._set_param('{"date_end": null}')
        field_map = self.FieldMap.get_map()
        self.assertEqual(field_map['mode'], 'none')

    def test_invalid_json_falls_back_to_auto(self):
        self._set_param('esto no es json')
        field_map = self.FieldMap.get_map()
        self.assertEqual(field_map['source'], 'auto')
        self.assertEqual(field_map['date_end'], 'date_deadline')

    def test_non_dict_json_falls_back_to_auto(self):
        self._set_param('["date_start"]')
        self.assertEqual(self.FieldMap.get_map()['source'], 'auto')

    def test_default_duration(self):
        self.assertEqual(self.FieldMap.get_default_duration_hours(), DEFAULT_DURATION_HOURS)
        self.env['ir.config_parameter'].sudo().set_param(DEFAULT_DURATION_PARAM, '4')
        self.assertEqual(self.FieldMap.get_default_duration_hours(), 4.0)
        self.env['ir.config_parameter'].sudo().set_param(DEFAULT_DURATION_PARAM, 'x')
        self.assertEqual(self.FieldMap.get_default_duration_hours(), DEFAULT_DURATION_HOURS)
        self.env['ir.config_parameter'].sudo().set_param(DEFAULT_DURATION_PARAM, '-3')
        self.assertEqual(self.FieldMap.get_default_duration_hours(), DEFAULT_DURATION_HOURS)

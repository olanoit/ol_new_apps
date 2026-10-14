# -*- coding: utf-8 -*-
"""«Generar metrados» (v1.6, M16-03): crea en borrador el metrado de cada
ambiente de la selección que todavía no lo tiene y abre sus medidas en una
lista editable, para cargarlas en bloque (o exportarlas a Excel y volver a
importarlas)."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class ConstructionMeasurementGenerateWizard(models.TransientModel):
    _name = 'construction.measurement.generate.wizard'
    _description = 'Generar metrados'
    _check_company_auto = True

    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, check_company=True,
        domain="[('is_construction_site', '=', True)]")
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    task_ids = fields.Many2many(
        'project.task', string='Pisos, departamentos o ambientes', check_company=True,
        domain="[('project_id', '=', project_id), "
               "('construction_level', 'in', ('floor', 'apartment', 'space'))]",
        help='Vacío: todos los ambientes de la obra.')
    space_count = fields.Integer(string='Ambientes sin metrado', compute='_compute_space_count')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        task_ids = self.env.context.get('construction_selection_task_ids')
        if task_ids:
            tasks = self.env['project.task'].browse(task_ids)
            res.setdefault('project_id', tasks[:1].project_id.id)
            res['task_ids'] = [(6, 0, tasks.filtered(
                lambda t: t.construction_level in ('floor', 'apartment', 'space')).ids)]
        return res

    def _get_spaces(self):
        self.ensure_one()
        domain = [('project_id', '=', self.project_id.id), ('construction_level', '=', 'space')]
        if self.task_ids:
            ids = self.task_ids.ids
            domain += ['|', '|', '|', ('id', 'in', ids),
                       ('construction_floor_task_id', 'in', ids),
                       ('construction_apartment_task_id', 'in', ids),
                       ('parent_id', 'in', ids)]
        spaces = self.env['project.task'].search(domain)
        done = self.env['construction.measurement'].search([('task_id', 'in', spaces.ids)]).task_id
        return spaces - done

    @api.depends('project_id', 'task_ids')
    def _compute_space_count(self):
        for wizard in self:
            wizard.space_count = len(wizard._get_spaces()) if wizard.project_id else 0

    def action_generate(self):
        self.ensure_one()
        spaces = self._get_spaces()
        if not spaces:
            raise UserError(self.env._('Todos los ambientes de la selección ya tienen metrado.'))
        measurements = self.env['construction.measurement'].create(
            [{'task_id': space.id} for space in spaces])
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Medidas por cargar'),
            'res_model': 'construction.measurement.line',
            'view_mode': 'list',
            'views': [(self.env.ref('al_construction_planner.construction_measurement_line_view_list').id,
                       'list')],
            'domain': [('measurement_id', 'in', measurements.ids)],
            'context': {'group_by': ['floor_task_id', 'task_id']},
        }

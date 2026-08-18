# -*- coding: utf-8 -*-
"""Línea base: foto inmutable de la planificación de un proyecto.

Sirve para comparar «lo que se planificó» contra «lo que hay ahora»: cada línea
guarda las fechas y el avance de una tarea en el momento de la captura. Las
líneas no se pueden modificar; si el plan cambia, se toma otra línea base.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GanttBaseline(models.Model):
    _name = 'al.gantt.baseline'
    _description = 'Gantt — línea base'
    _order = 'date_captured desc, id desc'

    name = fields.Char(string='Nombre', required=True)
    project_id = fields.Many2one(
        'project.project', string='Proyecto', required=True,
        ondelete='cascade', index=True,
    )
    date_captured = fields.Datetime(
        string='Capturada el', required=True, readonly=True,
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        'res.users', string='Capturada por', readonly=True,
        default=lambda self: self.env.user,
    )
    line_ids = fields.One2many(
        'al.gantt.baseline.line', 'baseline_id', string='Líneas', readonly=True,
    )
    task_count = fields.Integer(string='Tareas', compute='_compute_task_count', store=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)

    @api.depends('line_ids')
    def _compute_task_count(self):
        counts = dict(self.env['al.gantt.baseline.line']._read_group(
            [('baseline_id', 'in', self.ids)], groupby=['baseline_id'], aggregates=['__count'],
        ))
        for baseline in self:
            baseline.task_count = counts.get(baseline, 0)


class GanttBaselineLine(models.Model):
    _name = 'al.gantt.baseline.line'
    _description = 'Gantt — línea base (tarea)'

    baseline_id = fields.Many2one(
        'al.gantt.baseline', string='Línea base', required=True,
        ondelete='cascade', index=True,
    )
    task_id = fields.Many2one(
        'project.task', string='Tarea', required=True, ondelete='cascade', index=True,
    )
    date_start = fields.Datetime(string='Inicio planificado', readonly=True)
    date_end = fields.Datetime(string='Fin planificado', readonly=True)
    progress = fields.Float(string='Avance', readonly=True)

    _baseline_task_uniq = models.Constraint(
        'UNIQUE(baseline_id, task_id)',
        'Una tarea solo puede figurar una vez en la misma línea base.',
    )

    def write(self, values):
        """Inmutable: una línea base que se puede retocar no sirve de referencia."""
        raise UserError(_(
            "Las líneas de una línea base no se pueden modificar. "
            "Capture una nueva si el plan cambió."
        ))


class GanttBaselineService(models.AbstractModel):
    _inherit = 'al.gantt.data'

    @api.model
    def create_baseline(self, project_ids, name=None):
        """Captura una línea base por proyecto con las tareas que tienen fecha."""
        self._check_gantt_access()
        field_map = self.env['al.gantt.field.map'].get_map()
        if not field_map['date_end']:
            raise UserError(_("No hay campo de fechas configurado: no se puede capturar una línea base."))

        projects = self.env['project.project'].browse(list(project_ids or [])).exists()
        if not projects:
            raise UserError(_("Seleccione al menos un proyecto."))
        projects.check_access('read')

        created = []
        for project in projects:
            tasks = self.env['project.task'].search([
                ('project_id', '=', project.id),
                (field_map['date_end'], '!=', False),
            ])
            baseline = self.env['al.gantt.baseline'].create({
                'name': name or _("Línea base %s", fields.Datetime.now().strftime('%d/%m/%Y %H:%M')),
                'project_id': project.id,
            })
            self.env['al.gantt.baseline.line'].create([{
                'baseline_id': baseline.id,
                'task_id': task.id,
                'date_start': task[field_map['date_start']] if field_map['date_start'] else False,
                'date_end': task[field_map['date_end']],
                'progress': task[field_map['progress']] if field_map['progress'] else 0.0,
            } for task in tasks])
            created.append({
                'id': baseline.id,
                'name': baseline.name,
                'project_id': project.id,
                'date': self._iso(baseline.date_captured),
                'task_count': len(tasks),
            })
        return {'ok': True, 'baselines': created}

    @api.model
    def _read_baselines(self, project_ids):
        """Líneas base disponibles para los proyectos consultados."""
        records = self.env['al.gantt.baseline'].search_read(
            [('project_id', 'in', list(project_ids))],
            ['id', 'name', 'project_id', 'date_captured', 'task_count'],
        )
        return [{
            'id': record['id'],
            'name': record['name'],
            'project_id': self._m2o(record['project_id'])[0],
            'date': self._iso(record['date_captured']),
            'task_count': record['task_count'],
        } for record in records]

    @api.model
    def _apply_baseline(self, tasks, baseline_id):
        """Añade a cada tarea sus fechas de línea base y el desvío en días."""
        for task in tasks:
            task['baseline_start'] = None
            task['baseline_end'] = None
            task['baseline_variance_days'] = None
        baseline = self.env['al.gantt.baseline'].browse(int(baseline_id)).exists()
        if not baseline:
            return {'applied': False}

        lines = self.env['al.gantt.baseline.line'].search_read(
            [('baseline_id', '=', baseline.id)], ['task_id', 'date_start', 'date_end'],
        )
        by_task = {self._m2o(line['task_id'])[0]: line for line in lines}
        for task in tasks:
            line = by_task.get(task['id'])
            if not line:
                continue
            task['baseline_start'] = self._iso(line['date_start'])
            task['baseline_end'] = self._iso(line['date_end'])
            if line['date_end'] and task['end']:
                delta = self._from_iso(task['end']) - line['date_end']
                task['baseline_variance_days'] = round(delta.total_seconds() / 86400.0, 2)
        return {'applied': True, 'id': baseline.id, 'name': baseline.name}

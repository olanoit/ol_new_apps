# -*- coding: utf-8 -*-
"""W-08 «Cambiar fechas» (F-08): desplaza n días, o lleva a una fecha nueva,
la selección del árbol (y las etapas del cronograma de sus ambientes). Con todas las etapas mueve las tareas (y su Gantt) y
recalcula la fecha de necesidad de sus líneas; con algunas etapas solo
desplaza la fecha de necesidad de las líneas de esas etapas. Avisa a
Logística, con una actividad en cada documento, de los requerimientos y OC
abiertos cuya fecha queda desfasada con la nueva necesidad."""
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from .plan_generate_wizard import STAGE_FIELDS


class ConstructionPlanRescheduleWizard(models.TransientModel):
    _name = 'construction.plan.reschedule.wizard'
    _inherit = 'construction.plan.supply.mixin'
    _description = 'Cambiar fechas desde el plan'

    mode = fields.Selection(
        [('shift', 'Desplazar días'), ('date', 'Fecha nueva')], string='Cambio',
        default='shift', required=True)
    days = fields.Integer(string='Días', default=7, help='Negativo: adelanta.')
    date_new = fields.Date(
        string='Nuevo inicio', help='Nuevo inicio de la tarea más temprana de la selección.')
    date_current = fields.Date(
        string='Inicio actual', compute='_compute_preview', store=True,
        help='Inicio de la tarea más temprana de la selección (o la fecha de necesidad más '
             'temprana, si no tiene fechas).')
    delta_days = fields.Integer(
        string='Desplazamiento (días)', compute='_compute_preview', store=True)
    move_tasks = fields.Boolean(
        string='Mueve las tareas', compute='_compute_preview', store=True,
        help='Solo con todas las etapas: las tareas no tienen fechas por etapa.')
    task_count = fields.Integer(string='Nº de tareas', compute='_compute_preview', store=True)
    line_ids = fields.One2many(
        'construction.plan.reschedule.wizard.line', 'wizard_id', string='Líneas afectadas',
        compute='_compute_preview', store=True)

    def _get_date_fields(self):
        field_map = self.env['al.gantt.field.map'].get_map()
        Task = self.env['project.task']
        return [name for name in (field_map.get('date_start'), field_map.get('date_end'))
                if name and name in Task._fields]

    def _get_tasks(self):
        """Tareas con nivel de la selección y sus descendientes."""
        self.ensure_one()
        tasks = self._get_selected_tasks()
        if tasks is None:
            tasks = self.env['project.task'].search([
                ('project_id', '=', self.plan_id.project_id.id),
                ('construction_level', '!=', False)])
        return tasks

    def _get_affected_lines(self):
        self.ensure_one()
        return self._get_selected_lines()

    def _get_reference_date(self, tasks, lines):
        start_field = self.env['al.gantt.field.map'].get_map().get('date_start')
        starts = [fields.Date.to_date(task[start_field]) for task in tasks
                  if start_field and task[start_field]]
        if starts:
            return min(starts)
        needs = [line.date_needed for line in lines if line.date_needed]
        return min(needs) if needs else False

    @api.depends('plan_id', 'task_ids', 'whole_project', 'mode', 'days', 'date_new',
                 *STAGE_FIELDS.values())
    def _compute_preview(self):
        for wizard in self:
            commands = [Command.clear()]
            wizard.date_current = False
            wizard.delta_days = 0
            wizard.task_count = 0
            wizard.move_tasks = all(wizard[field] for field in STAGE_FIELDS.values())
            if not wizard.plan_id:
                wizard.line_ids = commands
                continue
            tasks = wizard._get_tasks()
            lines = wizard._get_affected_lines()
            current = wizard._get_reference_date(tasks, lines)
            wizard.date_current = current
            delta = wizard._get_delta(current)
            wizard.delta_days = delta
            wizard.task_count = len(tasks) if wizard.move_tasks else 0
            for line in lines:
                commands.append(Command.create({
                    'plan_line_id': line.id,
                    'date_old': line.date_needed,
                    'date_new': line.date_needed + timedelta(days=delta)
                    if line.date_needed else False,
                }))
            wizard.line_ids = commands

    def _get_delta(self, current):
        self.ensure_one()
        if self.mode == 'shift':
            return self.days or 0
        if self.date_new and current:
            return (self.date_new - current).days
        return 0

    # ------------------------------------------------------------------
    # Aplicar
    # ------------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_supply_wizard_state()
        if self.mode == 'date' and not self.date_new:
            raise UserError(self.env._('Indique la fecha nueva.'))
        tasks = self._get_tasks()
        lines = self._get_affected_lines()
        delta = self._get_delta(self._get_reference_date(tasks, lines))
        if not delta:
            raise UserError(self.env._('Las fechas no cambian: indique los días o la fecha nueva.'))
        if not lines and not (self.move_tasks and tasks):
            raise UserError(self.env._('La selección no tiene tareas ni líneas que mover.'))
        shift = timedelta(days=delta)
        start_field = self.env['al.gantt.field.map'].get_map().get('date_start')
        dated = lines.browse()
        if self.move_tasks:
            for name in self._get_date_fields():
                for task in tasks.filtered(name):
                    task[name] = task[name] + shift
            # La fecha de necesidad de las líneas cuya tarea tiene inicio se
            # recalcula desde el nuevo inicio; las demás se desplazan igual.
            if start_field:
                dated = lines.filtered(lambda l: l.task_id and l.task_id[start_field])
        defaults = dated._get_default_date_needed()
        news = {line: defaults.get(line) or (line.date_needed and line.date_needed + shift)
                for line in lines}
        for new, same in lines.grouped(lambda line: news[line]).items():
            same.write({'date_needed': new})
        # Las barras del cronograma (P-15) de las etapas elegidas se mueven
        # igual; sus líneas ya se movieron arriba.
        spaces = lines.space_task_id | tasks.filtered(lambda t: t.construction_level == 'space')
        stages = self.env['construction.space.stage'].search([
            ('space_task_id', 'in', spaces.ids), ('stage', 'in', self._get_stages())])
        for stage in stages:
            stage.with_context(construction_stage_keep_lines=True).write({
                'date_start': stage.date_start + shift, 'date_end': stage.date_end + shift})
        notified = self._notify_logistics(lines, delta)
        body = self.env._(
            'Fechas cambiadas %(delta)s días (%(selection)s): %(tasks)s tareas y %(lines)s '
            'líneas; avisos a Logística: %(docs)s.', delta=delta,
            selection=self._get_selection_label(),
            tasks=len(tasks) if self.move_tasks else 0, lines=len(lines),
            docs=', '.join(notified) or '—')
        plan.message_post(body=body)
        return {'type': 'ir.actions.act_window_close'}

    # ------------------------------------------------------------------
    # Avisos a Logística
    # ------------------------------------------------------------------
    def _notify_logistics(self, lines, delta):
        """Ver ``construction.resource.plan._notify_logistics`` (lo comparte
        con el arrastre de etapas en el cronograma)."""
        return self.plan_id._notify_logistics(lines, delta)


class ConstructionPlanRescheduleWizardLine(models.TransientModel):
    _name = 'construction.plan.reschedule.wizard.line'
    _description = 'Línea afectada por el cambio de fechas'

    wizard_id = fields.Many2one(
        'construction.plan.reschedule.wizard', string='Asistente', required=True,
        ondelete='cascade')
    plan_line_id = fields.Many2one('construction.resource.plan.line', string='Línea del plan')
    apartment_task_id = fields.Many2one(
        related='plan_line_id.apartment_task_id', string='Departamento')
    task_id = fields.Many2one(related='plan_line_id.task_id', string='Nivel')
    stage = fields.Selection(related='plan_line_id.stage', string='Etapa')
    resource_type = fields.Selection(
        related='plan_line_id.resource_type', string='Tipo de recurso')
    resource_name = fields.Char(related='plan_line_id.resource_name', string='Recurso')
    date_old = fields.Date(string='Necesidad actual')
    date_new = fields.Date(string='Nueva necesidad')

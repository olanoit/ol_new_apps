# -*- coding: utf-8 -*-
"""W-06 «Asignar cuadrilla» (personal propio, F-07): turnos de la cuadrilla
por recurso y semana con la tarea del nivel y la línea del plan. El capataz
registra después las horas en la hoja de horas de esa tarea: son el ejecutado
y el real de la línea; los turnos aún sin horas, su comprometido."""
from datetime import datetime, time, timedelta

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

# Horario de referencia del turno semanal (hora local): las horas asignadas
# se escriben aparte y son las que cuentan.
SLOT_START = time(8, 0)
SLOT_END = time(17, 0)


class ConstructionPlanCrewWizard(models.TransientModel):
    _name = 'construction.plan.crew.wizard'
    _inherit = 'construction.plan.supply.mixin'
    _description = 'Asignar cuadrilla desde el plan'

    role_id = fields.Many2one(
        'planning.role', string='Rol',
        help='Rol de las líneas de personal propio; los recursos lo reciben si no lo tienen, '
             'para que sus horas cuenten en la línea.')
    resource_ids = fields.Many2many(
        'resource.resource', string='Recursos', check_company=True,
        domain="[('resource_type', '=', 'user'), ('company_id', 'in', (company_id, False))]",
        help='Obreros de la cuadrilla (empleados con su costo hora).')
    member_ids = fields.One2many(
        'construction.plan.crew.wizard.member', 'wizard_id', string='Cuadrilla por rol',
        help='Composición de la cuadrilla (v1.7, M17-11): cada integrante con su rol va a las '
             'líneas de personal propio de ese rol. Vacía: los recursos con el rol de arriba.')
    date_start = fields.Date(
        string='Primera semana', compute='_compute_date_start', store=True, readonly=False,
        precompute=True, required=True, help='Se ajusta al inicio de la semana de la obra.')
    weeks = fields.Integer(string='Semanas', default=1, required=True)
    hours_per_week = fields.Float(
        string='Horas por semana', default=48.0, required=True,
        help='De cada recurso; se reparten entre las líneas de la selección según su monto '
             'planificado.')
    line_ids = fields.One2many(
        'construction.plan.crew.wizard.line', 'wizard_id', string='Vista previa',
        compute='_compute_line_ids', store=True)
    plan_line_count = fields.Integer(
        string='Nº de líneas del plan', compute='_compute_line_ids', store=True)
    hours_total = fields.Float(string='Horas', compute='_compute_line_ids', store=True)
    note = fields.Text(string='Avisos', compute='_compute_line_ids', store=True)

    @api.depends('plan_id')
    def _compute_date_start(self):
        today = fields.Date.context_today(self)
        for wizard in self:
            project = wizard.plan_id.project_id
            wizard.date_start = project._construction_period(today)[0] if project else today

    def _get_candidate_lines(self, role=None):
        """Líneas de personal propio de la selección con el rol (o sin rol)."""
        self.ensure_one()
        role = role or self.role_id
        lines = self._get_selected_lines([('resource_type', '=', 'labor')])
        return lines.filtered(lambda l: not l._get_role() or l._get_role() == role)

    def _get_members(self):
        """[(recurso, rol)] de la cuadrilla: su composición por rol o los
        recursos con el rol del asistente."""
        self.ensure_one()
        if self.member_ids:
            return [(member.resource_id, member.role_id) for member in self.member_ids
                    if member.resource_id and member.role_id]
        return [(resource, self.role_id) for resource in self.resource_ids] \
            if self.role_id else []

    def _get_weeks(self):
        self.ensure_one()
        project = self.plan_id.project_id
        start = project._construction_period(self.date_start)[0] if project else self.date_start
        return [start + timedelta(weeks=week) for week in range(max(self.weeks, 0))]

    @api.depends('plan_id', 'task_ids', 'whole_project', 'role_id', 'resource_ids',
                 'member_ids.role_id', 'member_ids.resource_id',
                 'date_start', 'weeks', 'hours_per_week', 'stage_ids')
    def _compute_line_ids(self):
        for wizard in self:
            commands, notes = [Command.clear()], []
            members = wizard._get_members() if wizard.plan_id else []
            # sudo: el empleado del recurso es de RR. HH.; solo se mira si
            # existe para avisar.
            resources_sudo = self.env['resource.resource'].union(
                *(resource for resource, _role in members)).sudo()
            no_employee = resources_sudo.filtered(lambda r: not r.employee_id).sudo(False)
            if no_employee:
                notes.append(self.env._(
                    'Sin empleado (no registran horas ni tienen costo hora): %s.',
                    ', '.join(no_employee.mapped('name'))))
            all_lines = self.env['construction.resource.plan.line']
            hours_total = 0.0
            for role in dict.fromkeys(role for _resource, role in members):
                lines = wizard._get_candidate_lines(role)
                all_lines |= lines
                if not lines:
                    notes.append(self.env._(
                        'La selección no tiene líneas de personal propio del rol %s.',
                        role.display_name))
                    continue
                if not wizard.date_start or wizard.hours_per_week <= 0:
                    continue
                total_amount = sum(lines.mapped('amount_planned'))
                shares = {line: (line.amount_planned / total_amount if total_amount
                                 else 1.0 / len(lines)) for line in lines}
                for resource in [r for r, member_role in members
                                 if member_role == role and r not in no_employee]:
                    for week in wizard._get_weeks():
                        for line, share in shares.items():
                            hours = round(wizard.hours_per_week * share, 2)
                            if hours <= 0:
                                continue
                            hours_total += hours
                            commands.append(Command.create({
                                'resource_id': resource.id,
                                'role_id': role.id,
                                'week_start': week,
                                'plan_line_id': line.id,
                                'hours': hours,
                            }))
            wizard.line_ids = commands
            wizard.plan_line_count = len(all_lines)
            wizard.hours_total = hours_total
            wizard.note = '\n'.join(notes) or False

    # ------------------------------------------------------------------
    # Crear los turnos
    # ------------------------------------------------------------------
    def _slot_datetimes(self, week_start):
        """Inicio y fin del turno semanal en UTC (hora local del usuario)."""
        tz = pytz.timezone(self.env.user.tz or self.env.context.get('tz') or 'UTC')

        def to_utc(day, moment):
            local = tz.localize(datetime.combine(day, moment))
            return local.astimezone(pytz.utc).replace(tzinfo=None)

        return to_utc(week_start, SLOT_START), to_utc(week_start + timedelta(days=6), SLOT_END)

    def action_assign(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_supply_wizard_state()
        if self.weeks <= 0 or self.hours_per_week <= 0:
            raise UserError(self.env._('Indique las semanas y las horas por semana.'))
        rows = self.line_ids.filtered(lambda r: r.hours > 0)
        if not rows:
            raise UserError(self.env._(
                'No hay turnos que crear: elija recursos con empleado y una selección con '
                'líneas de personal propio del rol.'))
        hour = self.env.ref('uom.product_uom_hour')
        # sudo: los turnos y los roles de los recursos son de Planificación;
        # la cuadrilla la asigna Proyectos desde el plan, sin ser
        # administrador de turnos. Los valores salen de la vista previa.
        for row in rows:
            resource_sudo = row.resource_id.sudo()
            if row.role_id not in resource_sudo.role_ids:
                resource_sudo.write({'role_ids': [Command.link(row.role_id.id)]})
        slot_values = []
        for row in rows:
            start, end = self._slot_datetimes(row.week_start)
            line = row.plan_line_id
            slot_values.append({
                'resource_id': row.resource_id.id,
                'role_id': row.role_id.id,
                'project_id': plan.project_id.id,
                'company_id': plan.company_id.id,
                'start_datetime': start,
                'end_datetime': end,
                'allocated_hours': row.hours,
                'name': '%s · %s' % (line.resource_name or '', line.task_id.display_name or ''),
                'construction_task_id': line.task_id.id,
                'construction_plan_line_id': line.id,
            })
        slots_sudo = self.env['planning.slot'].sudo().create(slot_values)
        allocation_values = []
        for row, slot_sudo in zip(rows, slots_sudo):
            line = row.plan_line_id
            # Lo pedido del personal propio son horas de turnos: en la unidad
            # de la línea si se mide en horas; si se paga por driver, el turno
            # solo compromete costo.
            qty = hour._compute_quantity(row.hours, line.product_uom_id) \
                if line._is_hour_based() else 0.0
            allocation_values.append({
                'plan_line_id': line.id,
                'kind': 'planning_slot',
                'slot_id': slot_sudo.id,
                'qty_allocated': qty,
            })
        self.env['construction.resource.plan.allocation'].create(allocation_values)
        plan._mark_in_progress()
        plan.message_post(body=self.env._(
            'Cuadrilla %(role)s asignada (%(selection)s): %(resources)s, %(weeks)s semanas, '
            '%(count)s turnos y %(hours)s horas.',
            role=', '.join(rows.role_id.mapped('display_name')),
            selection=self._get_selection_label(),
            resources=', '.join(rows.resource_id.mapped('name')), weeks=self.weeks,
            count=len(slots_sudo), hours=round(sum(rows.mapped('hours')), 2)))
        if slots_sudo.sudo(False).has_access('read'):
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._('Turnos de la cuadrilla'),
                'res_model': 'planning.slot',
                'view_mode': 'list,form',
                'domain': [('id', 'in', slots_sudo.ids)],
                'context': {'create': False},
            }
        return {'type': 'ir.actions.act_window_close'}


class ConstructionPlanCrewWizardLine(models.TransientModel):
    _name = 'construction.plan.crew.wizard.line'
    _description = 'Turno de la cuadrilla'
    _order = 'week_start, resource_id, id'

    wizard_id = fields.Many2one(
        'construction.plan.crew.wizard', string='Asistente', required=True, ondelete='cascade')
    resource_id = fields.Many2one('resource.resource', string='Recurso', required=True)
    role_id = fields.Many2one('planning.role', string='Rol')
    week_start = fields.Date(string='Semana', required=True)
    plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', required=True)
    apartment_task_id = fields.Many2one(
        related='plan_line_id.apartment_task_id', string='Departamento')
    task_id = fields.Many2one(related='plan_line_id.task_id', string='Nivel')
    activity_id = fields.Many2one(related='plan_line_id.activity_id', string='Actividad')
    hours = fields.Float(string='Horas', digits=(16, 2))


class ConstructionPlanCrewWizardMember(models.TransientModel):
    _name = 'construction.plan.crew.wizard.member'
    _description = 'Integrante de la cuadrilla'

    wizard_id = fields.Many2one(
        'construction.plan.crew.wizard', string='Asistente', required=True, ondelete='cascade')
    role_id = fields.Many2one('planning.role', string='Rol', required=True)
    resource_id = fields.Many2one(
        'resource.resource', string='Recurso', required=True,
        domain="[('resource_type', '=', 'user')]")

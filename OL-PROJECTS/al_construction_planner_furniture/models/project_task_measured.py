# -*- coding: utf-8 -*-
"""Ambiente medido (paquete 1.9, M19-06).

En mobiliario, el supervisor solo marca el ambiente como medido, con la fecha
y un archivo (plano, foto o exportación de SketchUp): no escribe cantidades
ni pasa por aprobación. Optimización ve los ambientes medidos que aún no
están en una orden de fabricación; las cantidades reales llegan con la carga
del despiece a la orden."""
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

SUPERVISOR_GROUP = 'al_construction_planner.group_planner_user'


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_measured = fields.Boolean(
        string='Medido', readonly=True, copy=False, tracking=True,
        help='El supervisor midió el ambiente: Optimización puede preparar su orden.')
    construction_measured_date = fields.Date(
        string='Fecha de medición', readonly=True, copy=False, tracking=True)
    construction_measured_user_id = fields.Many2one(
        'res.users', string='Medido por', readonly=True, copy=False)
    construction_measured_attachment_ids = fields.Many2many(
        'ir.attachment', 'project_task_construction_measured_attachment_rel', 'task_id',
        'attachment_id', string='Archivos de la medición', readonly=True, copy=False)
    # Mismo vínculo que mrp.production.construction_space_task_ids.
    construction_production_ids = fields.Many2many(
        'mrp.production', 'mrp_production_construction_space_rel', 'task_id', 'production_id',
        string='Órdenes de fabricación', readonly=True, copy=False)
    construction_measured_pending = fields.Boolean(
        string='Por cargar a una orden', compute='_compute_construction_measured_pending',
        search='_search_construction_measured_pending', compute_sudo=True,
        help='Medido y todavía sin orden de fabricación.')

    @api.depends('construction_measured', 'construction_production_ids.state')
    def _compute_construction_measured_pending(self):
        for task in self:
            task.construction_measured_pending = task.construction_measured and not any(
                state != 'cancel' for state in task.construction_production_ids.mapped('state'))

    def _search_construction_measured_pending(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        # El supervisor no lee Fabricación: solo se pregunta si el ambiente
        # ya está en una orden no cancelada.
        busy_sudo = self.env['mrp.production'].sudo().search(
            [('state', '!=', 'cancel'), ('construction_space_task_ids', '!=', False)])
        busy_ids = busy_sudo.construction_space_task_ids.ids
        domain = [('construction_measured', '=', True), ('id', 'not in', busy_ids)]
        if (operator == '=') == value:
            return domain
        return ['!', '&'] + domain

    # Etapa actual del ambiente (paquete 1.15, M115-04): «Medido» sale de esta
    # marca y su cambio recalcula la etapa actual.
    def _construction_space_measured(self):
        self.ensure_one()
        return bool(self.construction_measured)

    @api.model
    def _construction_current_stage_trigger_fields(self):
        return super()._construction_current_stage_trigger_fields() | {'construction_measured'}

    def action_construction_mark_measured(self):
        self._construction_check_supervisor()
        spaces = self.filtered(lambda t: t.construction_level == 'space')
        if not spaces:
            raise UserError(self.env._('Solo un ambiente se marca como medido.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Marcar como medido'),
            'res_model': 'construction.space.measured.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_ids': spaces.ids},
        }

    def _construction_check_supervisor(self):
        if not self.env.user.has_group(SUPERVISOR_GROUP):
            raise AccessError(self.env._('Solo el personal de obra marca un ambiente como medido.'))

    def action_construction_unmark_measured(self):
        self._construction_check_supervisor()
        busy = self.filtered(lambda t: t.construction_measured and not
                             t.construction_measured_pending)
        if busy:
            raise UserError(self.env._(
                'Ya tiene orden de fabricación: %s.', ', '.join(busy.mapped('display_name'))))
        self.check_access('read')
        # Igual que al marcarlo: solo la marca de la medición.
        tasks_sudo = self.sudo()
        tasks_sudo.write({'construction_measured': False, 'construction_measured_date': False,
                          'construction_measured_user_id': False})
        for task in tasks_sudo:
            task.message_post(body=self.env._('Medición desmarcada.'))
        return True


class ResCompany(models.Model):
    """Nombres de los estados del ambiente que no son etapas (paquete 1.16,
    M116-02): los usa la etapa actual de cada ambiente del Cronograma
    (M115-04). «Medido» y no «Metrado»: en construcción por partidas el
    metrado es la medición con aprobación."""
    _inherit = 'res.company'

    construction_state_pending_label = fields.Char(
        string='Estado sin empezar', default='Pendiente', translate=True)
    construction_state_measured_label = fields.Char(
        string='Estado del ambiente medido', default='Medido', translate=True)
    construction_state_delivered_label = fields.Char(
        string='Estado del ambiente entregado', default='Entregado', translate=True)

    def _construction_space_state_names(self):
        names = super()._construction_space_state_names()
        return {'pending': self.construction_state_pending_label or names['pending'],
                'measured': self.construction_state_measured_label or names['measured'],
                'delivered': self.construction_state_delivered_label or names['delivered']}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_state_pending_label = fields.Char(
        related='company_id.construction_state_pending_label', readonly=False)
    construction_state_measured_label = fields.Char(
        related='company_id.construction_state_measured_label', readonly=False)
    construction_state_delivered_label = fields.Char(
        related='company_id.construction_state_delivered_label', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _construction_space_state_labels(self):
        """{'pending', 'measured', 'delivered': nombre} de los estados del
        ambiente que no son etapas, o vacío si el perfil de la obra no los
        usa (M116-02). Los usa el perfil que mide sus ambientes (función
        «Metrado» del perfil): una obra sin perfil es de mobiliario."""
        self.ensure_one()
        profile = self.construction_profile_id
        if profile and not profile.feature_measurement:
            return {}
        company = self.company_id or self.env.company
        return {'pending': company.construction_state_pending_label or self.env._('Pendiente'),
                'measured': company.construction_state_measured_label or self.env._('Medido'),
                'delivered': company.construction_state_delivered_label
                or self.env._('Entregado')}

# -*- coding: utf-8 -*-
"""W-07 «Registrar avance» (P-06): unidades de driver de una actividad en los
módulos o ambientes de la selección (donde cuelgan sus líneas), con fotos.
Por defecto propone el saldo; no acepta más que el saldo más la tolerancia
del plan."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from ..models.common import DRIVER_TYPES


class ConstructionPlanProgressWizard(models.TransientModel):
    _name = 'construction.plan.progress.wizard'
    _inherit = 'construction.plan.supply.mixin'
    _description = 'Registrar avance desde el plan'

    available_activity_ids = fields.Many2many(
        'construction.labor.activity', string='Actividades de la selección',
        compute='_compute_available_activity_ids', check_company=True)
    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad', required=True, check_company=True,
        domain="[('id', 'in', available_activity_ids)]")
    partner_id = fields.Many2one(
        'res.partner', string='Contrata', check_company=True,
        help='Vacía: todas las líneas de la actividad, tengan o no contrata.')
    date = fields.Date(string='Fecha de ejecución', required=True,
                       default=fields.Date.context_today)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_plan_progress_wizard_attachment_rel', 'wizard_id',
        'attachment_id', string='Fotos', check_company=True)
    line_ids = fields.One2many(
        'construction.plan.progress.wizard.line', 'wizard_id', string='Avance',
        compute='_compute_line_ids', store=True, readonly=False)
    qty_total = fields.Float(
        string='Unidades a reportar', compute='_compute_qty_total', digits='Product Unit')
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad')

    def _get_driver_lines(self, activity=None):
        self.ensure_one()
        domain = [('resource_type', 'in', DRIVER_TYPES), ('activity_id', '!=', False),
                  ('task_id', '!=', False)]
        if activity:
            domain.append(('activity_id', '=', activity.id))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        return self._get_selected_lines(domain)

    @api.depends('plan_id', 'task_ids', 'whole_project', 'partner_id')
    def _compute_available_activity_ids(self):
        for wizard in self:
            wizard.available_activity_ids = wizard._get_driver_lines().activity_id \
                if wizard.plan_id else False

    @api.depends('plan_id', 'task_ids', 'whole_project', 'activity_id', 'partner_id')
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            if wizard.plan_id and wizard.activity_id:
                for line in wizard._get_driver_lines(wizard.activity_id).sorted(
                        lambda l: (l.floor_task_id.sequence, l.apartment_task_id.name or '',
                                   l.task_id.sequence, l.task_id.name or '', l.id)):
                    balance = wizard._get_balance(line)
                    commands.append(Command.create({
                        'plan_line_id': line.id,
                        'qty_planned': line.qty_planned,
                        'qty_executed': line.qty_executed,
                        'qty_pending': line._get_reported_qty(),
                        'qty_balance': balance,
                        'qty_report': max(balance, 0.0),
                    }))
            wizard.line_ids = commands

    @staticmethod
    def _get_balance(line):
        """Presupuestado menos lo reportado o validado (lo rechazado no cuenta)."""
        return line.qty_planned - line.qty_executed - line._get_reported_qty()

    @api.depends('line_ids.qty_report')
    def _compute_qty_total(self):
        for wizard in self:
            wizard.qty_total = sum(wizard.line_ids.mapped('qty_report'))

    def action_register(self):
        self.ensure_one()
        if self.plan_id.state not in ('approved', 'in_progress'):
            raise UserError(self.env._('El avance se reporta sobre el plan vigente.'))
        if not self.attachment_ids:
            raise UserError(self.env._('Adjunte al menos una foto del avance.'))
        rows = self.line_ids.filtered(
            lambda r: r.plan_line_id.product_uom_id.compare(r.qty_report, 0.0) > 0)
        if not rows:
            raise UserError(self.env._('No hay unidades que reportar.'))
        for row in rows:
            line = row.plan_line_id
            limit = self._get_balance(line) + line._get_tolerance_qty()
            if line.product_uom_id.compare(row.qty_report, limit) > 0:
                raise UserError(self.env._(
                    '%(task)s: se reportan %(qty)s %(uom)s y el saldo (con la tolerancia del '
                    'plan) es %(limit)s.', task=line.task_id.display_name,
                    qty=round(row.qty_report, 2), uom=line.product_uom_id.name,
                    limit=round(max(limit, 0.0), 2)))
        Progress = self.env['construction.task.progress']
        progresses = Progress
        for row in rows:
            line = row.plan_line_id
            photos = self._copy_photos()
            progress = Progress.create({
                'task_id': line.task_id.id,
                'activity_id': line.activity_id.id,
                'plan_line_id': line.id,
                'date': self.date,
                'qty': row.qty_report,
                'attachment_ids': [Command.set(photos.ids)],
            })
            photos.write({'res_id': progress.id})
            progresses |= progress
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Avances registrados'),
            'res_model': 'construction.task.progress',
            'view_mode': 'list,form',
            'domain': [('id', 'in', progresses.ids)],
            'context': {'create': False},
        }

    def _copy_photos(self):
        """Copia de las fotos para cada avance (cada uno es dueño de las suyas;
        el archivo se guarda una sola vez en el almacén de adjuntos)."""
        return self.attachment_ids.copy({'res_model': 'construction.task.progress', 'res_id': 0})


class ConstructionPlanProgressWizardLine(models.TransientModel):
    _name = 'construction.plan.progress.wizard.line'
    _description = 'Fila del registro de avance'

    wizard_id = fields.Many2one(
        'construction.plan.progress.wizard', string='Asistente', required=True,
        ondelete='cascade')
    plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', required=True)
    task_id = fields.Many2one(related='plan_line_id.task_id', string='Módulo o ambiente')
    apartment_task_id = fields.Many2one(
        related='plan_line_id.apartment_task_id', string='Departamento')
    typology_id = fields.Many2one(related='plan_line_id.typology_id', string='Tipología')
    partner_id = fields.Many2one(related='plan_line_id.partner_id', string='Contrata')
    uom_id = fields.Many2one(related='plan_line_id.product_uom_id', string='Unidad')
    qty_planned = fields.Float(string='Presupuestado', digits='Product Unit')
    qty_executed = fields.Float(string='Acumulado', digits='Product Unit')
    qty_pending = fields.Float(
        string='Por validar', digits='Product Unit', help='Reportado y aún no validado.')
    qty_balance = fields.Float(string='Saldo', digits='Product Unit')
    qty_report = fields.Float(string='Reportar hoy', digits='Product Unit')
    progress_pct = fields.Float(string='Avance resultante', compute='_compute_progress_pct')

    @api.depends('qty_report', 'qty_executed', 'qty_pending', 'qty_planned')
    def _compute_progress_pct(self):
        for row in self:
            done = row.qty_executed + row.qty_pending + row.qty_report
            row.progress_pct = min(done / row.qty_planned, 1.0) if row.qty_planned else 0.0

# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

from ..models.construction_resource_plan import DRAFT_STATES, OPEN_STATES

# Campos de cabecera que la versión nueva hereda de la vigente.
HEADER_FIELDS = (
    'project_id', 'company_id', 'user_id', 'date_start', 'date_end', 'exceed_policy',
    'exceed_tolerance', 'lead_days_material', 'lead_days_contract', 'lead_days_production',
)


class ConstructionPlanReplanWizard(models.TransientModel):
    """Replanificar (W-09): versión nueva en borrador del plan vigente. La
    vigente sigue en uso hasta que se apruebe la nueva."""
    _name = 'construction.plan.replan.wizard'
    _description = 'Nueva versión del plan de recursos'

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan vigente', required=True, readonly=True)
    reason = fields.Text(string='Motivo', required=True)
    mode = fields.Selection(
        [('all', 'Copiar todo'), ('remaining', 'Solo saldos')],
        string='Qué copiar', required=True, default='all',
        help='«Solo saldos» copia en cada línea lo que falta pedir o ejecutar, y omite las '
             'líneas ya cubiertas.')

    def action_create_version(self):
        self.ensure_one()
        plan = self.plan_id
        if plan.state not in OPEN_STATES:
            raise UserError(self.env._('Solo se replanifica el plan vigente de la obra.'))
        if not (self.reason or '').strip():
            raise UserError(self.env._('Indique el motivo de la versión nueva.'))
        pending = plan.search([
            ('project_id', '=', plan.project_id.id), ('state', 'in', DRAFT_STATES)], limit=1)
        if pending:
            raise UserError(self.env._(
                'La obra ya tiene la versión %s en preparación: termínela o cancélela.',
                pending.display_name))
        values = {name: plan[name] for name in HEADER_FIELDS}
        values = plan._convert_to_write(values)
        values.update({'parent_id': plan.id, 'replan_reason': self.reason})
        new_plan = plan.create(values)
        line_values = []
        for line in plan.line_ids.filtered(lambda l: l.line_state != 'cancel'):
            qty = line.qty_planned
            if self.mode == 'remaining':
                qty = line.qty_planned - line._get_consumed_qty()
                if line.product_uom_id.compare(qty, 0) <= 0:
                    continue
            vals = line.copy_data({
                'plan_id': new_plan.id,
                'qty_planned': qty,
                'source': 'replan',
                'source_ref': plan.display_name,
                'previous_line_id': line.id,
                'date_needed': line.date_needed,
                'analytic_distribution': line.analytic_distribution,
            })[0]
            line_values.append(vals)
        self.env['construction.resource.plan.line'].create(line_values)
        plan.message_post(body=self.env._(
            'Versión nueva en preparación: %(plan)s. Motivo: %(reason)s',
            plan=new_plan.display_name, reason=self.reason))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.resource.plan',
            'view_mode': 'form',
            'res_id': new_plan.id,
        }

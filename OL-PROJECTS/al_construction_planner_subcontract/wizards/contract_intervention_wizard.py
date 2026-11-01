# -*- coding: utf-8 -*-
"""«Intervenir contrata» (paquete 3 de CREVAL, CR-20, con I-13 del paquete
1.16): pide la fecha y el motivo, arma la preliquidación por partida y, al
confirmar, baja las líneas intervenidas de la orden a lo ejecutado, libera el
saldo del plan para «Asignar contrata» y retiene el fondo de la orden. No
genera asiento."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import EXEC_APPROVER_GROUPS

from ..models.construction_contract_intervention import INTERVENTION_HOLD


class ConstructionContractInterventionWizard(models.TransientModel):
    _name = 'construction.contract.intervention.wizard'
    _description = 'Intervenir contrata'
    _check_company_auto = True

    purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de contrata', required=True, check_company=True,
        domain="[('construction_is_service_order', '=', True), ('state', '=', 'purchase'), "
               "('construction_closed', '=', False)]")
    company_id = fields.Many2one(related='purchase_order_id.company_id', string='Compañía')
    partner_id = fields.Many2one(related='purchase_order_id.partner_id', string='Contratista')
    project_id = fields.Many2one(related='purchase_order_id.construction_project_id',
                                 string='Obra')
    currency_id = fields.Many2one(related='purchase_order_id.currency_id', string='Moneda')
    date = fields.Date(string='Fecha de la intervención', required=True,
                       default=fields.Date.context_today)
    reason = fields.Text(string='Motivo', required=True)
    line_ids = fields.One2many(
        'construction.contract.intervention.wizard.line', 'wizard_id', string='Preliquidación',
        compute='_compute_line_ids', store=True, readonly=False)
    amount_valued = fields.Monetary(string='Valorizado', compute='_compute_totals',
                                    currency_field='currency_id')
    amount_released = fields.Monetary(string='Comprometido que se libera',
                                      compute='_compute_totals', currency_field='currency_id')
    fund_amount = fields.Monetary(string='Fondo que se retiene', compute='_compute_totals',
                                  currency_field='currency_id')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get('purchase_order_id') and 'purchase_order_id' in fields_list:
            order = self._order_from_selection()
            if order:
                res['purchase_order_id'] = order.id
        return res

    def _selection_tasks(self):
        """Partidas marcadas en el Cronograma (con sus descendientes)."""
        task_ids = [i for i in self.env.context.get('construction_selection_task_ids') or []
                    if i]
        if not task_ids:
            return self.env['project.task']
        return self.env['project.task'].search([('id', 'child_of', task_ids)])

    def _selection_allocations(self):
        tasks = self._selection_tasks()
        if not tasks:
            return self.env['construction.resource.plan.allocation']
        # sudo: se buscan las órdenes de la selección aunque quien interviene
        # no administre compras; solo para saber cuál es.
        return self.env['construction.resource.plan.allocation'].sudo().search([
            ('kind', '=', 'service_order'),
            '|', ('plan_line_id.task_id', 'in', tasks.ids),
            ('plan_line_id.space_task_id', 'in', tasks.ids)]).filtered(
            lambda a: a.state != 'cancel')

    def _order_from_selection(self):
        """Desde el Cronograma: la orden de las partidas marcadas, que debe
        ser una sola."""
        if not self.env.context.get('construction_selection_task_ids'):
            return self.env['purchase.order']
        orders = self._selection_allocations().purchase_line_id.order_id.filtered(
            lambda o: o.state == 'purchase' and not o.construction_closed)
        if not orders:
            raise UserError(self.env._(
                'Las partidas seleccionadas no tienen una orden de contrata en ejecución.'))
        if len(orders) > 1:
            raise UserError(self.env._(
                'Las partidas seleccionadas son de varias órdenes de contrata (%s): intervenga una '
                'a la vez.', ', '.join(orders.mapped('name'))))
        return orders.sudo(False)

    # ------------------------------------------------------------------
    # Preliquidación
    # ------------------------------------------------------------------
    def _validated_by_plan_line(self, order, plan_lines):
        """{línea del plan: avance validado de la contrata} (sin re-trabajo),
        en la unidad de la actividad."""
        if not plan_lines:
            return {}
        Progress = self.env['construction.task.progress'].sudo()
        groups = Progress._read_group(
            order._construction_progress_domain() + [
                ('plan_line_id', 'in', plan_lines.ids), ('is_rework', '=', False)],
            ['plan_line_id'], ['qty_weighted:sum'])
        return {line: qty or 0.0 for line, qty in groups}

    @api.model
    def _task_label(self, po_line, allocations):
        task = po_line.construction_task_id
        if task:
            return task.display_name
        tasks = allocations.plan_line_id.task_id
        return ', '.join(tasks[:5].mapped('display_name')) + (' …' if len(tasks) > 5 else '')

    @api.depends('purchase_order_id')
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            if wizard.purchase_order_id:
                commands += [Command.create(vals) for vals in wizard._prepare_lines()]
            wizard.line_ids = commands

    def _prepare_lines(self):
        self.ensure_one()
        # sudo: quien interviene (ejecución › aprueba) no administra compras;
        # la preliquidación solo lee la orden de la contrata.
        order_sudo = self.purchase_order_id.sudo()
        selected = self._selection_allocations().purchase_line_id
        po_lines = order_sudo.order_line.filtered(
            lambda l: not l.display_type and not l.construction_intervention_line_id
            and l.construction_allocation_ids.filtered(lambda a: a.state != 'cancel'))
        allocations = po_lines.construction_allocation_ids.filtered(lambda a: a.state != 'cancel')
        validated = self._validated_by_plan_line(order_sudo, allocations.plan_line_id)
        rows = []
        for po_line in po_lines:
            line_allocations = po_line.construction_allocation_ids.filtered(
                lambda a: a.state != 'cancel')
            uom = po_line.product_uom_id
            activity = po_line.construction_activity_id
            executed = 0.0
            for plan_line in line_allocations.plan_line_id:
                qty = validated.get(plan_line, 0.0)
                if activity.uom_id and uom and activity.uom_id != uom:
                    qty = activity.uom_id._compute_quantity(qty, uom)
                executed += qty
            qty_new = min(max(po_line.qty_received, executed), po_line.product_qty)
            released = max(po_line.product_qty - qty_new, 0.0)
            rows.append({
                'purchase_line_id': po_line.id,
                'intervene': po_line in selected if selected else True,
                'task_label': self._task_label(po_line, line_allocations),
                'activity_id': activity.id,
                'uom_id': uom.id,
                'price_unit': po_line.price_unit,
                'qty_contracted': po_line.product_qty,
                'qty_validated': executed,
                'qty_valued': po_line.qty_received,
                'qty_new': qty_new,
                'qty_released': released,
            })
        return rows

    @api.depends('line_ids.intervene', 'line_ids.amount_valued', 'line_ids.amount_released',
                 'purchase_order_id')
    def _compute_totals(self):
        for wizard in self:
            chosen = wizard.line_ids.filtered('intervene')
            wizard.amount_valued = sum(chosen.mapped('amount_valued'))
            wizard.amount_released = sum(chosen.mapped('amount_released'))
            # sudo: el fondo es de contabilidad; aquí solo se muestra lo que se
            # retiene.
            funds_sudo = wizard.purchase_order_id.sudo().construction_guarantee_fund_ids
            wizard.fund_amount = sum(funds_sudo.filtered(
                lambda f: f.state != 'paid').mapped('amount_residual'))

    # ------------------------------------------------------------------
    # Confirmar
    # ------------------------------------------------------------------
    def _check_can_intervene(self, rows):
        self.ensure_one()
        if not self.env.user.has_groups(EXEC_APPROVER_GROUPS):
            raise UserError(self.env._('Interviene una contrata quien aprueba la ejecución.'))
        order = self.purchase_order_id
        if not order.construction_is_service_order or order.state != 'purchase' \
                or order.construction_closed:
            raise UserError(self.env._(
                'Se interviene una orden de contrata confirmada y no cerrada.'))
        if not rows:
            raise UserError(self.env._('Marque las partidas que se intervienen.'))
        if not (self.reason or '').strip():
            raise UserError(self.env._('Escriba el motivo de la intervención.'))
        plan_lines = rows.purchase_line_id.construction_allocation_ids.plan_line_id
        # sudo: el avance reportado de la contrata se lee aunque quien
        # interviene no sea quien lo valida.
        pending = self.env['construction.task.progress'].sudo().search([
            ('plan_line_id', 'in', plan_lines.ids), ('state', '=', 'draft'),
            ('partner_id', 'child_of', order.partner_id.commercial_partner_id.id)])
        if pending:
            raise UserError(self.env._(
                'Valide o rechace antes el avance reportado de la contrata en estas partidas: '
                '%s.', ', '.join(pending.mapped('display_name'))))
        later = self.env['construction.task.progress'].sudo().search([
            ('plan_line_id', 'in', plan_lines.ids), ('state', '=', 'validated'),
            ('partner_id', 'child_of', order.partner_id.commercial_partner_id.id),
            ('date', '>', self.date)], order='date desc', limit=1)
        if later:
            raise UserError(self.env._(
                'La contrata tiene avance validado el %s en estas partidas: la intervención no '
                'puede ser anterior.', fields.Date.to_string(later.date)))

    def action_confirm(self):
        self.ensure_one()
        rows = self.line_ids.filtered('intervene')
        self._check_can_intervene(rows)
        order = self.purchase_order_id
        # sudo: la intervención la decide ejecución › aprueba, que no
        # administra compras ni el fondo (lo retiene el sistema, como pide
        # CR-20: quien interviene puede no ser de contabilidad).
        order_sudo = order.sudo()
        intervention_sudo = self.env['construction.contract.intervention'].sudo().create({
            'name': '%s-INT%02d' % (order_sudo.name, len(order_sudo.construction_intervention_ids)
                                     + 1),
            'purchase_order_id': order.id,
            'date': self.date,
            'reason': self.reason,
            'user_id': self.env.user.id,
            'line_ids': [Command.create({
                'sequence': index,
                'purchase_line_id': row.purchase_line_id.id,
                'task_label': row.task_label,
                'activity_id': row.activity_id.id,
                'uom_id': row.uom_id.id,
                'price_unit': row.price_unit,
                'qty_contracted': row.qty_contracted,
                'qty_validated': row.qty_validated,
                'qty_valued': row.qty_valued,
                'qty_new': row.qty_new,
                'qty_released': row.qty_released,
                'amount_valued': row.amount_valued,
                'amount_released': row.amount_released,
            }) for index, row in enumerate(rows)],
        })
        plan_lines = self._apply_to_order(order_sudo, intervention_sudo)
        funds = self._retain_fund(order_sudo, intervention_sudo)
        intervention_sudo.fund_ids = funds
        body = self.env._(
            'Contrata intervenida (%(name)s) el %(date)s por %(user)s: %(count)s partidas; '
            'comprometido liberado %(amount)s. Motivo: %(reason)s',
            name=intervention_sudo.name, date=fields.Date.to_string(self.date),
            user=self.env.user.name, count=len(rows),
            amount=self.currency_id.format(intervention_sudo.amount_released), reason=self.reason)
        order_sudo.message_post(body=body)
        for plan in plan_lines.plan_id:
            plan.message_post(body=body)
        intervention_sudo.message_post(body=body)
        if intervention_sudo.sudo(False).has_access('read'):
            return {
                'type': 'ir.actions.act_window',
                'res_model': intervention_sudo._name,
                'res_id': intervention_sudo.id,
                'view_mode': 'form',
            }
        return {'type': 'ir.actions.act_window_close'}

    def _apply_to_order(self, order_sudo, intervention_sudo):
        """Baja cada línea intervenida a lo ejecutado y sus asignaciones a lo
        hecho; deja las líneas del plan sin contrata."""
        plan_lines = self.env['construction.resource.plan.line']
        validated = self._validated_by_plan_line(
            order_sudo, intervention_sudo.line_ids.purchase_line_id.construction_allocation_ids
            .plan_line_id)
        for line in intervention_sudo.line_ids:
            po_line = line.purchase_line_id.sudo()
            po_line.construction_intervention_line_id = line
            for allocation in po_line.construction_allocation_ids.filtered(
                    lambda a: a.state != 'cancel'):
                plan_line = allocation.plan_line_id
                executed = max(allocation.qty_done, validated.get(plan_line, 0.0))
                if plan_line.product_uom_id.compare(executed, allocation.qty_allocated) < 0:
                    allocation.qty_allocated = executed
                plan_lines |= plan_line
            if po_line.product_uom_id.compare(line.qty_new, po_line.product_qty) < 0:
                po_line.product_qty = line.qty_new
        # La contrata sale de la línea del plan (proceso interno sobre el plan
        # aprobado, como la asignación): su saldo vuelve a «Asignar contrata».
        partner = order_sudo.partner_id.commercial_partner_id
        plan_lines.filtered(
            lambda l: l.partner_id.commercial_partner_id == partner).with_context(
            construction_plan_force=True).write({'partner_id': False})
        plan_lines._refresh_control()
        return plan_lines

    def _retain_fund(self, order_sudo, intervention_sudo):
        """D2: las cuotas del fondo de la orden quedan retenidas hasta la
        liquidación final."""
        # Una cuota ya retenida por otro motivo sigue con el suyo.
        funds = order_sudo.construction_guarantee_fund_ids.filtered(
            lambda f: f.state != 'paid' and not f.hold)
        funds.write({
            'hold': True, 'hold_by_intervention': True,
            'hold_reason': self.env._('%(hold)s (%(name)s): %(reason)s', hold=INTERVENTION_HOLD,
                                      name=intervention_sudo.name, reason=self.reason),
        })
        return funds


class ConstructionContractInterventionWizardLine(models.TransientModel):
    _name = 'construction.contract.intervention.wizard.line'
    _description = 'Partida de la preliquidación de la intervención'

    wizard_id = fields.Many2one('construction.contract.intervention.wizard', string='Asistente',
                                required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Moneda')
    intervene = fields.Boolean(string='Intervenir', default=True)
    purchase_line_id = fields.Many2one('purchase.order.line', string='Línea de la orden',
                                       required=True)
    task_label = fields.Char(string='Partida')
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad')
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    price_unit = fields.Float(string='Precio', digits='Product Price')
    qty_contracted = fields.Float(string='Contratado', digits='Product Unit')
    qty_validated = fields.Float(string='Ejecutado validado', digits='Product Unit')
    qty_valued = fields.Float(string='Valorizado', digits='Product Unit')
    qty_new = fields.Float(string='Cantidad nueva', digits='Product Unit',
                           help='La línea de la orden baja a lo ejecutado: lo valorizado o, si '
                                'hay avance validado sin valorizar, ese.')
    qty_released = fields.Float(string='Saldo', digits='Product Unit')
    amount_valued = fields.Monetary(string='Importe valorizado', compute='_compute_amounts',
                                    currency_field='currency_id')
    amount_released = fields.Monetary(string='Comprometido que se libera',
                                      compute='_compute_amounts', currency_field='currency_id')

    @api.depends('qty_valued', 'qty_released', 'price_unit')
    def _compute_amounts(self):
        for row in self:
            currency = row.currency_id
            valued = row.qty_valued * row.price_unit
            released = row.qty_released * row.price_unit
            row.amount_valued = currency.round(valued) if currency else valued
            row.amount_released = currency.round(released) if currency else released

# -*- coding: utf-8 -*-
"""W-05 «Asignar contrata» (P-05): pone la contrata en las líneas de contrata
de la selección y suma su alcance a la OC de servicio abierta de la contrata
en la obra (una por contrata y obra; si no existe, se crea en borrador)."""
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import stage_selection

from ..models.construction_contract_condition import compute_cascade


class ConstructionPlanContractWizard(models.TransientModel):
    _name = 'construction.plan.contract.wizard'
    _inherit = 'construction.plan.supply.mixin'
    _description = 'Asignar contrata desde el plan'

    stage = fields.Selection(
        stage_selection, string='Etapa',
        help='Vacía: todas las etapas de ejecución en campo de la selección.')
    available_activity_ids = fields.Many2many(
        'construction.labor.activity', string='Actividades de la selección',
        compute='_compute_available_activity_ids', check_company=True)
    activity_ids = fields.Many2many(
        'construction.labor.activity', 'construction_plan_contract_wiz_activity_rel',
        'wizard_id', 'activity_id', string='Actividades', check_company=True,
        domain="[('id', 'in', available_activity_ids)]",
        help='Vacía: todas las actividades de contrata de la selección.')
    partner_id = fields.Many2one(
        'res.partner', string='Contrata', required=True, check_company=True)
    date_start = fields.Date(
        string='Inicio de la ejecución', default=fields.Date.context_today, required=True,
        help='Fecha prevista en la OC; también fija la tarifa vigente.')
    date_end = fields.Date(string='Fin de la ejecución')
    line_ids = fields.One2many(
        'construction.plan.contract.wizard.line', 'wizard_id', string='Vista previa',
        compute='_compute_line_ids', store=True, readonly=False)
    plan_line_count = fields.Integer(
        string='Nº de líneas del plan', compute='_compute_totals',
        help='Líneas de contrata de la selección que reciben la contrata.')
    amount_total = fields.Monetary(
        string='Monto', compute='_compute_totals', currency_field='currency_id')
    retention_total = fields.Monetary(
        string='Retención', compute='_compute_totals', currency_field='currency_id')
    amount_net = fields.Monetary(
        string='Neto', compute='_compute_totals', currency_field='currency_id')
    purchase_order_id = fields.Many2one(
        'purchase.order', string='OC de servicio', compute='_compute_purchase_order_id',
        check_company=True,
        help='La OC abierta de la contrata en la obra; vacía: se creará una en borrador.')
    note = fields.Text(string='Avisos', compute='_compute_line_ids', store=True)
    # Alcance adicional sobre el saldo de la actividad (v1.8, M18-05): sigue la
    # política de contratas del plan.
    # Condiciones de contrata (CREVAL v1.0, 3.4): se proponen las del
    # contratista o las de Ajustes y se copian a la orden.
    condition_id = fields.Many2one(
        'construction.contract.condition', string='Condiciones de contrata',
        compute='_compute_condition_id', store=True, readonly=False,
        domain="[('order_id', '=', False), '|', ('company_id', '=', False), "
               "('company_id', '=', company_id)]",
        help='Vacío: la orden se comporta como hasta ahora (retención de la tarifa y '
             'liquidación semanal).')
    advance_pct = fields.Float(string='Adelanto (%)', digits=(16, 6),
                               compute='_compute_condition_values', store=True, readonly=False)
    guarantee_pct = fields.Float(string='Fondo de garantía (%)', digits=(16, 6),
                                 compute='_compute_condition_values', store=True, readonly=False)
    order_mode = fields.Selection(
        [('open', 'Sumar a la orden abierta'), ('new', 'Orden nueva')], string='Orden',
        compute='_compute_order_mode', store=True, readonly=False, required=True,
        default='open',
        help='Orden nueva: una orden de contrata aparte (por ejemplo, otra especialidad).')
    specialty = fields.Char(string='Especialidad', compute='_compute_specialty', store=True,
                            readonly=False)
    terms_total = fields.Monetary(string='Total contractual con IGV',
                                  compute='_compute_terms_totals', currency_field='currency_id')
    terms_advance = fields.Monetary(string='Adelanto', compute='_compute_terms_totals',
                                    currency_field='currency_id')
    terms_guarantee = fields.Monetary(string='Fondo de garantía', compute='_compute_terms_totals',
                                      currency_field='currency_id')
    exceed_reason = fields.Text(
        string='Motivo del alcance adicional',
        help='Obligatorio si se asigna más de lo que queda de la actividad en la selección y '
             'la política de contratas pide aprobación (la da la jefatura de proyectos).')

    @api.depends('partner_id', 'company_id')
    def _compute_condition_id(self):
        for wizard in self:
            partner = wizard.partner_id.commercial_partner_id.with_company(wizard.company_id)
            wizard.condition_id = partner.construction_condition_id \
                or wizard.company_id.construction_default_condition_id

    @api.depends('condition_id')
    def _compute_condition_values(self):
        for wizard in self:
            wizard.advance_pct = wizard.condition_id.advance_pct
            wizard.guarantee_pct = wizard.condition_id.guarantee_pct

    @api.depends('purchase_order_id', 'condition_id')
    def _compute_order_mode(self):
        for wizard in self:
            order = wizard.purchase_order_id
            same = order and (order.construction_terms_id.template_id == wizard.condition_id
                              or (not order.construction_terms_id and not wizard.condition_id))
            wizard.order_mode = 'open' if same else 'new'

    @api.depends('line_ids.plan_line_ids')
    def _compute_specialty(self):
        for wizard in self:
            levels = wizard.line_ids.plan_line_ids.level_1_id
            wizard.specialty = levels[0].name if len(levels) == 1 else False

    @api.depends('line_ids.amount', 'condition_id', 'advance_pct', 'guarantee_pct')
    def _compute_terms_totals(self):
        for wizard in self:
            condition = wizard.condition_id
            if not condition:
                wizard.terms_total = wizard.terms_advance = wizard.terms_guarantee = 0.0
                continue
            direct = sum(wizard.line_ids.mapped('amount'))
            _rows, totals = compute_cascade(condition, wizard.currency_id, direct, 0.0, 0.0,
                                            advance_pct=wizard.advance_pct,
                                            guarantee_pct=wizard.guarantee_pct)
            wizard.terms_total = totals['total']
            wizard.terms_advance = totals['advance']
            wizard.terms_guarantee = totals['retention']

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Desde el cronograma (P-15): la etapa marcada; con varias, todas.
        stages = self.env.context.get('construction_selection_stages') or []
        if 'stage' in fields_list and stages:
            res['stage'] = stages[0] if len(stages) == 1 else False
        return res

    def _get_stages(self):
        self.ensure_one()
        return [self.stage] if self.stage else list(self.env['construction.stage']._field_codes())

    def _get_candidate_lines(self):
        """Líneas de contrata de la selección con saldo por asignar."""
        self.ensure_one()
        domain = [('resource_type', '=', 'contract'), ('activity_id', '!=', False)]
        lines = self._get_selected_lines(domain)
        return lines.filtered(
            lambda l: l.product_uom_id.compare(l.qty_planned - l.qty_requested, 0.0) > 0)

    @api.depends('plan_id', 'task_ids', 'whole_project', 'stage')
    def _compute_available_activity_ids(self):
        for wizard in self:
            wizard.available_activity_ids = wizard._get_candidate_lines().activity_id \
                if wizard.plan_id else False

    @api.depends('plan_id', 'task_ids', 'whole_project', 'stage', 'activity_ids', 'partner_id',
                 'date_start', 'condition_id')
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            notes = []
            if wizard.plan_id:
                rows, notes = wizard._prepare_lines()
                commands += [Command.create(vals) for vals in rows]
            wizard.line_ids = commands
            wizard.note = '\n'.join(notes) or False

    def _prepare_lines(self):
        self.ensure_one()
        lines = self._get_candidate_lines()
        if self.activity_ids:
            lines = lines.filtered(lambda l: l.activity_id in self.activity_ids)
        notes = []
        others = lines.filtered(lambda l: l.partner_id and l.partner_id != self.partner_id)
        if others and self.partner_id:
            notes.append(self.env._(
                '%(count)s líneas ya tienen otra contrata (%(partners)s) y no se reasignan.',
                count=len(others), partners=', '.join(others.partner_id.mapped('display_name'))))
            lines -= others
        # Con condiciones «por partida», una línea por actividad y partida
        # (CREVAL v1.0, 3.4: toda línea de la orden lleva su partida).
        by_task = self.condition_id.line_detail == 'task'
        groups = defaultdict(lambda: self.env['construction.resource.plan.line'])
        for line in lines:
            groups[(line.activity_id, line.task_id if by_task else self.env['project.task'])] |= line
        rows = []
        project = self.plan_id.project_id
        for (activity, task), plan_lines in sorted(
                groups.items(), key=lambda kv: (kv[0][0].sequence, kv[0][0].code, kv[0][0].id,
                                                kv[0][1].construction_path or '', kv[0][1].id)):
            price, retention_pct, rate = activity._get_rate(
                project, self.partner_id or None, self.date_start)
            qty = sum(l.qty_planned - l.qty_requested for l in plan_lines)
            rows.append({
                'activity_id': activity.id,
                'task_id': task.id,
                'uom_id': activity.uom_id.id,
                'qty': qty,
                'price_unit': price,
                # El fondo de garantía de las condiciones reemplaza a la
                # retención de la tarifa.
                'retention_pct': 0.0 if self.condition_id else retention_pct,
                'rate_id': rate.id,
                'plan_line_ids': [Command.set(plan_lines.ids)],
            })
        return rows, notes

    @api.depends('line_ids.amount', 'line_ids.retention_amount', 'line_ids.plan_line_ids')
    def _compute_totals(self):
        for wizard in self:
            wizard.plan_line_count = len(wizard.line_ids.plan_line_ids)
            wizard.amount_total = sum(wizard.line_ids.mapped('amount'))
            wizard.retention_total = sum(wizard.line_ids.mapped('retention_amount'))
            wizard.amount_net = wizard.amount_total - wizard.retention_total

    @api.depends('partner_id', 'plan_id')
    def _compute_purchase_order_id(self):
        # sudo: la OC se busca aunque el planificador no tenga acceso a
        # compras; solo para mostrar a cuál se sumará el alcance.
        orders_sudo = self.env['purchase.order'].sudo()
        for wizard in self:
            order_sudo = orders_sudo._construction_open_service_order(
                wizard.partner_id, wizard.plan_id.project_id) if wizard.partner_id else False
            wizard.purchase_order_id = order_sudo.id if order_sudo else False

    # ------------------------------------------------------------------
    # Crear
    # ------------------------------------------------------------------
    def _get_service_product(self, activity):
        """Servicio de la OC de la actividad: el suyo o uno creado con su
        nombre, su unidad y recepción manual, sin impuestos (los de la
        contrata se ponen en el producto si corresponden)."""
        if activity.product_id:
            return activity.product_id
        # sudo: el planificador no suele poder crear productos ni editar el
        # catálogo de actividades; el servicio sale de la actividad.
        product_sudo = self.env['product.product'].sudo().create({
            'name': activity.with_context(lang=self.env.user.lang).name,
            'default_code': activity.code,
            'type': 'service',
            'uom_id': activity.uom_id.id,
            'purchase_method': 'receive',
            'purchase_ok': True,
            'sale_ok': False,
            'taxes_id': [Command.clear()],
            'supplier_taxes_id': [Command.clear()],
            'company_id': activity.company_id.id,
        })
        activity.sudo().product_id = product_sudo
        return product_sudo.sudo(False)

    def _get_service_taxes(self, product):
        """Impuestos del servicio; con condiciones que cobran IGV y un servicio
        sin impuestos, el impuesto de compra por defecto de la compañía."""
        company = self.plan_id.company_id
        taxes = product.supplier_taxes_id.filtered(lambda t: t.company_id == company)
        if not taxes and self.condition_id.scheme_line_ids.filtered(lambda l: l.kind == 'tax'):
            taxes = company.account_purchase_tax_id
        return taxes

    def _get_analytic_distribution(self, plan_lines):
        distributions = {tuple(sorted((line.analytic_distribution or {}).items()))
                         for line in plan_lines}
        if len(distributions) == 1 and next(iter(distributions)):
            return dict(next(iter(distributions)))
        account = self.plan_id.project_id.account_id
        return {str(account.id): 100.0} if account else False

    def _check_additional_scope(self, rows):
        """Alcance por encima del saldo de la actividad en la selección: la
        política de contratas del plan (avisar, aprobación de la jefatura o
        bloquear) y el registro del exceso autorizado."""
        from odoo.addons.al_construction_planner.models.common import PROJECT_HEAD_GROUPS
        plan = self.plan_id
        excess_rows = []
        for row in rows:
            balance = sum(l.qty_planned - l.qty_requested for l in row.plan_line_ids)
            if row.uom_id.compare(row.qty, balance) > 0:
                excess_rows.append((row, row.qty - balance))
        if not excess_rows:
            return
        policy = plan._exceed_policy_for('contract')
        text = '\n'.join('   · %s: %s %s' % (row.activity_id.display_name, round(excess, 2),
                                               row.uom_id.name) for row, excess in excess_rows)
        if policy == 'block':
            raise UserError(self.env._(
                'El alcance pasa lo que queda en el plan y la política de contratas es '
                'bloquear:\n\n%s', text))
        if policy == 'approval':
            if not self.env.user.has_groups(PROJECT_HEAD_GROUPS):
                raise UserError(self.env._(
                    'El alcance adicional lo aprueba la jefatura de proyectos:\n\n%s', text))
            if not (self.exceed_reason or '').strip():
                raise UserError(self.env._('Escriba el motivo del alcance adicional.'))
            self.env['construction.exceed.log']._log([{
                'kind': 'excess', 'plan_id': plan.id, 'project_id': plan.project_id.id,
                'company_id': plan.company_id.id, 'plan_line_id': row.plan_line_ids[:1].id,
                'task_id': row.plan_line_ids[:1].task_id.id,
                'activity_id': row.activity_id.id, 'partner_id': self.partner_id.id,
                'qty': excess, 'uom_id': row.uom_id.id, 'amount': excess * row.price_unit,
                'reason': self.exceed_reason, 'document': plan.display_name,
                'res_model': plan._name, 'res_id': plan.id,
            } for row, excess in excess_rows])
        else:
            plan.message_post(body=self.env._(
                'Alcance adicional asignado a %(partner)s sobre lo planificado:\n%(text)s',
                partner=self.partner_id.display_name, text=text))

    def action_assign(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_supply_wizard_state()
        if self.date_end and self.date_end < self.date_start:
            raise UserError(self.env._('La ejecución termina antes de empezar.'))
        rows = self.line_ids.filtered(
            lambda r: r.uom_id and r.uom_id.compare(r.qty, 0.0) > 0 and r.plan_line_ids)
        if not rows:
            raise UserError(self.env._(
                'No hay actividades de contrata por asignar en esta selección.'))
        self._check_additional_scope(rows)
        project = plan.project_id
        # sudo: la OC de servicio nace de la asignación y queda en borrador
        # para que Compras la confirme; quien asigna (Proyectos) no necesita
        # permisos de compras.
        orders_sudo = self.env['purchase.order'].sudo()
        order_sudo = orders_sudo._construction_open_service_order(self.partner_id, project) \
            if self.order_mode == 'open' else orders_sudo
        if order_sudo and order_sudo.state != 'draft' and self.condition_id:
            # Con condiciones, una orden confirmada solo crece por una
            # ampliación (adicional aprobado): el alcance nuevo va en otra.
            order_sudo = orders_sudo
        if not order_sudo:
            order_sudo = orders_sudo.create({
                'partner_id': self.partner_id.id,
                'company_id': plan.company_id.id,
                'construction_is_service_order': True,
                'construction_project_id': project.id,
                'construction_plan_id': plan.id,
                'construction_specialty': self.specialty,
                'origin': '%s · %s' % (project.display_name, plan.display_name),
            })
        elif order_sudo.construction_plan_id != plan:
            order_sudo.construction_plan_id = plan
        if self.condition_id:
            order_sudo._construction_apply_terms(self.condition_id, {
                'advance_pct': self.advance_pct, 'guarantee_pct': self.guarantee_pct})
        allocation_values = []
        for row in rows:
            product = self._get_service_product(row.activity_id)
            po_line_sudo = order_sudo.order_line.filtered(
                lambda l: l.construction_activity_id == row.activity_id
                and l.product_id == product and l.construction_task_id == row.task_id
                and not l.construction_is_additional
                and l.currency_id.compare_amounts(l.price_unit, row.price_unit) == 0)[:1]
            if po_line_sudo:
                po_line_sudo.product_qty += row.qty
            else:
                po_line_sudo = self.env['purchase.order.line'].sudo().create({
                    'order_id': order_sudo.id,
                    'product_id': product.id,
                    'product_qty': row.qty,
                    'product_uom_id': row.uom_id.id,
                    'price_unit': row.price_unit,
                    'tax_ids': [Command.set(self._get_service_taxes(product).ids)],
                    'date_planned': self.date_start,
                    'name': '%s · %s' % (row.task_id.display_name, row.activity_id.display_name)
                    if row.task_id else row.activity_id.display_name,
                    'construction_activity_id': row.activity_id.id,
                    'construction_task_id': row.task_id.id,
                    'construction_retention_pct': row.retention_pct,
                    'analytic_distribution': self._get_analytic_distribution(row.plan_line_ids),
                })
            for plan_line in row.plan_line_ids:
                qty = plan_line.qty_planned - plan_line.qty_requested
                if plan_line.product_uom_id.compare(qty, 0.0) > 0:
                    allocation_values.append({
                        'plan_line_id': plan_line.id,
                        'kind': 'service_order',
                        'purchase_line_id': po_line_sudo.id,
                        'qty_allocated': qty,
                    })
        plan_lines = rows.plan_line_ids
        # La contrata se escribe sobre el plan aprobado: es la asignación que
        # la especificación prevé (proceso interno, no una edición del plan).
        plan_lines.with_context(construction_plan_force=True).write(
            {'partner_id': self.partner_id.id})
        self.env['construction.resource.plan.allocation'].create(allocation_values)
        plan._mark_in_progress()
        body = self.env._(
            'Contrata %(partner)s asignada a %(lines)s líneas (%(selection)s): %(count)s '
            'actividades por %(amount)s en %(order)s.', partner=self.partner_id.display_name,
            lines=len(plan_lines), selection=self._get_selection_label(), count=len(rows),
            amount=self.currency_id.format(self.amount_total), order=order_sudo.name)
        plan.message_post(body=body)
        order_sudo.message_post(body=body)
        if order_sudo.sudo(False).has_access('read'):
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': order_sudo.id,
                'view_mode': 'form',
            }
        return {'type': 'ir.actions.act_window_close'}


class ConstructionPlanContractWizardLine(models.TransientModel):
    _name = 'construction.plan.contract.wizard.line'
    _description = 'Actividad de la asignación de contrata'

    wizard_id = fields.Many2one(
        'construction.plan.contract.wizard', string='Asistente', required=True,
        ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Moneda')
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    qty = fields.Float(string='Driver presupuestado', digits='Product Unit')
    price_unit = fields.Monetary(string='Tarifa', currency_field='currency_id')
    amount = fields.Monetary(
        string='Monto', compute='_compute_amount', currency_field='currency_id')
    retention_pct = fields.Float(string='Retención (%)', digits=(5, 2))
    retention_amount = fields.Monetary(
        string='Retención', compute='_compute_amount', currency_field='currency_id')
    rate_id = fields.Many2one('construction.labor.rate', string='Tarifa aplicada')
    task_id = fields.Many2one('project.task', string='Partida')
    plan_line_ids = fields.Many2many(
        'construction.resource.plan.line', 'construction_plan_contract_wiz_line_rel',
        'wizard_line_id', 'plan_line_id', string='Líneas del plan')

    @api.depends('qty', 'price_unit', 'retention_pct')
    def _compute_amount(self):
        for row in self:
            currency = row.currency_id
            amount = row.qty * row.price_unit
            amount = currency.round(amount) if currency else amount
            retention = amount * row.retention_pct / 100.0
            row.amount = amount
            row.retention_amount = currency.round(retention) if currency else retention

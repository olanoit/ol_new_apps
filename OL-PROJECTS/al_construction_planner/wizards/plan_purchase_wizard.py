# -*- coding: utf-8 -*-
"""W-02 «Compra masiva» (P-10): un requerimiento de compra (OCA) con la
necesidad de la selección, en dos modos: con la analítica de la obra (compra
toda la necesidad) o como stock general (descuenta lo libre en el central y
lo que ya viene en compras). En los dos sube el comprado de las líneas."""
from collections import defaultdict
from datetime import date

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round


class ConstructionPlanPurchaseWizard(models.TransientModel):
    _name = 'construction.plan.purchase.wizard'
    _inherit = 'construction.plan.supply.mixin'
    _description = 'Compra masiva desde el plan'

    mode = fields.Selection(
        [('project', 'Con analítica de la obra'), ('general', 'Stock general')],
        string='Modo', required=True, default='project',
        help='Con analítica: cada línea lleva la distribución de la obra y se compra toda la '
             'necesidad. Stock general: sin analítica y se compra la necesidad menos lo libre '
             'en el central y lo que ya viene en compras.')
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Destino', required=True, check_company=True,
        domain="[('code', '=', 'incoming'), ('company_id', '=', company_id)]",
        default=lambda self: self._default_picking_type(),
        help='Recepción del almacén central donde entra la compra.')
    date_from = fields.Date(string='Necesidad desde')
    date_to = fields.Date(string='Necesidad hasta')
    group_by = fields.Selection(
        [('product', 'Producto'), ('date', 'Producto y fecha de necesidad')],
        string='Agrupar por', required=True, default='product')
    line_ids = fields.One2many(
        'construction.plan.purchase.wizard.line', 'wizard_id', string='Vista previa',
        compute='_compute_line_ids', store=True, readonly=False)
    amount_need = fields.Monetary(
        string='Necesidad a costo del maestro', compute='_compute_amount_need',
        currency_field='currency_id')

    @api.model
    def _default_picking_type(self):
        company = self.env.company
        return company.construction_pr_picking_type_id or self.env['purchase.request'].with_context(
            company_id=company.id)._default_picking_type()

    @api.depends('line_ids.qty_need', 'line_ids.product_id')
    def _compute_amount_need(self):
        for wizard in self:
            wizard.amount_need = sum(
                line.qty_need * line.product_id.with_company(wizard.company_id).standard_price
                for line in wizard.line_ids)

    def _get_need(self, line):
        """Necesidad de compra de una línea del plan, en la UdM del producto:
        lo planificado menos lo ya comprado o pedido por la obra (lo pedido
        sigue su propio camino: despacho del central o compra del faltante)."""
        covered = max(line.qty_requested, line.qty_purchased)
        return line._qty_to_product_uom(max(line.qty_planned - covered, 0.0))

    def _get_purchase_uom(self, product):
        sellers = product.seller_ids.filtered(
            lambda s: not s.company_id or s.company_id == self.company_id)
        return sellers[:1].product_uom_id or product.uom_id

    @api.depends('plan_id', 'task_ids', 'whole_project', 'mode', 'picking_type_id',
                 'date_from', 'date_to', 'group_by', 'stage_production', 'stage_assembly',
                 'stage_installation', 'stage_finishing')
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            if wizard.plan_id:
                commands += [Command.create(vals) for vals in wizard._prepare_lines()]
            wizard.line_ids = commands

    def _prepare_lines(self):
        self.ensure_one()
        domain = [('resource_type', '=', 'material'), ('product_id', '!=', False)]
        if self.date_from:
            domain.append(('date_needed', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_needed', '<=', self.date_to))
        groups = defaultdict(lambda: self.env['construction.resource.plan.line'])
        for line in self._get_selected_lines(domain):
            if line.product_id.type != 'consu':
                continue
            if line._product_uom().is_zero(self._get_need(line)):
                continue
            key_date = line.date_needed if self.group_by == 'date' else False
            groups[(line.product_id, key_date)] |= line
        location = self.picking_type_id.default_location_dest_id
        stock_left = {}
        result = []
        for (product, key_date), plan_lines in sorted(
                groups.items(), key=lambda kv: (kv[0][0].display_name, kv[0][1] or date.min)):
            need = sum(self._get_need(line) for line in plan_lines)
            if product not in stock_left:
                ctx_product = product.with_context(location=location.id) if location else product
                stock_left[product] = [max(ctx_product.free_qty, 0.0),
                                       max(ctx_product.incoming_qty, 0.0)]
            free, incoming = stock_left[product]
            if self.mode == 'general':
                # Lo libre y lo que ya viene cubren la necesidad, en ese orden;
                # lo que cubre no vuelve a usarse en el grupo siguiente.
                from_free = min(free, need)
                from_incoming = min(incoming, need - from_free)
                stock_left[product] = [free - from_free, incoming - from_incoming]
                to_buy = need - from_free - from_incoming
            else:
                to_buy = need
            purchase_uom = self._get_purchase_uom(product)
            qty_to_buy = product.uom_id._compute_quantity(to_buy, purchase_uom, round=False)
            if self._is_whole_uom(purchase_uom):
                qty_to_buy = float_round(qty_to_buy, precision_rounding=1.0, rounding_method='UP')
            result.append({
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'purchase_uom_id': purchase_uom.id,
                'date_required': key_date or min(
                    filter(None, plan_lines.mapped('date_needed')), default=False),
                'qty_need': need,
                'qty_free': free,
                'qty_incoming': incoming,
                'qty_to_buy': qty_to_buy,
                'plan_line_ids': [Command.set(plan_lines.ids)],
            })
        return result

    def _get_analytic_distribution(self, plan_lines):
        """Distribución de la obra: la de las líneas si todas comparten una; si
        no, la cuenta analítica de la obra al 100 %."""
        distributions = {tuple(sorted((line.analytic_distribution or {}).items()))
                         for line in plan_lines}
        if len(distributions) == 1 and next(iter(distributions)):
            return dict(next(iter(distributions)))
        account = self.plan_id.project_id.account_id
        return {str(account.id): 100.0} if account else False

    def action_create(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_supply_wizard_state()
        lines = self.line_ids.filtered(
            lambda l: l.purchase_uom_id and l.purchase_uom_id.compare(l.qty_to_buy, 0.0) > 0)
        if not lines:
            raise UserError(self.env._('No hay nada que comprar con esta selección y filtros.'))
        modes = dict(self._fields['mode']._description_selection(self.env))
        request = self.env['purchase.request'].create({
            'origin': plan.display_name,
            'company_id': plan.company_id.id,
            'picking_type_id': self.picking_type_id.id,
            'description': self.env._(
                'Compra masiva de %(project)s (%(mode)s): %(selection)s',
                project=plan.project_id.display_name, mode=modes[self.mode].lower(),
                selection=self._get_selection_label()),
            'construction_plan_id': plan.id,
        })
        allocation_values = []
        for line in lines:
            pr_line = self.env['purchase.request.line'].create({
                'request_id': request.id,
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'product_uom_id': line.purchase_uom_id.id,
                'product_qty': line.qty_to_buy,
                'date_required': line.date_required or fields.Date.context_today(self),
                'analytic_distribution': (self._get_analytic_distribution(line.plan_line_ids)
                                          if self.mode == 'project' else False),
                'construction_plan_mode': self.mode,
            })
            qty = line.purchase_uom_id._compute_quantity(line.qty_to_buy, line.product_id.uom_id)
            balance = {plan_line: self._get_need(plan_line) for plan_line in line.plan_line_ids}
            shares = line.plan_line_ids._supply_split(qty, balance=balance)
            allocation_values += [{
                'plan_line_id': plan_line.id,
                'kind': 'purchase_request',
                'purchase_request_line_id': pr_line.id,
                'qty_allocated': share,
            } for plan_line, share in shares.items() if not plan_line.product_uom_id.is_zero(share)]
        self.env['construction.resource.plan.allocation'].create(allocation_values)
        plan._mark_in_progress()
        plan.message_post(body=self.env._(
            'Compra masiva %(request)s (%(mode)s): %(count)s productos.',
            request=request.name, mode=modes[self.mode].lower(), count=len(lines)))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request',
            'res_id': request.id,
            'view_mode': 'form',
        }


class ConstructionPlanPurchaseWizardLine(models.TransientModel):
    _name = 'construction.plan.purchase.wizard.line'
    _description = 'Línea de la compra masiva'

    wizard_id = fields.Many2one(
        'construction.plan.purchase.wizard', string='Asistente', required=True,
        ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unidad')
    purchase_uom_id = fields.Many2one('uom.uom', string='Unidad de compra')
    date_required = fields.Date(string='Requerido')
    qty_need = fields.Float(string='Necesidad', digits='Product Unit')
    qty_free = fields.Float(string='Libre en central', digits='Product Unit')
    qty_incoming = fields.Float(string='Ya en compras', digits='Product Unit')
    qty_to_buy = fields.Float(string='A comprar', digits='Product Unit')
    plan_line_ids = fields.Many2many(
        'construction.resource.plan.line', 'construction_plan_purchase_wiz_line_rel',
        'wizard_line_id', 'plan_line_id', string='Líneas del plan')

# -*- coding: utf-8 -*-
"""Abastecimiento de la obra (P-18) y alertas de abastecimiento.

Por producto de material del plan vigente:

- necesidad por semana de inicio de la etapa que consume el material en cada
  ambiente (``construction.space.stage``, el calendario de P-15); sin etapa
  del ambiente, la fecha de necesidad de la línea. Lo atrasado entra en la
  primera semana. La necesidad es lo planificado menos lo consumido;
- «Obra»: la necesidad total del plan;
- stock libre en el almacén de la obra y en el central; «En OC»: lo pedido y
  no recibido en OC confirmadas con la analítica de la obra;
- a comprar = necesidad del horizonte − stock − en OC, en la unidad de compra
  (la del proveedor) y redondeado hacia arriba si la unidad no es de medida;
- costo del plan (W-12), último precio de compra y alerta cuando lo supera
  en el umbral de la compañía o más; monto = a comprar × costo del plan.

``_get_supply_alerts`` resume las alertas para el inicio de la aplicación
(fase 11): precio sobre el plan, necesidad sin OC a menos de una semana y
producto sin proveedor habitual."""
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.misc import formatLang

from .common import STAGES

DEFAULT_WEEKS = 4
MAX_WEEKS = 12
#: Días que cuentan como «necesidad inmediata» para la alerta sin OC.
SOON_DAYS = 7


class ConstructionSupplyBoard(models.AbstractModel):
    _name = 'construction.supply.board'
    _description = 'Abastecimiento de la obra'

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    @api.model
    def _get_board_data(self, project, weeks=DEFAULT_WEEKS, stages=None, date_ref=None):
        """Filas del tablero de ``project``. ``stages``: etapas a incluir
        (``'none'`` = líneas sin etapa); vacío o ``None``, todas."""
        project.ensure_one()
        plan = project._construction_current_plan()
        weeks = max(1, min(int(weeks or DEFAULT_WEEKS), MAX_WEEKS))
        today = date_ref or fields.Date.context_today(self)
        week0 = project._construction_period(today)[0]
        week_starts = [week0 + timedelta(weeks=i) for i in range(weeks)]
        horizon_end = week_starts[-1] + timedelta(days=6)
        soon_end = today + timedelta(days=SOON_DAYS)
        result = {
            'project_id': project.id,
            'plan_id': plan.id,
            'plan_name': plan.display_name or '',
            'plan_state': plan.state or '',
            'weeks': [fields.Date.to_string(week) for week in week_starts],
            'horizon_end': fields.Date.to_string(horizon_end),
            'threshold': (plan.company_id or self.env.company).construction_price_alert_pct,
            'rows': [],
        }
        if not plan:
            return result
        company = plan.company_id
        domain = [('plan_id', '=', plan.id), ('resource_type', '=', 'material'),
                  ('product_id', '!=', False), ('product_id.type', '=', 'consu')]
        if stages:
            stage_domain = [('stage', 'in', [s for s in stages if s != 'none'])]
            if 'none' in stages:
                stage_domain = ['|', ('stage', '=', False)] + stage_domain
            domain += stage_domain
        # sudo: el consumido de las líneas sale de inventario y fabricación;
        # el tablero solo lo muestra (como el árbol del plan).
        lines_sudo = self.env['construction.resource.plan.line'].sudo().search(domain)
        if not lines_sudo:
            return result
        stage_dates = {
            (stage.space_task_id.id, stage.stage): stage.date_start
            for stage in self.env['construction.space.stage'].search(
                [('project_id', '=', project.id)])}

        products = lines_sudo.product_id
        need_total = defaultdict(float)
        need_weeks = defaultdict(lambda: defaultdict(float))
        need_soon = defaultdict(float)
        amount_plan = defaultdict(float)
        qty_plan = defaultdict(float)
        for line in lines_sudo:
            product = line.product_id
            planned = line._qty_to_product_uom(line.qty_planned)
            remaining = max(planned - line._qty_to_product_uom(line.qty_consumed), 0.0)
            qty_plan[product] += planned
            amount_plan[product] += line.amount_planned
            need_total[product] += remaining
            if product.uom_id.is_zero(remaining):
                continue
            need_date = (stage_dates.get((line.space_task_id.id, line.stage))
                         or line.date_needed or plan.date_start)
            week = max(project._construction_period(need_date)[0], week0)
            if week <= week_starts[-1]:
                need_weeks[product][week] += remaining
            if need_date < soon_end:
                need_soon[product] += remaining

        stock = self._get_free_stock(project, company, products)
        on_order = self._get_on_order(project, company, products)
        last_prices = self.env['construction.purchase.price.report']._get_last_prices(
            products, company, today)
        threshold = company.construction_price_alert_pct
        Mixin = self.env['construction.plan.supply.mixin']
        for product in products.sorted('display_name'):
            uom = product.uom_id
            horizon = sum(need_weeks[product].values())
            to_buy = max(horizon - stock[product] - on_order[product], 0.0)
            purchase_uom = self._get_purchase_uom(product, company)
            qty_to_buy = uom._compute_quantity(to_buy, purchase_uom, round=False)
            if Mixin._is_whole_uom(purchase_uom):
                qty_to_buy = float_round(qty_to_buy, precision_rounding=1.0,
                                         rounding_method='UP')
            else:
                qty_to_buy = purchase_uom.round(qty_to_buy)
            cost_plan = amount_plan[product] / qty_plan[product] if qty_plan[product] else 0.0
            last_date, last_price = last_prices.get(product, (False, 0.0))
            price_pct = ((last_price - cost_plan) / cost_plan * 100.0) \
                if cost_plan and last_price else 0.0
            soon_missing = max(need_soon[product] - stock[product] - on_order[product], 0.0)
            sellers = product.seller_ids.filtered(
                lambda s: not s.company_id or s.company_id == company)
            result['rows'].append({
                'product_id': product.id,
                'product_name': product.display_name,
                'uom': uom.name,
                'purchase_uom': purchase_uom.name,
                'need_total': need_total[product],
                'need_weeks': [need_weeks[product].get(week, 0.0) for week in week_starts],
                'need_horizon': horizon,
                'stock': stock[product],
                'on_order': on_order[product],
                'to_buy': to_buy,
                'qty_to_buy': qty_to_buy,
                'cost_plan': cost_plan,
                'price_last': last_price,
                'price_last_date': fields.Date.to_string(last_date) if last_date else False,
                'price_pct': price_pct,
                # Se compara el porcentaje que se muestra (un decimal).
                'price_alert': bool(cost_plan and last_price
                                    and round(price_pct, 1) >= threshold),
                'amount': purchase_uom._compute_quantity(qty_to_buy, uom, round=False) * cost_plan,
                'need_soon_missing': soon_missing,
                'no_po_alert': not uom.is_zero(soon_missing),
                'no_supplier_alert': not sellers,
            })
        return result

    @api.model
    def _get_purchase_uom(self, product, company):
        """Unidad de compra: la del proveedor habitual (como la compra masiva,
        W-02); sin proveedor, la del producto."""
        sellers = product.seller_ids.filtered(
            lambda s: not s.company_id or s.company_id == company)
        return sellers[:1].product_uom_id or product.uom_id

    @api.model
    def _get_free_stock(self, project, company, products):
        """{producto: libre en el almacén de la obra y en el central} en la
        unidad del producto."""
        locations = (project.construction_location_id
                     | company.construction_src_location_id)
        result = defaultdict(float)
        if not locations:
            return result
        # sudo: el planificador no suele tener acceso a inventario; solo se
        # leen cantidades para el tablero.
        products_sudo = products.sudo().with_company(company).with_context(
            location=locations.ids)
        for product in products_sudo:
            result[product.sudo(False)] = max(product.free_qty, 0.0)
        return result

    @api.model
    def _get_on_order(self, project, company, products):
        """{producto: pedido y no recibido} de las OC confirmadas con la
        analítica de la obra, en la unidad del producto."""
        result = defaultdict(float)
        account = project.account_id
        if not account or not products:
            return result
        # sudo: lectura de compras para el tablero (el planificador no es de
        # Compras).
        po_lines_sudo = self.env['purchase.order.line'].sudo().search([
            ('product_id', 'in', products.ids), ('state', '=', 'purchase'),
            ('company_id', '=', company.id), ('display_type', '=', False),
            ('analytic_distribution', 'in', account.ids),
        ])
        for po_line in po_lines_sudo:
            received = po_line.product_uom_id._compute_quantity(
                po_line.qty_received, po_line.product_id.uom_id, round=False)
            pending = po_line.product_uom_qty - received
            if pending > 0:
                result[po_line.product_id.sudo(False)] += pending
        return result

    # ------------------------------------------------------------------
    # Alertas (reutilizables por el inicio de la aplicación)
    # ------------------------------------------------------------------
    @api.model
    def _get_supply_alerts(self, projects, date_ref=None):
        """Alertas de abastecimiento de las obras: lista de dicts con
        ``type`` (``price``, ``no_po`` o ``no_supplier``), obra, producto y
        mensaje."""
        alerts = []
        for project in projects:
            data = self._get_board_data(project, date_ref=date_ref)
            alerts += self._alerts_from_rows(project, data['rows'])
        return alerts

    @api.model
    def _alerts_from_rows(self, project, rows):
        alerts = []
        for row in rows:
            base = {'project_id': project.id, 'project_name': project.display_name,
                    'product_id': row['product_id'], 'product_name': row['product_name']}
            if row['price_alert']:
                alerts.append(dict(base, type='price', message=self.env._(
                    '%(product)s: el último precio %(last)s supera en %(pct)s %% al costo del '
                    'plan %(plan)s.', product=row['product_name'],
                    last=formatLang(self.env, row['price_last']),
                    pct=formatLang(self.env, row['price_pct'], digits=1),
                    plan=formatLang(self.env, row['cost_plan']))))
            if row['no_po_alert']:
                alerts.append(dict(base, type='no_po', message=self.env._(
                    '%(product)s: faltan %(qty)s %(uom)s para la necesidad de los próximos '
                    '%(days)s días y no hay stock ni OC que los cubra.',
                    product=row['product_name'],
                    qty=formatLang(self.env, row['need_soon_missing']), uom=row['uom'],
                    days=SOON_DAYS)))
            if row['no_supplier_alert']:
                alerts.append(dict(base, type='no_supplier', message=self.env._(
                    '%s: sin proveedor habitual.', row['product_name'])))
        return alerts

    # ------------------------------------------------------------------
    # Interfaz de la pantalla (acción de cliente)
    # ------------------------------------------------------------------
    @api.model
    def get_board_projects(self):
        """Obras con plan de recursos para el selector de la pantalla."""
        plans = self.env['construction.resource.plan'].search(
            [('state', 'not in', ('cancel', 'replaced', 'closed'))])
        return [{'id': project.id, 'name': project.display_name}
                for project in plans.project_id.sorted('name')]

    @api.model
    def get_board(self, project_id, options=None):
        options = options or {}
        project = self.env['project.project'].browse(project_id).exists()
        if not project:
            raise UserError(self.env._('La obra ya no existe.'))
        data = self._get_board_data(
            project, weeks=options.get('weeks') or DEFAULT_WEEKS,
            stages=options.get('stages') or None)
        data['alerts'] = self._alerts_from_rows(project, data['rows'])
        data['stages'] = [list(stage) for stage in STAGES] + [['none', self.env._('Sin etapa')]]
        data['currency_symbol'] = (
            self.env['construction.resource.plan'].browse(data['plan_id']).currency_id.symbol
            or self.env.company.currency_id.symbol)
        return data

    @api.model
    def action_open_purchase(self, project_id, product_ids, options=None):
        """«Compra masiva» (W-02) con los productos marcados, toda la obra,
        las etapas del filtro y necesidad hasta el fin del horizonte."""
        options = options or {}
        project = self.env['project.project'].browse(project_id)
        plan = project._construction_current_plan()
        if not plan:
            raise UserError(self.env._('La obra no tiene plan de recursos.'))
        if not product_ids:
            raise UserError(self.env._('Marque los productos a comprar.'))
        plan._check_supply_wizard_state()
        data_weeks = max(1, min(int(options.get('weeks') or DEFAULT_WEEKS), MAX_WEEKS))
        week0 = project._construction_period(fields.Date.context_today(self))[0]
        horizon_end = week0 + timedelta(weeks=data_weeks) - timedelta(days=1)
        stages = [s for s in options.get('stages') or [] if s != 'none']
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner.action_plan_purchase_wizard')
        action['context'] = {
            'default_plan_id': plan.id,
            'default_date_to': fields.Date.to_string(horizon_end),
            'construction_selection_project': True,
            'construction_selection_stages': stages,
            'construction_selection_product_ids': product_ids,
        }
        return action

    @api.model
    def action_open_prices(self, product_id, project_id=None):
        """P-16 del producto desde el tablero."""
        product = self.env['product.product'].browse(product_id)
        plan = self.env['project.project'].browse(project_id)._construction_current_plan() \
            if project_id else None
        return self.env['construction.purchase.price.analysis']._action_open(
            product, plan=plan or None)


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def action_open_supply_board(self):
        """Abastecimiento de la obra (P-18) del plan."""
        self.ensure_one()
        action = self.env['ir.actions.client']._for_xml_id(
            'al_construction_planner.action_construction_supply_board')
        action['context'] = {'construction_project_id': self.project_id.id}
        return action

    def action_open_product_create(self):
        """Crear producto (W-11) sin línea: queda marcado con este plan."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Crear producto desde el plan'),
            'res_model': 'construction.product.create.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_plan_id': self.id,
                        'default_company_id': (self.company_id or self.env.company).id},
        }


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def action_open_purchase_prices(self):
        """Precios de compra (P-16) del producto de las líneas."""
        if len(self.product_id) != 1 or len(self.plan_id) != 1:
            raise UserError(self.env._('Seleccione líneas de un solo plan y de un solo producto.'))
        return self.env['construction.purchase.price.analysis']._action_open(
            self.product_id, plan=self.plan_id,
            lines=self.filtered(lambda l: l.product_id == self.product_id))

    def action_open_product_create(self):
        """Crear producto desde la línea (W-11, P-17)."""
        self.ensure_one()
        if self.plan_id.state != 'draft':
            raise UserError(self.env._(
                'El plan %s ya no está en borrador: créele una versión nueva.',
                self.plan_id.display_name))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Crear producto desde el plan'),
            'res_model': 'construction.product.create.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_plan_line_id': self.id,
                        'default_company_id': (self.company_id or self.env.company).id},
        }

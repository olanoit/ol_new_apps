# -*- coding: utf-8 -*-
"""Valorización al cliente por avance de la partida (requerimiento CREVAL
v1.0, CR-01) y gastos generales, imprevistos, utilidad y descuento en
proporción (CR-12).

* La obra elige la base de la valorización: las entregas semanales (como
  hasta ahora) o el avance validado de cada partida de la venta al corte,
  con el porcentaje escrito con motivo de siempre.
* Las líneas de la venta marcadas como gastos generales, imprevistos,
  utilidad o descuento no son partidas: quedan fuera de los niveles y del
  plan y se valorizan en la proporción del costo directo valorizado."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import norm

from .construction_valuation import DONE_STATES

LINE_ROLES = [
    ('partida', 'Partida'),
    ('overhead', 'Gastos generales'),
    ('contingency', 'Imprevistos'),
    ('profit', 'Utilidad'),
    ('discount', 'Descuento'),
]
# Cómo empieza el nombre de la línea de la venta → su rol.
ROLE_PREFIXES = (
    ('gastos generales', 'overhead'), ('imprevistos', 'contingency'),
    ('utilidad', 'profit'), ('descuento', 'discount'),
)
VALUATION_BASES = [
    ('delivery', 'Entregas semanales'),
    ('progress', 'Avance validado de la partida'),
]


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    construction_line_role = fields.Selection(
        LINE_ROLES, string='Rol en la obra', compute='_compute_construction_line_role',
        store=True, readonly=False, precompute=True,
        help='Partida: entra a los niveles y al plan. Gastos generales, imprevistos, utilidad o '
             'descuento: fuera de los niveles y del plan; se valorizan en proporción al costo '
             'directo. Se propone por el nombre de la línea.')

    @api.depends('name')
    def _compute_construction_line_role(self):
        for line in self:
            name = norm((line.name or '').splitlines()[0] if line.name else '')
            line.construction_line_role = next(
                (role for prefix, role in ROLE_PREFIXES if name.startswith(prefix)), 'partida')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_valuation_basis = fields.Selection(
        VALUATION_BASES, string='Base de la valorización', default='delivery', required=True,
        help='Entregas semanales: lo entregado de cada partida en las entregas confirmadas. '
             'Avance validado de la partida: el avance validado de cada línea de la venta al '
             'corte (o el porcentaje que se escriba con motivo).')

    def _construction_partida_lines(self):
        return super()._construction_partida_lines().filtered(
            lambda l: l.construction_line_role == 'partida')

    def _construction_proportional_lines(self):
        """Líneas de la venta que se valorizan en proporción al costo directo."""
        self.ensure_one()
        return self.construction_sale_order_id.order_line.filtered(
            lambda l: not l.display_type and not l.is_downpayment
            and l.construction_line_role != 'partida')


class ConstructionValuation(models.Model):
    _inherit = 'construction.valuation'

    @api.model
    def _get_progress_line_values(self, project, cutoff, exclude=None):
        """Una línea por partida con su avance validado al corte: lo ejecutado
        valorizado al costo del plan ÷ lo planificado de la partida."""
        plan = project._construction_current_plan()
        if not plan:
            raise UserError(self.env._('La obra %s no tiene un plan vigente.',
                                       project.display_name))
        lines_by_partida = project._construction_lines_by_partida(plan)
        all_lines = self.env['construction.resource.plan.line'].union(*lines_by_partida.values())
        execution = all_lines._construction_valued_execution(cutoff)
        previous = self.env['construction.valuation.line'].search([
            ('valuation_id.project_id', '=', project.id),
            ('valuation_id.state', 'in', DONE_STATES),
            ('valuation_id', 'not in', (exclude or self).ids)])
        currency = project.company_id.currency_id or self.env.company.currency_id
        values = []
        for sale_line, plan_lines in lines_by_partida.items():
            planned = sum(plan_lines.mapped('amount_planned'))
            executed = sum(sum(execution[line].values()) for line in plan_lines)
            progress = min(executed / planned, 1.0) if planned else 0.0
            price = sale_line._construction_price(cutoff)
            before = previous.filtered(lambda l, s=sale_line: l.sale_line_id == s)
            confirmed_before = sum(before.mapped('amount_confirmed'))
            amount = max(currency.round(price * progress - confirmed_before), 0.0)
            values.append({
                'sale_line_id': sale_line.id, 'price': price,
                'progress_delivered': progress, 'pct_rule': round(progress * 100, 2),
                'confirmed_before': confirmed_before,
                'amortization_before': sum(before.mapped('amount_amortization')),
                'amount_delivered': amount, 'amount_confirmed': amount,
            })
        return values

    @api.model
    def _create_from_progress(self, project, cutoff):
        if self.search_count([('project_id', '=', project.id), ('state', '=', 'draft')]):
            raise UserError(self.env._(
                'La obra %s ya tiene una valorización en borrador.', project.display_name))
        values = self._get_progress_line_values(project, cutoff)
        valuation = self.create({
            'project_id': project.id,
            'sale_order_id': project.construction_sale_order_id.id,
            'cutoff_date': cutoff,
            'guarantee_pct': project.construction_guarantee_pct,
            'advance_amortization_pct': project.construction_advance_amortization_pct,
            'line_ids': [Command.create(vals) for vals in values],
        })
        valuation._construction_sync_proportional()
        return valuation

    def _construction_sync_proportional(self):
        """Gastos generales, imprevistos, utilidad y descuento: el mismo
        porcentaje acumulado que el costo directo (las partidas) de la venta,
        en lo entregado y en lo confirmado."""
        Line = self.env['construction.valuation.line']
        for valuation in self.filtered(lambda v: v.state in ('draft', 'sent')):
            project = valuation.project_id
            proportional = project._construction_proportional_lines()
            if not proportional:
                continue
            cutoff = valuation.cutoff_date
            currency = valuation.currency_id
            partidas = project._construction_partida_lines()
            direct = sum(line._construction_price(cutoff) for line in partidas)
            if not direct:
                continue
            previous = Line.search([
                ('valuation_id.project_id', '=', project.id),
                ('valuation_id.state', 'in', DONE_STATES),
                ('valuation_id', '!=', valuation.id)])
            mine = valuation.line_ids.filtered(lambda l: l.sale_line_id in partidas)
            before = sum(previous.filtered(lambda l: l.sale_line_id in partidas).mapped(
                'amount_confirmed'))
            delivered_ratio = (before + sum(mine.mapped('amount_delivered'))) / direct
            confirmed_ratio = (before + sum(mine.mapped('amount_confirmed'))) / direct
            for sale_line in proportional:
                price = sale_line._construction_price(cutoff)
                line_before = previous.filtered(lambda l, s=sale_line: l.sale_line_id == s)
                confirmed_before = sum(line_before.mapped('amount_confirmed'))
                delivered = currency.round(price * delivered_ratio - confirmed_before)
                confirmed = currency.round(price * confirmed_ratio - confirmed_before)
                vals = {
                    'price': price, 'confirmed_before': confirmed_before,
                    'amortization_before': sum(line_before.mapped('amount_amortization')),
                    'progress_delivered': delivered_ratio,
                    'pct_rule': round(delivered_ratio * 100, 2),
                    'amount_delivered': delivered, 'amount_confirmed': confirmed,
                }
                line = valuation.line_ids.filtered(lambda l, s=sale_line: l.sale_line_id == s)
                if line:
                    line.with_context(construction_proportional_sync=True).write(vals)
                else:
                    valuation.write({'line_ids': [Command.create(
                        dict(vals, sale_line_id=sale_line.id))]})

    @api.model
    def _create_from_deliveries(self, project, cutoff, deliveries):
        valuation = super()._create_from_deliveries(project, cutoff, deliveries)
        valuation._construction_sync_proportional()
        return valuation

    @api.model
    def _prepare_valuations(self, today=None, projects=None):
        """Las obras que valorizan por avance de la partida preparan la
        valorización al último corte sin esperar entregas."""
        today = today or fields.Date.context_today(self)
        if projects is None:
            projects = self.env['project.project'].search([
                ('is_construction_site', '=', True), ('construction_sale_order_id', '!=', False)])
        by_progress = projects.filtered(lambda p: p.construction_valuation_basis == 'progress')
        created = super()._prepare_valuations(today=today, projects=projects - by_progress)
        for project in by_progress:
            cutoffs = [c for c in project._construction_valuation_cutoffs() if c < today]
            if not cutoffs or self.search_count([('project_id', '=', project.id),
                                                 ('state', '=', 'draft')], limit=1):
                continue
            valuation = self._create_from_progress(project, cutoffs[-1])
            if valuation.currency_id.is_zero(valuation.amount_delivered):
                valuation.unlink()
                continue
            created |= valuation
        return created

    def action_refresh(self):
        by_progress = self.filtered(
            lambda v: v.project_id.construction_valuation_basis == 'progress'
            and not v.contract_id and not v.delivery_ids)
        res = super(ConstructionValuation, self - by_progress).action_refresh() \
            if self - by_progress else True
        for valuation in by_progress:
            if valuation.state != 'draft':
                raise UserError(self.env._('Solo se actualizan valorizaciones en borrador.'))
            valuation.line_ids = [Command.clear()] + [
                Command.create(vals) for vals in self._get_progress_line_values(
                    valuation.project_id, valuation.cutoff_date, exclude=valuation)]
        (self - by_progress).filtered(lambda v: v.state == 'draft')._construction_sync_proportional()
        by_progress._construction_sync_proportional()
        return res

    def _construction_valued_by_progress(self):
        self.ensure_one()
        return self.project_id.construction_valuation_basis == 'progress' \
            and not self.contract_id and bool(self.line_ids)

    def _action_confirm(self, values, confirmed):
        """Lo que el cliente confirma de las partidas arrastra a los gastos
        generales, la utilidad y el descuento."""
        for line, amount in confirmed.items():
            line.amount_confirmed = amount
        self._construction_sync_proportional()
        confirmed = {line: amount for line, amount in confirmed.items()
                     if line.sale_line_id.construction_line_role == 'partida'}
        return super()._action_confirm(values, confirmed)


class ConstructionValuationLine(models.Model):
    _inherit = 'construction.valuation.line'

    line_role = fields.Selection(related='sale_line_id.construction_line_role',
                                 string='Rol en la obra')

    def write(self, vals):
        if 'pct_manual' in vals and any(
                line.line_role != 'partida' for line in self) \
                and not self.env.context.get('construction_proportional_sync'):
            raise UserError(self.env._(
                'Los gastos generales, la utilidad y el descuento siguen el avance del costo '
                'directo: escriba el porcentaje en las partidas.'))
        res = super().write(vals)
        if 'pct_manual' in vals:
            self.valuation_id._construction_sync_proportional()
        return res


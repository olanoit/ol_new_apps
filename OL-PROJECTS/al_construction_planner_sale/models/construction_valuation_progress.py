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

from odoo.addons.al_construction_planner.models.common import DRIVER_TYPES, norm

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
# Cómo se mide el avance de la partida (CR-01).
PROGRESS_SOURCES = [
    ('qty', 'Cantidad validada'),
    ('valued', 'Avance valorizado'),
]
# Costo directo sobre el que se prorratean gastos generales, utilidad y
# descuento (CR-01).
PROPORTIONAL_SCOPES = [
    ('order', 'Toda la venta'),
    ('section', 'Su especialidad (sección de la venta)'),
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

    construction_progress_source = fields.Selection(
        PROGRESS_SOURCES, string='Avance de la partida', default='qty', required=True,
        help='Cantidad validada: lo validado de la partida al corte ÷ lo presupuestado (sin '
             're-trabajos). Avance valorizado: lo ejecutado valorizado al costo del plan ÷ lo '
             'planificado, que pondera contrata, personal propio y material.')
    construction_proportional_scope = fields.Selection(
        PROPORTIONAL_SCOPES, string='Prorrateo de gastos generales', default='order',
        required=True,
        help='Costo directo sobre el que se valorizan los gastos generales, la utilidad y el '
             'descuento: el de toda la venta o el de las partidas de su sección.')

    def _construction_partida_lines(self):
        return super()._construction_partida_lines().filtered(
            lambda l: l.construction_line_role == 'partida')

    def _construction_line_sections(self):
        """{línea de la venta: su sección (la línea de sección anterior)}."""
        self.ensure_one()
        result, section = {}, None
        for line in self.construction_sale_order_id.order_line.sorted(lambda l: (l.sequence, l.id)):
            if line.display_type == 'line_section':
                section = line
            elif not line.display_type:
                result[line] = section
        return result

    def _construction_terms_contract(self):
        """Contrato vigente de la obra del que salen el adelanto, el fondo de
        garantía y la detracción de la valorización por avance (CR-01)."""
        self.ensure_one()
        return self.env['construction.contract'].search([
            ('project_id', '=', self.id), ('state', '=', 'active')], limit=1)

    def _construction_proportional_lines(self):
        """Líneas de la venta que se valorizan en proporción al costo directo."""
        self.ensure_one()
        return self.construction_sale_order_id.order_line.filtered(
            lambda l: not l.display_type and not l.is_downpayment
            and l.construction_line_role != 'partida')


class ConstructionValuation(models.Model):
    _inherit = 'construction.valuation'

    # Resumen con las condiciones del contrato (CR-01): IGV, detracción y lo
    # que cobra la obra.
    detraction_pct = fields.Float(
        string='Detracción (%)', readonly=True,
        help='La del contrato vigente de la obra al preparar la valorización.')
    amount_tax = fields.Monetary(string='IGV', compute='_compute_collection')
    amount_detraction = fields.Monetary(
        string='Detracción', compute='_compute_collection',
        help='Sobre el total con IGV de lo confirmado; el cliente la deposita en la cuenta de '
             'detracciones.')
    amount_to_collect = fields.Monetary(
        string='Neto a cobrar con IGV', compute='_compute_collection',
        help='Neto (confirmado menos fondo de garantía y amortización) más IGV menos detracción.')

    @api.depends('line_ids.amount_confirmed', 'amount_net', 'detraction_pct')
    def _compute_collection(self):
        for valuation in self:
            currency = valuation.currency_id
            tax = 0.0
            for line in valuation.line_ids:
                taxes = line.sale_line_id.tax_ids
                if taxes and line.amount_confirmed:
                    res = taxes.compute_all(line.amount_confirmed, currency=currency)
                    tax += res['total_included'] - res['total_excluded']
            tax = currency.round(tax) if currency else tax
            total = valuation.amount_confirmed + tax
            detraction = total * valuation.detraction_pct / 100.0
            detraction = currency.round(detraction) if currency else detraction
            valuation.amount_tax = tax
            valuation.amount_detraction = detraction
            valuation.amount_to_collect = valuation.amount_net + tax - detraction

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
        validated = self._construction_validated_qty(all_lines, cutoff) \
            if project.construction_progress_source == 'qty' else {}
        values = []
        for sale_line, plan_lines in lines_by_partida.items():
            progress = self._construction_partida_progress(
                project, plan_lines, execution, validated)
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
    def _construction_validated_qty(self, plan_lines, cutoff):
        """{línea del plan: cantidad validada hasta el corte, sin re-trabajos}."""
        # sudo: se cuenta lo validado de todas las contratas aunque quien
        # prepara la valorización no vea sus avances.
        progress_sudo = self.env['construction.task.progress'].sudo()
        groups = progress_sudo._read_group(
            [('plan_line_id', 'in', plan_lines.ids), ('state', '=', 'validated'),
             ('is_rework', '=', False), ('date', '<=', cutoff)],
            ['plan_line_id'], ['qty_weighted:sum'])
        return {line.id: qty or 0.0 for line, qty in groups}

    @api.model
    def _construction_partida_progress(self, project, plan_lines, execution, validated):
        """Avance de la partida al corte (CR-01). Por cantidad: lo validado de
        sus contratas y personal propio ÷ lo presupuestado, si van en una sola
        unidad; si no, o sin esas líneas, el avance valorizado."""
        if project.construction_progress_source == 'qty':
            drivers = plan_lines.filtered(lambda l: l.resource_type in DRIVER_TYPES)
            planned = sum(drivers.mapped('qty_planned'))
            if drivers and planned and len(drivers.product_uom_id) <= 1:
                done = sum(validated.get(line.id, 0.0) for line in drivers)
                return min(done / planned, 1.0)
        planned = sum(plan_lines.mapped('amount_planned'))
        executed = sum(sum(execution[line].values()) for line in plan_lines)
        return min(executed / planned, 1.0) if planned else 0.0

    @api.model
    def _create_from_progress(self, project, cutoff):
        if self.search_count([('project_id', '=', project.id), ('state', '=', 'draft')]):
            raise UserError(self.env._(
                'La obra %s ya tiene una valorización en borrador.', project.display_name))
        if not project.construction_sale_order_id:
            raise UserError(self.env._(
                'Indique la «Orden de venta del contrato» de la obra %s (pestaña Calendario e '
                'ingresos): sirve la cotización de la obra con sus metrados.',
                project.display_name))
        values = self._get_progress_line_values(project, cutoff)
        contract = project._construction_terms_contract()
        valuation = self.create({
            'project_id': project.id,
            'sale_order_id': project.construction_sale_order_id.id,
            'cutoff_date': cutoff,
            'guarantee_pct': contract.guarantee_pct if contract
            else project.construction_guarantee_pct,
            'advance_amortization_pct': contract.advance_pct if contract
            else project.construction_advance_amortization_pct,
            'detraction_pct': contract.detraction_pct,
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
            all_partidas = project._construction_partida_lines()
            previous = Line.search([
                ('valuation_id.project_id', '=', project.id),
                ('valuation_id.state', 'in', DONE_STATES),
                ('valuation_id', '!=', valuation.id)])
            sections = project._construction_line_sections() \
                if project.construction_proportional_scope == 'section' else {}
            for sale_line in proportional:
                # Con prorrateo por especialidad, las partidas de su sección;
                # sin partidas en la sección, las de toda la venta.
                partidas = all_partidas.filtered(
                    lambda l, s=sections.get(sale_line): s and sections.get(l) == s) \
                    or all_partidas
                direct = sum(line._construction_price(cutoff) for line in partidas)
                if not direct:
                    continue
                mine = valuation.line_ids.filtered(lambda l, p=partidas: l.sale_line_id in p)
                before = sum(previous.filtered(lambda l, p=partidas: l.sale_line_id in p).mapped(
                    'amount_confirmed'))
                delivered_ratio = (before + sum(mine.mapped('amount_delivered'))) / direct
                confirmed_ratio = (before + sum(mine.mapped('amount_confirmed'))) / direct
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
            valuation._construction_sync_progress_lines(self._get_progress_line_values(
                valuation.project_id, valuation.cutoff_date, exclude=valuation))
        (self - by_progress).filtered(lambda v: v.state == 'draft')._construction_sync_proportional()
        by_progress._construction_sync_proportional()
        return res

    def _construction_sync_progress_lines(self, values):
        """Actualiza las líneas por partida en vez de rehacerlas: el %
        escrito a mano, con su motivo, autor y fecha, se conserva y su monto
        se recalcula sobre lo confirmado antes (CR-01)."""
        self.ensure_one()
        existing = {line.sale_line_id.id: line for line in self.line_ids}
        partidas = self.project_id._construction_partida_lines()
        commands = []
        for vals in values:
            line = existing.pop(vals['sale_line_id'], None)
            if not line:
                commands.append(Command.create(vals))
                continue
            if line.is_manual:
                amount = self.currency_id.round(
                    vals['price'] * line.pct_manual / 100.0 - vals['confirmed_before'])
                vals = dict(vals, amount_delivered=max(amount, 0.0),
                            amount_confirmed=max(amount, 0.0),
                            progress_delivered=line.pct_manual / 100.0)
            commands.append(Command.update(line.id, vals))
        # Las partidas que ya no están (sin plan) salen; las de prorrateo las
        # rehace _construction_sync_proportional.
        commands += [Command.delete(line.id) for line in existing.values()
                     if line.sale_line_id in partidas and not line.is_manual]
        self.with_context(construction_proportional_sync=True).line_ids = commands

    def _construction_advance_pct(self):
        """Por avance de la partida, el adelanto del contrato vigente de la
        obra, como el fondo y la detracción (CR-01)."""
        self.ensure_one()
        if not self.contract_id and self.project_id.construction_valuation_basis == 'progress':
            contract = self.project_id._construction_terms_contract()
            if contract:
                return contract.advance_pct
        return super()._construction_advance_pct()

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


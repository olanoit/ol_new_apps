# -*- coding: utf-8 -*-
"""Retazos del corte (paquete 1.11, M111-12, fase B).

El retazo es un producto propio del tablero, con una variante por banda y un
lote por unidad con sus medidas. El almacenero puede cubrir la fracción de
una plancha con un retazo del pool («Cubrir con retazo») y, después del
corte, producción declara lo que salió: retazos, merma y planchas sin tocar
(«Declarar sobrantes»). El retazo se valoriza por área con el costo de la
plancha y queda fuera del reparto de las piezas."""
import math

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

REMNANT_BANDS = [
    ('r10', 'R10 (merma)'),
    ('r25', 'R25'),
    ('r50', 'R50'),
    ('r75', 'R75'),
    ('r99', 'R99'),
    ('whole', 'Plancha sin tocar'),
]
# Bandas que se guardan como retazo (D5): R10 es merma; sobre R99, plancha.
VARIANT_BANDS = ('r25', 'r50', 'r75', 'r99')
DEFAULT_BAND_LIMITS = '10,25,50,75,99'


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_cut_closing_required = fields.Boolean(
        string='Exigir «Declarar sobrantes» antes de terminar el corte')
    construction_remnant_band_limits = fields.Char(
        string='Límites de las bandas de retazo (%)', default=DEFAULT_BAND_LIMITS,
        help='Cota inferior abierta y superior cerrada. Hasta el primero es merma y sobre el '
             'último, plancha sin tocar.')

    @api.constrains('construction_remnant_band_limits')
    def _check_construction_remnant_band_limits(self):
        for company in self:
            company._construction_band_limits()

    def _construction_band_limits(self):
        self.ensure_one()
        text = self.construction_remnant_band_limits or DEFAULT_BAND_LIMITS
        try:
            limits = [float(value) for value in text.split(',')]
        except ValueError:
            limits = []
        if len(limits) != 5 or limits != sorted(set(limits)) or not 0 < limits[0] \
                or limits[-1] > 100:
            raise ValidationError(self.env._(
                'Los límites de las bandas de retazo son cinco porcentajes crecientes entre 0 '
                'y 100, por ejemplo %s.', DEFAULT_BAND_LIMITS))
        return limits

    def _construction_band(self, pct):
        """Banda de un sobrante según su % de plancha."""
        self.ensure_one()
        for limit, band in zip(self._construction_band_limits(), REMNANT_BANDS):
            if pct <= limit:
                return band[0]
        return 'whole'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_cut_closing_required = fields.Boolean(
        related='company_id.construction_cut_closing_required', readonly=False)
    construction_remnant_band_limits = fields.Char(
        related='company_id.construction_remnant_band_limits', readonly=False)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_construction_create_remnant(self):
        """Crea el producto retazo del tablero: con lote, una variante por
        banda (R25 a R99) y la misma categoría."""
        attribute = self.env.ref('al_construction_planner_mrp.product_attribute_remnant_band')
        for board in self.filtered(lambda t: not t.construction_remnant_tmpl_id):
            if not board.construction_is_indivisible:
                raise UserError(self.env._(
                    '%s no es un tablero en planchas enteras.', board.display_name))
            # Un tablero leído desde su variante trae create_product_product
            # apagado en el contexto: el retazo sí necesita sus variantes.
            board.construction_remnant_tmpl_id = self.with_context(
                create_product_product=True).create({
                'name': self.env._('RETAZO %s', board.name),
                'default_code': board.default_code and '%s-R' % board.default_code,
                'type': 'consu',
                'is_storable': True,
                'tracking': 'lot',
                'categ_id': board.categ_id.id,
                'sale_ok': False,
                'purchase_ok': False,
                'company_id': board.company_id.id,
                'construction_is_remnant': True,
                'construction_remnant_source_tmpl_id': board.id,
                'attribute_line_ids': [Command.create({
                    'attribute_id': attribute.id,
                    'value_ids': [Command.set(attribute.value_ids.ids)],
                })],
            })
        return True


class ProductProduct(models.Model):
    _inherit = 'product.product'

    construction_remnant_band = fields.Selection(
        [band for band in REMNANT_BANDS if band[0] in VARIANT_BANDS], string='Banda',
        compute='_compute_construction_remnant_band', store=True)

    @api.depends('product_template_attribute_value_ids')
    def _compute_construction_remnant_band(self):
        attribute = self.env.ref(
            'al_construction_planner_mrp.product_attribute_remnant_band', raise_if_not_found=False)
        for product in self:
            value = product.product_template_attribute_value_ids.filtered(
                lambda v: v.attribute_id == attribute)[:1]
            band = (value.product_attribute_value_id.name or '').lower()
            product.construction_remnant_band = band if band in VARIANT_BANDS else False

    def _construction_remnant_variant(self, band):
        """Variante retazo de este tablero para una banda."""
        self.ensure_one()
        return self.construction_remnant_tmpl_id.product_variant_ids.filtered(
            lambda p: p.construction_remnant_band == band)[:1]


class StockLot(models.Model):
    _inherit = 'stock.lot'

    construction_length_mm = fields.Integer(string='Largo (mm)')
    construction_width_mm = fields.Integer(string='Ancho (mm)')
    construction_area_m2 = fields.Float(
        string='Área (m²)', digits=(16, 4), compute='_compute_construction_area', store=True)
    construction_sheet_pct = fields.Float(
        string='% de plancha', digits=(16, 1), compute='_compute_construction_area', store=True)
    construction_band = fields.Selection(
        REMNANT_BANDS, string='Banda', compute='_compute_construction_area', store=True)
    construction_origin_production_id = fields.Many2one(
        'mrp.production', string='Orden de origen', readonly=True, index='btree_not_null')
    construction_origin_project_id = fields.Many2one(
        'project.project', string='Obra de origen', readonly=True)

    @api.depends('construction_length_mm', 'construction_width_mm', 'product_id')
    def _compute_construction_area(self):
        for lot in self:
            area = lot.construction_length_mm * lot.construction_width_mm / 1e6
            sheet = lot.product_id.construction_remnant_source_tmpl_id.construction_sheet_area_m2
            pct = area / sheet * 100 if sheet else 0.0
            lot.construction_area_m2 = area
            lot.construction_sheet_pct = pct
            lot.construction_band = (lot.company_id or self.env.company)._construction_band(pct) \
                if area and sheet else False

    @api.constrains('construction_length_mm', 'construction_width_mm', 'product_id')
    def _check_construction_remnant_measures(self):
        for lot in self.filtered(lambda l: l.product_id.construction_is_remnant):
            if lot.construction_length_mm <= 0 or lot.construction_width_mm <= 0:
                raise ValidationError(self.env._(
                    'El lote de retazo %s necesita largo y ancho.', lot.name))


class StockLocation(models.Model):
    _inherit = 'stock.location'

    construction_remnant_pool = fields.Boolean(
        string='Pool de retazos',
        help='Los retazos guardados aquí (y en sus sububicaciones) se ofrecen al cubrir la '
             'fracción de una plancha.')


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    construction_remnant_location_id = fields.Many2one(
        'stock.location', string='Ubicación de retazos', check_company=True,
        domain="[('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])]",
        help='Adonde entran los retazos que declara el corte de esta planta.')


class StockMove(models.Model):
    _inherit = 'stock.move'

    construction_covers_move_id = fields.Many2one(
        'stock.move', string='Cubre la fracción de', readonly=True, copy=False,
        index='btree_not_null',
        help='En el componente retazo: el componente plancha cuya fracción cubre.')
    construction_cover_move_ids = fields.One2many(
        'stock.move', 'construction_covers_move_id', string='Retazos que la cubren')
    construction_remnant_lot_id = fields.Many2one(
        'stock.lot', string='Lote del retazo', readonly=True, copy=False)
    construction_covered_qty = fields.Float(
        string='Cubierto con retazo', digits='Product Unit',
        compute='_compute_construction_covered_qty')
    construction_can_cover = fields.Boolean(
        string='Puede cubrir con retazo', compute='_compute_construction_can_cover')

    @api.depends('construction_cover_move_ids.state',
                 'construction_cover_move_ids.construction_remnant_lot_id.construction_sheet_pct')
    def _compute_construction_covered_qty(self):
        for move in self:
            covered = sum(cover.construction_remnant_lot_id.construction_sheet_pct / 100
                          for cover in move.construction_cover_move_ids
                          if cover.state != 'cancel')
            move.construction_covered_qty = move.product_id.uom_id._compute_quantity(
                covered, move.product_uom, round=False) if covered else 0.0

    @api.depends('construction_cover_move_ids.state')
    def _compute_construction_need_display(self):
        return super()._compute_construction_need_display()

    def _construction_covered_qty(self):
        self.ensure_one()
        return self.construction_covered_qty

    def _construction_is_remnant(self):
        self.ensure_one()
        return self.product_id.construction_is_remnant

    @api.depends('state', 'construction_need_display', 'product_id', 'move_dest_ids')
    def _compute_construction_can_cover(self):
        for move in self:
            move.construction_can_cover = bool(
                move.state not in ('done', 'cancel', 'draft')
                and move.product_id.construction_remnant_tmpl_id
                and move._construction_whole_controlled()
                and move._construction_cover_fraction() > 0)

    # ------------------------------------------------------------------
    # Cubrir con retazo (P7)
    # ------------------------------------------------------------------
    def _construction_board_raw_moves(self):
        """Componentes plancha de la orden que abastece este movimiento del
        despacho a producción."""
        self.ensure_one()
        return self.move_dest_ids.filtered(
            lambda m: m.raw_material_production_id and m.product_id == self.product_id
            and m.state != 'cancel')

    def _construction_cover_fraction(self):
        """Fracción de plancha aún sin cubrir: necesidad 7.2 → 0.2."""
        self.ensure_one()
        raw_moves = self._construction_board_raw_moves()
        uom = self.product_id.uom_id
        need = covered = 0.0
        for raw in raw_moves:
            need += raw.product_uom._compute_quantity(raw.construction_need_qty, uom, round=False)
            covered += raw.product_uom._compute_quantity(
                raw.construction_covered_qty, uom, round=False)
        net = uom.round(max(need - covered, 0.0))
        return uom.round(net - math.floor(net))

    def action_construction_cover_remnant(self):
        self.ensure_one()
        if not self.construction_can_cover:
            raise UserError(self.env._(
                'No hay fracción de %s por cubrir con retazo.', self.product_id.display_name))
        if not self.product_id.construction_sheet_area_m2:
            raise UserError(self.env._(
                'La unidad de este tablero no tiene área; asigne una unidad "Plancha L×A m".'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Cubrir con retazo'),
            'res_model': 'construction.remnant.cover.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    def action_construction_remove_remnant(self):
        """«Quitar retazo»: el retazo vuelve libre y la plancha se vuelve a
        pedir entera."""
        for move in self:
            raw = move.move_dest_ids.filtered('construction_covers_move_id')
            if move.state in ('done', 'cancel') or not raw:
                raise UserError(self.env._('Este movimiento no es un retazo por despachar.'))
            # Mismo motivo que al cubrir: el almacenero no tiene permisos de
            # Fabricación; solo se quita su retazo de esta orden.
            raw_sudo = raw.sudo()
            production_sudo = raw_sudo.raw_material_production_id
            lot = raw_sudo.construction_remnant_lot_id
            board_move = raw_sudo.construction_covers_move_id
            (move.sudo() | raw_sudo)._action_cancel()
            production_sudo._construction_round_whole_sheets()
            production_sudo._construction_sync_sheet_dispatch(board_move.product_id)
            body = self.env._(
                'Se quitó el retazo %(lot)s de [%(product)s]; la plancha se pide entera.',
                lot=lot.name, product=board_move.product_id.default_code
                or board_move.product_id.name)
            production_sudo.message_post(body=body)
            if move.picking_id:
                move.picking_id.message_post(body=body)
        return True


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_cut_closing_ids = fields.One2many(
        'construction.cut.closing.line', 'production_id', string='Sobrantes declarados')
    construction_cut_closed = fields.Boolean(
        string='Sobrantes declarados', readonly=True, copy=False)
    construction_has_whole_sheets = fields.Boolean(
        string='Con tableros en planchas enteras',
        compute='_compute_construction_has_whole_sheets')

    @api.depends('move_raw_ids.construction_need_qty')
    def _compute_construction_has_whole_sheets(self):
        for production in self:
            production.construction_has_whole_sheets = bool(
                production.move_raw_ids.filtered(
                    lambda m: m.construction_need_qty and m.state != 'cancel'))

    def _construction_sync_sheet_dispatch(self, product):
        """El despacho a producción pide lo que piden los componentes plancha
        (tras cubrir o quitar un retazo, o declarar planchas sin tocar)."""
        self.ensure_one()
        raw_moves = self.move_raw_ids.filtered(
            lambda m: m.product_id == product and not m._construction_is_remnant())
        uom = product.uom_id
        total = sum(m.product_uom._compute_quantity(m.product_uom_qty, uom, round=False)
                    for m in raw_moves if m.state != 'cancel')
        origins = raw_moves.move_orig_ids.filtered(lambda m: m.product_id == product)
        done = sum(m.product_uom._compute_quantity(m.quantity, uom, round=False)
                   for m in origins if m.state == 'done')
        open_moves = origins.filtered(lambda m: m.state not in ('done', 'cancel'))
        if not open_moves:
            return
        target = open_moves[0]
        others = sum(m.product_uom._compute_quantity(m.product_uom_qty, uom, round=False)
                     for m in open_moves[1:])
        new_qty = uom._compute_quantity(max(total - done - others, 0.0), target.product_uom,
                                        round=False)
        if target.product_uom.compare(new_qty, target.product_uom_qty) == 0:
            return
        target._do_unreserve()
        if target.product_uom.is_zero(new_qty):
            target._action_cancel()
            return
        target.product_uom_qty = new_qty
        target._action_assign()

    def _construction_cover_with_remnants(self, board_move, quants):
        """Agrega los retazos como componentes que cubren ``board_move`` y su
        movimiento en el despacho a producción, reservado con el lote."""
        self.ensure_one()
        dispatch = board_move.move_orig_ids.filtered(
            lambda m: m.state not in ('done', 'cancel'))[:1]
        for quant in quants:
            lot = quant.lot_id
            variant = quant.product_id
            vals = self._get_move_raw_values(variant, 1.0, variant.uom_id)
            vals.update({
                'construction_covers_move_id': board_move.id,
                'construction_remnant_lot_id': lot.id,
                'procure_method': 'make_to_order',
            })
            raw = self.env['stock.move'].create(vals)
            # Sin abastecimiento: su movimiento del despacho se crea aquí,
            # con el lote elegido.
            raw._action_confirm(merge=False, create_proc=False)
            picking = dispatch.picking_id
            pick_move = self.env['stock.move'].create({
                'product_id': variant.id,
                'product_uom': variant.uom_id.id,
                'product_uom_qty': 1.0,
                'location_id': quant.location_id.id,
                'location_dest_id': raw.location_id.id,
                'picking_id': picking.id,
                'picking_type_id': picking.picking_type_id.id,
                'company_id': self.company_id.id,
                'origin': self.name,
                'move_dest_ids': [Command.link(raw.id)],
                'reference_ids': [Command.set(dispatch.reference_ids.ids)],
                'construction_remnant_lot_id': lot.id,
                'construction_covers_move_id': dispatch.id,
            })
            pick_move._action_confirm(merge=False)
            # Lo reservado al confirmar puede ser otro lote: se reserva el
            # elegido.
            pick_move._do_unreserve()
            self.env['stock.move.line'].create({
                'move_id': pick_move.id,
                'picking_id': picking.id,
                'product_id': variant.id,
                'product_uom_id': variant.uom_id.id,
                'lot_id': lot.id,
                'quantity': 1.0,
                'location_id': quant.location_id.id,
                'location_dest_id': pick_move.location_dest_id.id,
            })
        self._construction_round_whole_sheets()
        self._construction_sync_sheet_dispatch(board_move.product_id)

    # ------------------------------------------------------------------
    # Declarar sobrantes (P8)
    # ------------------------------------------------------------------
    def action_construction_cut_closing(self):
        self.ensure_one()
        if not self.construction_has_whole_sheets or self.state not in ('confirmed', 'progress',
                                                                         'to_close'):
            raise UserError(self.env._(
                'Solo se declaran sobrantes en una orden confirmada o en curso con tableros '
                'en planchas enteras.'))
        if self.construction_cut_closed:
            raise UserError(self.env._('Los sobrantes de %s ya se declararon.', self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Declarar sobrantes'),
            'res_model': 'construction.cut.closing.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_production_id': self.id},
        }

    def button_mark_done(self):
        for production in self:
            if production.company_id.construction_cut_closing_required \
                    and production.construction_has_whole_sheets \
                    and not production.construction_cut_closed:
                raise UserError(self.env._(
                    'Declare los sobrantes del corte (retazos, merma y planchas sin tocar) '
                    'antes de terminar la orden.'))
        return super().button_mark_done()

    def _cal_price(self, consumed_moves):
        """El retazo sale a su costo fijo (área × costo de la plancha). Con el
        costeo por medida lo descuenta al_mrp_piece_costing; sin él, se da
        como participación del subproducto."""
        self.ensure_one()
        fixed = self.move_finished_ids.filtered(
            lambda m: m.construction_fixed_cost and m.state not in ('done', 'cancel'))
        piece_costing = self._piece_costing_active() \
            if hasattr(self, '_piece_costing_active') else False
        if fixed and not piece_costing:
            finished = self.move_finished_ids.filtered(
                lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel'))
            qty = sum(m.product_uom._compute_quantity(m.quantity, m.product_id.uom_id)
                      for m in finished)
            total = sum(consumed_moves.mapped('value')) \
                + sum(wo._cal_cost() for wo in self.workorder_ids) + self.extra_cost * qty
            if total:
                for move in fixed:
                    move.cost_share = move.construction_fixed_cost / total * 100
        res = super()._cal_price(consumed_moves)
        if fixed and not piece_costing:
            for move in fixed.filtered(lambda m: m.product_id.cost_method in ('fifo', 'average')):
                qty = move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id)
                if qty:
                    move.price_unit = move.construction_fixed_cost / qty
        return res


class ConstructionCutClosingLine(models.Model):
    """Lo que declaró el corte por tablero: base de la merma por obra."""
    _name = 'construction.cut.closing.line'
    _description = 'Sobrantes declarados del corte'
    _order = 'production_id, id'

    production_id = fields.Many2one(
        'mrp.production', string='Orden', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True, index=True)
    project_id = fields.Many2one(
        'project.project', string='Obra', compute='_compute_project_id', store=True)
    product_id = fields.Many2one('product.product', string='Tablero', required=True)
    delivered_area_m2 = fields.Float(string='Entregado (m²)', digits=(16, 4))
    pieces_area_m2 = fields.Float(string='Piezas (m²)', digits=(16, 4))
    remnant_area_m2 = fields.Float(string='Retazos (m²)', digits=(16, 4))
    scrap_area_m2 = fields.Float(string='Merma (m²)', digits=(16, 4))
    scrap_pct = fields.Float(string='Merma (%)', digits=(16, 2))
    untouched_sheets = fields.Integer(string='Planchas sin tocar')
    declared_by = fields.Many2one('res.users', string='Declarado por')
    declared_date = fields.Datetime(string='Fecha')

    @api.depends('production_id')
    def _compute_project_id(self):
        for line in self:
            production = line.production_id
            line.project_id = production.project_id if 'project_id' in production._fields \
                else False

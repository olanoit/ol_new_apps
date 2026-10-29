# -*- coding: utf-8 -*-
"""«Cubrir con retazo» (paquete 1.11, M111-12, fase B, P7): el almacenero
cubre la fracción de una plancha del despacho a producción con un retazo del
mismo tablero, libre y del área suficiente."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from ..models.remnant import REMNANT_BANDS


class ConstructionRemnantCoverWizard(models.TransientModel):
    _name = 'construction.remnant.cover.wizard'
    _description = 'Cubrir con retazo'

    move_id = fields.Many2one('stock.move', string='Movimiento de plancha', required=True,
                              readonly=True)
    picking_id = fields.Many2one(related='move_id.picking_id', string='Despacho')
    product_id = fields.Many2one(related='move_id.product_id', string='Tablero')
    production_id = fields.Many2one('mrp.production', string='Orden de corte', readonly=True)
    need_qty = fields.Float(string='Necesidad (planchas)', digits='Product Unit', readonly=True)
    fraction_to_cover = fields.Float(string='Fracción a cubrir', digits=(16, 2), readonly=True)
    area_to_cover_m2 = fields.Float(string='Área a cubrir (m²)', digits=(16, 2), readonly=True)
    line_ids = fields.One2many('construction.remnant.cover.wizard.line', 'wizard_id',
                               string='Retazos disponibles')
    fit_confirmed = fields.Boolean(
        string='Las piezas entran en los retazos elegidos (verificado con el despiece)')
    fit_required = fields.Boolean(string='Exige la verificación del despiece', readonly=True)
    result_text = fields.Char(string='Resultado', compute='_compute_result_text')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        move = self.env['stock.move'].browse(values.get('move_id'))
        if not move:
            return values
        raw_moves = move._construction_board_raw_moves()
        uom = move.product_id.uom_id
        fraction = move._construction_cover_fraction()
        area = fraction * move.product_id.construction_sheet_area_m2
        values.update({
            'production_id': raw_moves.raw_material_production_id[:1].id,
            'need_qty': sum(m.uom_id._compute_quantity(m.construction_need_qty, uom,
                                                            round=False) for m in raw_moves),
            'fraction_to_cover': fraction,
            'fit_required': move.company_id.construction_remnant_fit_required,
            'area_to_cover_m2': area,
            'line_ids': [Command.create(vals) for vals in self._remnant_lines(move, area)],
        })
        return values

    @api.model
    def _remnant_lines(self, move, area):
        """Retazos libres del tablero en el pool o en la ubicación de retazos
        de la planta, del más chico que alcance al más grande."""
        remnant_tmpl = move.product_id.construction_remnant_tmpl_id
        if not remnant_tmpl:
            return []
        warehouses = self.env['stock.warehouse'].search(
            [('company_id', '=', move.company_id.id)])
        locations = self.env['stock.location'].search([
            ('usage', 'in', ('internal', 'view')),
            ('company_id', 'in', [move.company_id.id, False]),
            '|', ('construction_remnant_pool', '=', True),
            ('id', 'in', warehouses.construction_remnant_location_id.ids)])
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', remnant_tmpl.product_variant_ids.ids),
            ('location_id', 'child_of', locations.ids),
            ('lot_id', '!=', False), ('quantity', '>', 0)])
        lines = []
        for quant in quants:
            lot = quant.lot_id
            if quant.uom_id.compare(quant.quantity - quant.reserved_quantity, 1.0) < 0:
                continue
            if lot.construction_area_m2 + 1e-6 < area:
                continue
            lines.append({
                'quant_id': quant.id,
                'lot_id': lot.id,
                'product_id': quant.product_id.id,
                'location_id': quant.location_id.id,
                'length_mm': lot.construction_length_mm,
                'width_mm': lot.construction_width_mm,
                'area_m2': lot.construction_area_m2,
                'sheet_pct': lot.construction_sheet_pct,
                'band': lot.construction_band,
                'origin_project_id': lot.construction_origin_project_id.id,
            })
        return sorted(lines, key=lambda l: l['area_m2'])

    @api.depends('line_ids.selected', 'need_qty')
    def _compute_result_text(self):
        for wizard in self:
            chosen = wizard.line_ids.filtered('selected')
            covered = sum(chosen.mapped('sheet_pct')) / 100
            product = wizard.product_id
            if not chosen or not product:
                wizard.result_text = False
                continue
            whole = product._construction_whole_qty(
                max(wizard.need_qty - covered, 0.0), wizard.move_id.company_id)
            wizard.result_text = self.env._(
                '%(sheets)s planchas + %(count)s retazo(s) (cubre %(covered)s)',
                sheets=formatLang(self.env, whole, digits=0), count=len(chosen),
                covered=formatLang(self.env, covered, digits=2))

    def action_assign(self):
        self.ensure_one()
        chosen = self.line_ids.filtered('selected')
        if not chosen:
            raise UserError(self.env._('Marque al menos un retazo.'))
        if self.fit_required and not self.fit_confirmed:
            raise UserError(self.env._(
                'Confirme que las piezas entran en los retazos elegidos (despiece).'))
        quants = chosen.quant_id
        if quants.lot_id.filtered(lambda l: l.product_id.construction_remnant_source_tmpl_id
                                  != self.product_id.product_tmpl_id):
            raise UserError(self.env._('El retazo debe ser del mismo tablero.'))
        raw_moves = self.move_id._construction_board_raw_moves()
        # El almacenero no tiene permisos de Fabricación: solo se agregan a
        # esta orden los componentes retazo que él elige y se ajusta la
        # plancha que cubren.
        production_sudo = raw_moves.raw_material_production_id[:1].sudo()
        board_move = raw_moves.sorted(lambda m: -m.construction_need_qty)[:1]
        production_sudo._construction_cover_with_remnants(board_move.sudo(), quants)
        covered = sum(chosen.mapped('sheet_pct')) / 100
        product = self.product_id
        body = self.env._(
            'Fracción %(fraction)s de [%(code)s] cubierta con el retazo %(lots)s '
            '(%(covered)s plancha) por %(user)s.',
            fraction=formatLang(self.env, self.fraction_to_cover, digits=2),
            code=product.default_code or product.name,
            lots=', '.join(quants.lot_id.mapped('name')),
            covered=formatLang(self.env, covered, digits=2), user=self.env.user.name)
        production_sudo.message_post(body=body)
        self.picking_id.message_post(body=body)
        if covered > self.need_qty:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'type': 'warning',
                'message': self.env._('Lo cubierto con retazos supera la necesidad.'),
                'next': {'type': 'ir.actions.act_window_close'},
            }}
        return {'type': 'ir.actions.act_window_close'}


class ConstructionRemnantCoverWizardLine(models.TransientModel):
    _name = 'construction.remnant.cover.wizard.line'
    _description = 'Retazo disponible'
    _order = 'area_m2, id'

    wizard_id = fields.Many2one('construction.remnant.cover.wizard', required=True,
                                ondelete='cascade')
    selected = fields.Boolean(string='Elegir')
    quant_id = fields.Many2one('stock.quant', string='Existencia')
    lot_id = fields.Many2one('stock.lot', string='Lote')
    product_id = fields.Many2one('product.product', string='Retazo')
    location_id = fields.Many2one('stock.location', string='Ubicación')
    length_mm = fields.Integer(string='Largo (mm)')
    width_mm = fields.Integer(string='Ancho (mm)')
    area_m2 = fields.Float(string='Área (m²)', digits=(16, 2))
    sheet_pct = fields.Float(string='% plancha', digits=(16, 1))
    band = fields.Selection(REMNANT_BANDS, string='Banda')
    origin_project_id = fields.Many2one('project.project', string='Obra de origen')

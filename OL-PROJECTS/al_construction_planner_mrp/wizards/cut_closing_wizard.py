# -*- coding: utf-8 -*-
"""«Declarar sobrantes» (paquete 1.11, M111-12, fase B, P8): después del
corte, producción declara por tablero los retazos (largo, ancho, cantidad) y
las planchas sin tocar; el resto es merma. Las planchas sin tocar vuelven al
stock, los retazos entran con lote y medidas a la ubicación de retazos de la
planta y su costo sale por área."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from ..models.remnant import REMNANT_BANDS, VARIANT_BANDS


class ConstructionCutClosingWizard(models.TransientModel):
    _name = 'construction.cut.closing.wizard'
    _description = 'Declarar sobrantes del corte'

    production_id = fields.Many2one('mrp.production', string='Orden de corte', required=True,
                                    readonly=True)
    line_ids = fields.One2many('construction.cut.closing.wizard.line', 'wizard_id',
                               string='Tableros')
    # Opciones de la compañía (M111-19 D).
    edit_pieces = fields.Boolean(string='Piezas editables', readonly=True)
    tolerance_pct = fields.Float(string='Tolerancia del cuadre (%)', digits=(16, 2),
                                 readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        production = self.env['mrp.production'].browse(values.get('production_id'))
        if production:
            company = production.company_id
            values.update({
                'edit_pieces': company.construction_cut_closing_edit_pieces,
                'tolerance_pct': company.construction_cut_closing_tolerance,
                'line_ids': [Command.create(vals) for vals in self._board_lines(production)],
            })
        return values

    @api.model
    def _board_lines(self, production):
        """Tableros de la orden aún sin declarar, con lo entregado. Un tablero
        sin entregar va marcado: se declara cuando llegue (M111-17)."""
        lines = []
        declared = production.construction_cut_closing_ids.product_id
        for board in production._construction_cut_boards() - declared:
            uom = board.uom_id
            area = board.construction_sheet_area_m2
            raw = production.move_raw_ids.filtered(
                lambda m: m.product_id == board and m.state != 'cancel')
            need = sum(m.uom_id._compute_quantity(m.construction_need_qty, uom, round=False)
                       for m in raw)
            # Lo que entró a la planta: hecho o reservado en el despacho.
            dispatch = raw.move_orig_ids.filtered(
                lambda m: m.product_id == board and m.state != 'cancel')
            sheets = sum(m.uom_id._compute_quantity(m.quantity, uom, round=False)
                         for m in dispatch)
            if not dispatch:
                sheets = sum(m.uom_id._compute_quantity(m.product_uom_qty, uom, round=False)
                             for m in raw)
            remnants = production.move_raw_ids.filtered(
                lambda m: m.construction_covers_move_id in raw and m.state != 'cancel')
            remnant_area = sum(remnants.construction_remnant_lot_id.mapped('construction_area_m2'))
            lines.append({
                'product_id': board.id,
                'sheet_area_m2': area,
                'delivered_sheets': sheets,
                'delivered_remnant_area_m2': remnant_area,
                'undelivered': uom.is_zero(sheets) and not remnant_area,
                # Sin despiece cargado (M19-01), las piezas son la necesidad.
                'pieces_area_m2': need * area,
                'pieces_area_computed_m2': need * area,
            })
        return lines

    def action_confirm(self):
        self.ensure_one()
        production = self.production_id
        if production.construction_cut_closed:
            raise UserError(self.env._('Los sobrantes de %s ya se declararon.', production.name))
        lines = self.line_ids.filtered(lambda l: not l.undelivered)
        if not lines:
            raise UserError(self.env._(
                'Ningún tablero de %s se entregó todavía: los sobrantes se declaran cuando '
                'llegue.', production.name))
        for line in lines:
            line._check_balance()
        notes = []
        for line in lines:
            notes += line._pieces_note()
            notes += line._apply(production)
        pending = production._construction_cut_boards() - production.construction_cut_closing_ids.product_id
        if not pending:
            production.construction_cut_closed = True
        else:
            notes.append(self.env._(
                'Sin entregar, se declaran cuando lleguen: %s.',
                ', '.join(pending.mapped(lambda p: p.default_code or p.name))))
        body = self.env._('Sobrantes del corte declarados por %s.', self.env.user.name)
        if notes:
            body += ' ' + ' '.join(notes)
        production.message_post(body=body)
        return {'type': 'ir.actions.act_window_close'}


class ConstructionCutClosingWizardLine(models.TransientModel):
    _name = 'construction.cut.closing.wizard.line'
    _description = 'Sobrantes por tablero'

    wizard_id = fields.Many2one('construction.cut.closing.wizard', required=True,
                                ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Tablero')
    sheet_area_m2 = fields.Float(string='Área de la plancha (m²)', digits=(16, 4))
    delivered_sheets = fields.Float(string='Planchas entregadas', digits='Product Unit')
    delivered_remnant_area_m2 = fields.Float(string='Retazos entregados (m²)', digits=(16, 2))
    delivered_area_m2 = fields.Float(
        string='Entregado (m²)', digits=(16, 2), compute='_compute_balance')
    pieces_area_m2 = fields.Float(string='Piezas (m²)', digits=(16, 2))
    pieces_area_computed_m2 = fields.Float(string='Piezas calculadas (m²)', digits=(16, 2))
    undelivered = fields.Boolean(string='Sin entregar', readonly=True)
    untouched_sheets = fields.Integer(string='Planchas sin tocar')
    remnant_ids = fields.One2many('construction.cut.closing.remnant', 'line_id',
                                  string='Retazos')
    remnant_area_m2 = fields.Float(
        string='Retazos (m²)', digits=(16, 2), compute='_compute_balance')
    scrap_area_m2 = fields.Float(string='Merma (m²)', digits=(16, 2), compute='_compute_balance')
    scrap_pct = fields.Float(string='Merma (%)', digits=(16, 1), compute='_compute_balance')
    balance_ok = fields.Boolean(string='Cuadra', compute='_compute_balance')
    balance_text = fields.Char(string='Cuadre', compute='_compute_balance')

    @api.depends('delivered_sheets', 'delivered_remnant_area_m2', 'sheet_area_m2',
                 'pieces_area_m2', 'untouched_sheets', 'remnant_ids.area_m2',
                 'remnant_ids.qty', 'remnant_ids.band', 'undelivered',
                 'wizard_id.tolerance_pct')
    def _compute_balance(self):
        for line in self:
            if line.undelivered:
                line.update({
                    'delivered_area_m2': 0.0, 'remnant_area_m2': 0.0, 'scrap_area_m2': 0.0,
                    'scrap_pct': 0.0, 'balance_ok': True,
                    'balance_text': self.env._('Sin entregar: se declara cuando llegue'),
                })
                continue
            delivered = line.delivered_sheets * line.sheet_area_m2 + line.delivered_remnant_area_m2
            kept = line.remnant_ids.filtered(lambda r: r.band in VARIANT_BANDS)
            remnant = sum(r._exact_area() * r.qty for r in kept)
            whole = sum(r.qty for r in line.remnant_ids if r.band == 'whole')
            untouched = (line.untouched_sheets + whole) * line.sheet_area_m2
            scrap = delivered - line.pieces_area_m2 - remnant - untouched
            line.delivered_area_m2 = delivered
            line.remnant_area_m2 = remnant
            line.scrap_area_m2 = scrap
            line.scrap_pct = scrap / delivered * 100 if delivered else 0.0
            tolerance = line.wizard_id.tolerance_pct / 100
            line.balance_ok = scrap >= -tolerance * delivered
            if line.balance_ok:
                line.balance_text = self.env._(
                    '%(pieces)s + %(remnant)s + %(untouched)s + %(scrap)s = %(delivered)s ✓',
                    pieces=formatLang(self.env, line.pieces_area_m2, digits=2),
                    remnant=formatLang(self.env, remnant, digits=2),
                    untouched=formatLang(self.env, untouched, digits=2),
                    scrap=formatLang(self.env, scrap, digits=2),
                    delivered=formatLang(self.env, delivered, digits=2))
            else:
                line.balance_text = self.env._(
                    '⚠ Lo declarado supera lo entregado en %s m²',
                    formatLang(self.env, -scrap, digits=2))

    def _check_balance(self):
        for line in self:
            if line.untouched_sheets < 0 or any(r.qty <= 0 or r.length_mm <= 0
                                                or r.width_mm <= 0 for r in line.remnant_ids):
                raise UserError(self.env._(
                    'Revise %s: las medidas, cantidades y planchas sin tocar son positivas.',
                    line.product_id.display_name))
            if not line.balance_ok:
                raise UserError(self.env._(
                    'Lo declarado (piezas + retazos + planchas sin tocar) supera lo entregado '
                    'en %(area)s m² en %(product)s.',
                    area=formatLang(self.env, -line.scrap_area_m2, digits=2),
                    product=line.product_id.display_name))

    def _pieces_note(self):
        """Historial de la orden: quien corrigió el área de las piezas."""
        self.ensure_one()
        if not self.wizard_id.edit_pieces or abs(
                self.pieces_area_m2 - self.pieces_area_computed_m2) < 0.005:
            return []
        return [self.env._(
            '%(user)s corrigió las piezas de [%(code)s]: de %(old)s a %(new)s m².',
            user=self.env.user.name, code=self.product_id.default_code or self.product_id.name,
            old=formatLang(self.env, self.pieces_area_computed_m2, digits=2),
            new=formatLang(self.env, self.pieces_area_m2, digits=2))]

    def _apply(self, production):
        """Consumo, devolución de planchas sin tocar, retazos como
        subproductos y registro del cuadre. Devuelve avisos para el
        historial."""
        self.ensure_one()
        board = self.product_id
        notes = []
        untouched = self.untouched_sheets + sum(
            r.qty for r in self.remnant_ids if r.band == 'whole')
        scrap_remnants = self.remnant_ids.filtered(lambda r: r.band == 'r10')
        if scrap_remnants:
            notes.append(self.env._(
                '%(count)s sobrante(s) de [%(code)s] con 10 %% o menos de plancha se toman '
                'como merma.', count=sum(scrap_remnants.mapped('qty')),
                code=board.default_code or board.name))
        if untouched:
            self._consume_less(production, untouched)
            self._return_untouched(production, untouched)
        kept = self.remnant_ids.filtered(lambda r: r.band in VARIANT_BANDS)
        if kept:
            self._create_remnants(production, kept)
        # El jefe de producción («Fabricación: Usuario») solo lee el registro
        # del cierre (M111-14): lo escribe el asistente, como las demás
        # operaciones del cierre.
        self.env['construction.cut.closing.line'].sudo().create({
            'production_id': production.id,
            'product_id': board.id,
            'delivered_area_m2': self.delivered_area_m2,
            'pieces_area_m2': self.pieces_area_m2,
            'remnant_area_m2': sum(r._exact_area() * r.qty for r in kept),
            'scrap_area_m2': self.scrap_area_m2,
            'scrap_pct': self.scrap_pct,
            'untouched_sheets': untouched,
            'declared_by': self.env.user.id,
            'declared_date': fields.Datetime.now(),
        })
        return notes

    def _board_raw_moves(self, production):
        return production.move_raw_ids.filtered(
            lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel')
            and not m._construction_is_remnant())

    def _consume_less(self, production, untouched):
        """El consumo de la plancha queda en entregado − planchas sin tocar:
        se descuenta del componente con más necesidad."""
        uom = self.product_id.uom_id
        delta = float(untouched)
        for move in self._board_raw_moves(production).sorted(
                lambda m: -m.construction_need_qty):
            own = move.uom_id._compute_quantity(move.product_uom_qty, uom, round=False)
            take = min(own, delta)
            delta -= take
            move.product_uom_qty = uom._compute_quantity(own - take, move.uom_id,
                                                         round=False)
            if move.picked or not move.uom_id.is_zero(move.quantity):
                move.quantity = move.product_uom_qty
            if not delta:
                break

    def _return_untouched(self, production, untouched):
        """Devolución del despacho a producción: de la preproducción al
        origen. Si el despacho aún no se hizo, se pide menos."""
        dispatch = self._board_raw_moves(production).move_orig_ids.filtered(
            lambda m: m.product_id == self.product_id)
        done = dispatch.filtered(lambda m: m.state == 'done')
        if not done:
            production._construction_sync_sheet_dispatch(self.product_id)
            return
        picking = done[0].picking_id
        # Odoo 20: la devolución es un albarán borrador que se ajusta.
        returned = picking._create_return()
        for move in returned.move_ids:
            if move.origin_returned_move_id == done[0]:
                move.product_uom_qty = untouched
            else:
                move.unlink()
        returned.action_confirm()
        returned.action_assign()
        returned.message_post(body=self.env._(
            'Planchas sin tocar de %s: vuelven al stock.', production.name))

    def _create_remnants(self, production, remnants):
        """Cada retazo es un subproducto de la orden, en la variante de su
        banda, con un lote por unidad y su costo por área."""
        board = self.product_id
        if not board.construction_remnant_tmpl_id:
            # Producción no crea productos (M111-14): el retazo del tablero es
            # una plantilla técnica que el asistente crea la primera vez.
            board.product_tmpl_id.sudo().action_construction_create_remnant()
        warehouse = production.picking_type_id.warehouse_id
        unit_cost = board.with_company(production.company_id).standard_price
        project = production.project_id if 'project_id' in production._fields \
            else self.env['project.project']
        Lot = self.env['stock.lot']
        company = production.company_id
        code = board.default_code or str(board.id)
        site = (getattr(project, 'construction_code', False) or project.name or '') \
            if project else ''
        sequence = Lot.search_count([
            ('product_id', 'in', board.construction_remnant_tmpl_id.product_variant_ids.ids)])
        for band in VARIANT_BANDS:
            of_band = remnants.filtered(lambda r: r.band == band)
            if not of_band:
                continue
            variant = board._construction_remnant_variant(band)
            qty = sum(of_band.mapped('qty'))
            cost = sum(r._exact_area() * r.qty for r in of_band) * unit_cost / self.sheet_area_m2 \
                if self.sheet_area_m2 else 0.0
            vals = production._get_move_finished_values(
                variant.id, qty, variant.uom_id.id)
            destination = warehouse._construction_remnant_destination(band) \
                or production.location_dest_id
            vals.update({
                'location_dest_id': destination.id,
                'construction_fixed_cost': cost,
                # Odoo 20 retiró manual_consumption: la cantidad se marca
                # como tomada (picked) al validar el corte.
            })
            move = self.env['stock.move'].create(vals)
            move._action_confirm(merge=False)
            # La salida de producción se «reserva» sin lote al confirmar: se
            # reemplaza por una línea por retazo, cada una con su lote.
            move.move_line_ids.unlink()
            line_vals = []
            for remnant in of_band:
                for _unit in range(remnant.qty):
                    sequence += 1
                    lot = Lot.create({
                        'name': company._construction_remnant_lot_name({
                            'codigo': code, 'banda': band.upper(),
                            'largo': remnant.length_mm, 'ancho': remnant.width_mm,
                            'numero': '%04d' % sequence, 'obra': site,
                            'orden': production.name}),
                        'product_id': variant.id,
                        'company_id': production.company_id.id,
                        'construction_length_mm': remnant.length_mm,
                        'construction_width_mm': remnant.width_mm,
                        'construction_origin_production_id': production.id,
                        'construction_origin_project_id': project.id,
                    })
                    line_vals.append({
                        'move_id': move.id,
                        'company_id': production.company_id.id,
                        'product_id': variant.id,
                        'uom_id': variant.uom_id.id,
                        'lot_id': lot.id,
                        'quantity': 1.0,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })
            self.env['stock.move.line'].create(line_vals)
            move.picked = True


class ConstructionCutClosingRemnant(models.TransientModel):
    _name = 'construction.cut.closing.remnant'
    _description = 'Retazo declarado'

    line_id = fields.Many2one('construction.cut.closing.wizard.line', required=True,
                              ondelete='cascade')
    length_mm = fields.Integer(string='Largo (mm)')
    width_mm = fields.Integer(string='Ancho (mm)')
    qty = fields.Integer(string='Cant.', default=1)
    area_m2 = fields.Float(string='Área (m²)', digits=(16, 2), compute='_compute_measures')
    sheet_pct = fields.Float(string='% plancha', digits=(16, 1), compute='_compute_measures')
    band = fields.Selection(REMNANT_BANDS, string='Banda', compute='_compute_measures')

    def _exact_area(self):
        """Área sin el redondeo de la columna (el costo y el cuadre)."""
        self.ensure_one()
        return self.length_mm * self.width_mm / 1e6

    @api.depends('length_mm', 'width_mm', 'line_id.sheet_area_m2')
    def _compute_measures(self):
        for remnant in self:
            area = remnant._exact_area()
            sheet = remnant.line_id.sheet_area_m2
            pct = area / sheet * 100 if sheet else 0.0
            remnant.area_m2 = area
            remnant.sheet_pct = pct
            company = remnant.line_id.wizard_id.production_id.company_id or self.env.company
            remnant.band = company._construction_band(pct) if area and sheet else False

# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Domain

# Datos de la ficha que vienen de módulos opcionales de la suite (controlados,
# DIGEMID…): se muestran si el campo existe.
OPTIONAL_INFO_FIELDS = [
    ('pharmacy_control_list', None), ('pharmacy_digemid_code', None), ('pharmacy_igv_regime', None),
]


class PharmacyIngredient(models.Model):
    """Principios activos en la caja: filtro y búsqueda del catálogo."""
    _name = 'pharmacy.ingredient'
    _inherit = ['pharmacy.ingredient', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        # Odoo 20: sin argumento config; la configuración va en data['pos.config'].
        config = data['pos.config']
        # Solo los que llevan los productos cargados (dominio sobre esos productos).
        ingredient_ids = {ingredient_id for template in data['product.template']
                          for ingredient_id in template.get('pharmacy_ingredient_ids') or []}
        return [('id', 'in', list(ingredient_ids))]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'name', 'synonyms', 'atc_code']


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pharmacy_ingredient_ids = fields.Many2many(
        'pharmacy.ingredient', string='Principios activos', compute='_compute_pharmacy_ingredient_ids',
        help='Principios activos de la composición (para filtrar y buscar en la caja).')

    @api.depends('pharmacy_ingredient_line_ids.ingredient_id')
    def _compute_pharmacy_ingredient_ids(self):
        for template in self:
            template.pharmacy_ingredient_ids = template.pharmacy_ingredient_line_ids.ingredient_id

    @api.model
    def _load_pos_data_search_read(self, data, config):
        """Como los productos opcionales del TPV: los bioequivalentes vinculados
        se cargan aunque no entren en el límite de productos, para ofrecerlos
        y cambiarlos en el pedido sin ir al servidor."""
        result = super()._load_pos_data_search_read(data, config)
        loaded = {template['id'] for template in result}
        missing = {template_id for template in result
                   for template_id in template.get('pharmacy_bioequivalent_ids') or []} - loaded
        if missing:
            domain = Domain(self._load_pos_data_domain(data, config)) & Domain('id', 'in', list(missing))
            result += self._load_pos_data_read(self._load_product_with_domain(domain), config)
        return result

    @api.model
    def load_product_from_pos(self, config_id, domain, offset=0, limit=0):
        """Los productos que el TPV carga después (búsqueda, código de barras)
        llegan también con sus presentaciones y sus principios activos."""
        result = super().load_product_from_pos(config_id, domain, offset=offset, limit=limit)
        templates = result.get('product.template', [])
        if templates:
            config = self.env['pos.config'].browse(config_id)
            Presentation = self.env['pharmacy.presentation']
            presentations = Presentation.search([('product_tmpl_id', 'in', [t['id'] for t in templates])])
            result['pharmacy.presentation'] = Presentation._load_pos_data_read(presentations, config)
            Ingredient = self.env['pharmacy.ingredient']
            ingredients = Ingredient.search(Ingredient._load_pos_data_domain({'product.template': templates}, config))
            result['pharmacy.ingredient'] = Ingredient._load_pos_data_read(ingredients, config)
        return result

    # ------------------------------------------------------------------
    # Ficha del producto en la caja
    # ------------------------------------------------------------------
    def get_product_info_pos(self, price, quantity, pos_config_id, product_variant_id=False):
        result = super().get_product_info_pos(price, quantity, pos_config_id,
                                              product_variant_id=product_variant_id)
        if self.pharmacy_ok:
            config = self.env['pos.config'].browse(pos_config_id)
            result['pharmacy'] = self._pharmacy_pos_info(config)
        return result

    def _pharmacy_selection(self, fname):
        if fname not in self._fields or not self[fname]:
            return ''
        return dict(self._fields[fname]._description_selection(self.env)).get(self[fname], '')

    def _pharmacy_pos_info(self, config):
        """Información farmacéutica de la ficha del TPV: condición de venta,
        composición, registro, almacenamiento, presentaciones, lotes por
        vencimiento (FEFO) y equivalentes con precio y existencias."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        rows = [
            ('Principio activo', self.pharmacy_composition),
            ('Forma farmacéutica', self.pharmacy_dosage_form_id.name),
            ('Vía de administración', self.pharmacy_route_id.name),
            ('Tipo', self._pharmacy_selection('pharmacy_product_type')),
            ('Laboratorio', self.pharmacy_laboratory_id.name),
            ('Titular del registro', self.pharmacy_registry_holder_id.name),
            ('Registro sanitario', ' · '.join(filter(None, [
                self.pharmacy_sanitary_registry,
                self.pharmacy_registry_expiry and 'vence %s' % self.pharmacy_registry_expiry.strftime('%d/%m/%Y')]))),
            ('Código DIGEMID', self['pharmacy_digemid_code'] if 'pharmacy_digemid_code' in self._fields else ''),
            ('Lista de control', self._pharmacy_selection('pharmacy_control_list')),
            ('IGV', self._pharmacy_selection('pharmacy_igv_regime')),
            ('Almacenamiento', self.pharmacy_storage_conditions),
            ('Ubicación en estante', self.pharmacy_shelf),
        ]
        badges = [{'kind': self.pharmacy_sale_condition or 'otc',
                   'label': self._pharmacy_selection('pharmacy_sale_condition')}]
        if self.pharmacy_cold_chain:
            badges.append({'kind': 'cold', 'label': 'Cadena de frío'})
        if self.pharmacy_product_type == 'generic_dci':
            badges.append({'kind': 'generic', 'label': 'Genérico'})
        if self.pharmacy_bioequivalent:
            badges.append({'kind': 'bioequivalent', 'label': 'Equivalencia terapéutica demostrada'})
        # Quien atiende la caja no necesariamente lee lotes ni existencias de
        # inventario: solo se devuelven nombre, vencimiento y cantidad.
        location = config.picking_type_id.default_location_src_id
        quants_sudo = self.env['stock.quant'].sudo().search([
            ('product_id', 'in', self.product_variant_ids.ids), ('location_id', 'child_of', location.id),
            ('quantity', '>', 0), ('lot_id', '!=', False)]) if location else self.env['stock.quant']
        lots = {}
        for quant in quants_sudo:
            lot = quant.lot_id
            entry = lots.setdefault(lot.id, {
                'name': lot.name, 'quantity': 0.0, 'state': lot.pharmacy_state,
                'expiration': lot.expiration_date and fields.Date.context_today(self, lot.expiration_date),
            })
            entry['quantity'] += quant.quantity
        lot_list = sorted(lots.values(), key=lambda lot: lot['expiration'] or fields.Date.to_date('9999-12-31'))
        for lot in lot_list:
            days = (lot['expiration'] - today).days if lot['expiration'] else None
            lot.update(expiration=lot['expiration'] and lot['expiration'].strftime('%d/%m/%Y'), days=days,
                       near=days is not None and days <= 90, expired=days is not None and days < 0)
        equivalents = []
        for template in self.pharmacy_equivalent_ids.filtered(lambda t: t.available_in_pos and t.active)[:8]:
            variant = template.product_variant_id
            equivalents.append({
                'id': template.id, 'name': template.display_name, 'price': template.list_price,
                'type': template._pharmacy_selection('pharmacy_product_type'),
                'bioequivalent': template.pharmacy_bioequivalent or template in self.pharmacy_bioequivalent_ids,
                'qty': sum(self.env['stock.quant'].sudo().search([
                    ('product_id', '=', variant.id), ('location_id', 'child_of', location.id)]).mapped('quantity'))
                if location else 0,
            })
        equivalents.sort(key=lambda e: e['price'])
        return {
            'badges': badges,
            'rows': [{'label': label, 'value': value} for label, value in rows if value],
            'presentations': [{'name': p.name, 'factor': p.factor, 'price': p.price}
                              for p in self.pharmacy_presentation_ids.sorted(lambda p: (p.sequence, p.factor))],
            'lots': lot_list,
            'equivalents': equivalents,
            'texts': [{'label': label, 'value': value} for label, value in (
                ('Indicaciones', self.pharmacy_indications),
                ('Contraindicaciones', self.pharmacy_contraindications),
                ('Efectos adversos', self.pharmacy_adverse_effects)) if value],
        }

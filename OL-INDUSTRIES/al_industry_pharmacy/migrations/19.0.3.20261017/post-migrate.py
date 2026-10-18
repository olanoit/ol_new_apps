# -*- coding: utf-8 -*-
"""v3: los datos farmacéuticos del producto pasan a al_pharmacy_base.

El registro sanitario y la condición de venta conservan su columna (mismo
nombre de campo). El principio activo, la concentración y la forma
farmacéutica, que eran texto libre, se convierten en la composición
(principio activo + concentración) y en la forma del catálogo. Las columnas
viejas las borra Odoo al terminar la actualización.
"""
import logging
import re

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

UNITS = {'mg': 'mg', 'g': 'g', 'mcg': 'mcg', 'µg': 'mcg', 'ui': 'ui', 'ml': 'ml', '%': 'percent',
         'mg/ml': 'mg_ml', 'mg/5ml': 'mg_5ml', 'ui/ml': 'ui'}


def _parse_strength(text):
    match = re.match(r'\s*([\d.,]+)\s*(.*)$', text or '')
    if not match:
        return 0.0, 'mg'
    value = float(match.group(1).replace(',', '.'))
    unit = UNITS.get(match.group(2).replace(' ', '').lower(), 'mg')
    return value, unit


def migrate(cr, version):
    cr.execute(SQL("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'product_template'
           AND column_name IN ('pharmacy_active_ingredient', 'pharmacy_concentration',
                               'pharmacy_dosage_form')
    """))
    columns = {row[0] for row in cr.fetchall()}
    if 'pharmacy_active_ingredient' not in columns:
        return
    cr.execute(SQL("""
        SELECT id, pharmacy_active_ingredient,
               %s, %s
          FROM product_template
         WHERE pharmacy_active_ingredient IS NOT NULL OR pharmacy_sale_condition IS NOT NULL
    """, SQL.identifier('pharmacy_concentration') if 'pharmacy_concentration' in columns else SQL('NULL'),
        SQL.identifier('pharmacy_dosage_form') if 'pharmacy_dosage_form' in columns else SQL('NULL')))
    rows = cr.fetchall()
    env = api.Environment(cr, SUPERUSER_ID, {'active_test': False})
    Ingredient = env['pharmacy.ingredient']
    Form = env['pharmacy.dosage.form']
    for template_id, ingredient_name, concentration, form_name in rows:
        template = env['product.template'].browse(template_id)
        vals = {'pharmacy_ok': True}
        if form_name and not template.pharmacy_dosage_form_id:
            form = Form.search([('name', '=ilike', form_name.strip())], limit=1) \
                or Form.create({'name': form_name.strip().capitalize()})
            vals['pharmacy_dosage_form_id'] = form.id
        if ingredient_name and not template.pharmacy_ingredient_line_ids:
            strength, unit = _parse_strength(concentration)
            vals['pharmacy_ingredient_line_ids'] = [(0, 0, {
                'ingredient_id': Ingredient._get_or_create(ingredient_name).id,
                'strength': strength, 'strength_unit': unit,
            })]
        template.write(vals)
    _logger.info('al_industry_pharmacy: %s productos con datos farmacéuticos migrados', len(rows))

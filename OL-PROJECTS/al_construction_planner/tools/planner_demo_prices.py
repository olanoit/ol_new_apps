# -*- coding: utf-8 -*-
"""Datos demo de la fase 9 (precios y abastecimiento) sobre «DEMO PLAN
MOMEN-35-26».

Requiere haber ejecutado antes ``planner_demo_data.py`` y
``planner_demo_baseline.py``. Deja (todo ficticio):

- 27 compras confirmadas de «DEMO PLAN Melamina MDP blanco fantasía» entre
  el 10/04 y el 10/10/2026, como el ejemplo de P-16: 24 en dólares a
  «DEMO PLAN Novopan» (US$ 34.20 a 35.91 y una a US$ 42.37) y 3 en soles a
  otros proveedores (7 planchas a S/ 174.50, 64 a S/ 162.00 y 96 a
  S/ 165.00). Usa el tipo de cambio de Odoo de cada fecha; si falta, crea
  uno de ejemplo;
- una compra de «DEMO PLAN Melamina coñac» a S/ 196.00 (sobre el costo del
  plan: alerta en P-18) y 40 planchas de melamina blanca en el almacén
  central;
- la familia «DEMO PLAN Herrajes» con el código 3105 y la bisagra del demo
  con el código 3105001 (para «Crear producto desde el plan»).

Idempotente (si ya hay compras de «DEMO PLAN Novopan» no hace nada).
Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_prices.py
"""
from datetime import date, datetime, timedelta

from odoo import Command

P = 'DEMO PLAN'
env = env(user=env.ref('base.user_admin'))
project = env['project.project'].search([('name', '=', f'{P} MOMEN-35-26')], limit=1)
assert project, 'Ejecute antes planner_demo_data.py'
plan = project._construction_current_plan()
company = plan.company_id or env.company
env = env(context=dict(env.context, allowed_company_ids=company.ids))
Product = env['product.product']
white = Product.search([('name', '=', f'{P} Melamina MDP blanco fantasía')], limit=1)
cognac = Product.search([('name', '=', f'{P} Melamina coñac')], limit=1)
hinge = Product.search([('name', '=', f'{P} Bisagra lateral Danco')], limit=1)
assert white and cognac, 'Ejecute antes planner_demo_data.py'
Partner = env['res.partner']


def partner(name):
    return Partner.search([('name', '=', name)], limit=1) or Partner.create({'name': name})


novopan = partner(f'{P} Novopan Perú S.A.C.')
if env['purchase.order'].search_count([('partner_id', '=', novopan.id)]):
    print('Ya hay compras demo de precios: no se hace nada.')
else:
    usd = env.ref('base.USD')
    usd.active = True
    Rate = env['res.currency.rate']

    def ensure_rate(day, value):
        if not Rate.search_count([('currency_id', '=', usd.id), ('name', '=', day),
                                  ('company_id', 'in', [False, company.root_id.id])]):
            Rate.create({'currency_id': usd.id, 'name': day, 'company_id': company.root_id.id,
                         'inverse_company_rate': value})

    def purchase(vendor, product, qty, price, day, currency=None):
        order = env['purchase.order'].create({
            'partner_id': vendor.id,
            'company_id': company.id,
            'currency_id': (currency or company.currency_id).id,
            'origin': f'{P} precios',
            'order_line': [Command.create({
                'product_id': product.id, 'product_qty': qty, 'price_unit': price})],
        })
        order.button_confirm()
        order.date_approve = datetime.combine(day, datetime.min.time()) + timedelta(hours=15)
        return order

    start = date(2026, 4, 10)
    usd_prices = [34.20, 34.35, 34.50, 34.80, 34.95, 35.10, 35.25, 35.40, 35.55, 35.70,
                  42.37, 35.91, 35.60, 35.40, 35.20, 35.10, 34.95, 35.05, 35.20, 35.35,
                  35.50, 35.60, 35.75, 35.91]
    for i, price in enumerate(usd_prices):
        day = start + timedelta(days=7 * i + (i % 3))
        ensure_rate(day, 3.36 + (i % 5) * 0.03)
        purchase(novopan, white, 320 + (i % 4) * 64, price, day, currency=usd)
    purchase(partner(f'{P} Mavicch S.A.C.'), white, 7, 174.50, date(2026, 5, 28))
    purchase(partner(f'{P} Carpicentro S.A.C.'), white, 64, 162.00, date(2026, 6, 11))
    purchase(partner(f'{P} Soc. Import. de Prod. Ferreteros'), white, 96, 165.00,
             date(2026, 6, 11))
    purchase(partner(f'{P} Carpicentro S.A.C.'), cognac, 30, 196.00, date(2026, 10, 5))

    white.is_storable = True
    location = company.construction_src_location_id
    if location:
        env['stock.quant']._update_available_quantity(white, location, 40.0)

    family = env['product.category'].search([('name', '=', f'{P} Herrajes')], limit=1) \
        or env['product.category'].create({'name': f'{P} Herrajes'})
    family.construction_family_code = '3105'
    if hinge and not hinge.default_code:
        hinge.write({'default_code': '3105001', 'categ_id': family.id})
    env.cr.commit()
    print('Compras demo de precios creadas.')

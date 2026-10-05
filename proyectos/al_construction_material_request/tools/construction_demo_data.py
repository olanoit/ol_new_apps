# -*- coding: utf-8 -*-
"""Datos demo de requerimientos de obra para la ficha y las pruebas manuales
(prefijo DEMO RQO; todo ficticio). Idempotente: no toca datos que no sean DEMO.

Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < construction_demo_data.py
"""
P = 'DEMO RQO'
company = env.company
admin = env.ref('base.user_admin')
company._al_construction_ensure_setup()
central = company.construction_src_location_id


def get_or_create(model, domain, vals):
    return env[model].search(domain, limit=1) or env[model].create(vals)


print('=== Analítica ===')
plans = {}
for key, name in (('disc', 'Disciplina'), ('part', 'Partida')):
    plans[key] = get_or_create('account.analytic.plan', [('name', '=', f'{P} {name}')],
                               {'name': f'{P} {name}'})
acc = {}
for key, plan, name in (('estr', 'disc', 'Estructuras'), ('arq', 'disc', 'Arquitectura'),
                        ('conc', 'part', '02.01 Concreto simple'),
                        ('alba', 'part', '03.01 Muros de albañilería')):
    acc[key] = get_or_create('account.analytic.account', [('name', '=', f'{P} {name}')],
                             {'name': f'{P} {name}', 'plan_id': plans[plan].id})


def dist(*keys):
    return {','.join(str(acc[k].id) for k in keys): 100}


print('=== Ubicaciones por familia ===')
loc = {}
for key, name in (('cem', 'Cementos'), ('fie', 'Fierros')):
    loc[key] = get_or_create('stock.location', [('name', '=', f'{P} {name}'),
                                                ('location_id', '=', central.id)],
                             {'name': f'{P} {name}', 'usage': 'internal',
                              'location_id': central.id})

print('=== Materiales y existencias ===')
uom = {k: env.ref(f'uom.{x}') for k, x in (('u', 'product_uom_unit'),
                                           ('m3', 'product_uom_cubic_meter'),
                                           ('kg', 'product_uom_kgm'))}
products = {}
for key, name, u, cost, location, qty in (
        ('cem', 'Cemento Portland tipo I, bolsa 42.5 kg', 'u', 29.50, loc['cem'], 60),
        ('fie', 'Fierro corrugado 1/2" x 9 m', 'u', 46.00, loc['fie'], 200),
        ('are', 'Arena gruesa', 'm3', 65.00, central, 5),
        ('lad', 'Ladrillo King Kong 18 huecos', 'u', 1.10, central, 0),
        ('cla', 'Clavo para madera 3"', 'kg', 6.80, central, 50)):
    product = env['product.product'].search([('name', '=', f'{P} {name}')], limit=1)
    if not product:
        product = env['product.product'].create({
            'name': f'{P} {name}', 'type': 'consu', 'is_storable': True,
            'uom_id': uom[u].id, 'standard_price': cost})
        if qty:
            env['stock.quant']._update_available_quantity(product, location, qty)
    products[key] = product

print('=== Usuarios, obras y reglas de aprobación ===')
grp = 'al_construction_material_request.group_construction_'
residente = env['res.users'].search([('login', '=', 'demo_rqo_residente')]) or \
    env['res.users'].create({
        'name': f'{P} Residente de obra', 'login': 'demo_rqo_residente', 'lang': 'es_419',
        'group_ids': [(6, 0, [env.ref(f'{grp}requester').id])]})
gerente = env['res.users'].search([('login', '=', 'demo_rqo_gerente')]) or \
    env['res.users'].create({
        'name': f'{P} Gerente de operaciones', 'login': 'demo_rqo_gerente', 'lang': 'es_419',
        'group_ids': [(6, 0, [env.ref(f'{grp}operations_manager').id])]})
sites = {}
for key, name in (('a', 'Colegio A'), ('b', 'Posta médica B')):
    sites[key] = get_or_create('project.project', [('name', '=', f'{P} {name}')], {
        'name': f'{P} {name}', 'is_construction_site': True, 'user_id': admin.id})
    sites[key].message_subscribe(partner_ids=residente.partner_id.ids)

model = env['ir.model']._get('construction.material.request')
get_or_create('tier.definition', [('name', '=', f'{P} Nivel 1: jefe de proyecto de la obra')], {
    'name': f'{P} Nivel 1: jefe de proyecto de la obra', 'model_id': model.id,
    'review_type': 'field',
    'reviewer_field_id': env['ir.model.fields']._get(
        'construction.material.request', 'project_manager_id').id,
    'definition_domain': "[('project_manager_id', '!=', False)]",
    'sequence': 20, 'approve_sequence': True, 'notify_on_create': True})
get_or_create('tier.definition', [('name', '=', f'{P} Nivel 2: gerencia (más de S/ 10 000)')], {
    'name': f'{P} Nivel 2: gerencia (más de S/ 10 000)', 'model_id': model.id,
    'review_type': 'group', 'reviewer_group_id': env.ref(f'{grp}operations_manager').id,
    'definition_domain': "[('amount_estimated', '>', 10000)]",
    'sequence': 10, 'approve_sequence': True, 'notify_on_create': True})
vendor = get_or_create('res.partner', [('name', '=', f'{P} Distribuidora de materiales')],
                       {'name': f'{P} Distribuidora de materiales', 'is_company': True})

print('=== Requerimientos ===')
Request = env['construction.material.request']


def request(key, site, lines, **vals):
    """``lines``: (producto, cantidad, analítica, modo)."""
    marker = f'{P} {key}'
    found = Request.search([('note', 'ilike', marker)], limit=1)
    if found:
        return found, False
    rec = Request.with_user(residente).create({
        'project_id': sites[site].id,
        'note': f'<p>{marker}: {vals.pop("texto")}</p>',
        'line_ids': [(0, 0, {'product_id': products[p].id, 'product_qty': q,
                             'analytic_distribution': d, 'supply_mode': m})
                     for p, q, d, m in lines],
        **vals,
    })
    return rec.with_env(env), True


def approve(rec):
    rec.with_user(residente).action_request_approval()
    if rec.state == 'to_approve':
        rec.with_user(admin)._validate_tier()


# 1. Borrador: ladrillo sin stock y clavos con stock
r1, _new = request('borrador', 'a', [
    ('lad', 2000, dist('arq', 'alba'), 'direct'),
    ('cla', 10, dist('arq', 'alba'), 'central')],
    texto='Muros del segundo piso.', priority='1', date_required='2026-10-10')

# 2. En aprobación, dos niveles: 400 bolsas = S/ 11 800
r2, new = request('aprobacion', 'b', [('cem', 400, dist('estr', 'conc'), 'central')],
                  texto='Vaciado de losa del bloque B.', date_required='2026-10-20')
if new:
    r2.with_user(residente).action_request_approval()
    r2.with_user(admin)._validate_tier()  # nivel 1 aprobado; queda la gerencia

# 3. El caso de las 100 bolsas con 60 disponibles, procesado y con OC
r3, new = request('proceso', 'a', [
    ('cem', 100, dist('estr', 'conc'), 'central'),
    ('fie', 50, dist('estr', 'conc'), 'central'),
    ('are', 8, dist('estr', 'conc'), 'direct')],
    texto='Zapatas y columnas del bloque A.', date_required='2026-10-05')
if new:
    approve(r3)
    # Procesa Logística (admin): el requerimiento de compra queda a su nombre.
    r3.with_user(admin).action_process()
    # Como admin: el asistente usa la zona horaria del usuario para las fechas.
    wizard = env['purchase.request.line.make.purchase.order'].with_user(admin).with_context(
        active_model='purchase.request', active_ids=r3.purchase_request_ids.ids,
    ).create({'supplier_id': vendor.id})
    wizard.make_purchase_order()
    r3.purchase_order_ids.button_confirm()

# 4. Hecho: todo salió del almacén y llegó a la obra
r4, new = request('hecho', 'b', [('fie', 20, dist('estr', 'conc'), 'central')],
                  texto='Refuerzo de vigas.', date_required='2026-09-30')
if new:
    approve(r4)
    r4.with_user(admin).action_process()
    picking = r4.picking_ids
    picking.move_ids.picked = True
    picking.button_validate()

env.cr.commit()
for rec in (r1, r2, r3, r4):
    print(f'  {rec.name:<18} {rec.state:<12} id={rec.id} {rec.project_id.name}')
print('  pickings R3:', r3.picking_ids.mapped('name'), 'PR:', r3.purchase_request_ids.mapped('name'),
      'OC:', r3.purchase_order_ids.mapped('name'))

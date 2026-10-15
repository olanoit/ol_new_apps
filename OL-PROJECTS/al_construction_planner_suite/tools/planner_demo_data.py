# -*- coding: utf-8 -*-
"""Datos demo del planificador de obra (prefijo DEMO PLAN; todo ficticio).

Reproduce el piso 05 de la especificación v1.4 (departamentos 501 a 508,
tipologías 01 a 08): 66 módulos, 41.33 ML, material S/ 6,642.91, contrata
S/ 2,301.53 y total S/ 8,944.44, con el Dpto 501 en 7 módulos, 4.22 ML,
S/ 735.29 + S/ 258.37 y la instalación del piso en S/ 941.17 (P-05).
Lo que el maestro no da (reparto entre las tipologías 04 a 08, precios de
los materiales, cantidades por ambiente distintas de la tipología 01) es
inventado (E) y se cuadra con una línea de ajuste por tipología.

Idempotente. Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_data.py
"""
P = 'DEMO PLAN'
unit = env.ref('uom.product_uom_unit')
meter = env.ref('uom.product_uom_meter')


def get_or_create(model, domain, vals):
    return env[model].search(domain, limit=1) or env[model].create(vals)


print('=== Obra ===')
project = get_or_create('project.project', [('name', '=', f'{P} MOMEN-35-26')], {
    'name': f'{P} MOMEN-35-26', 'is_construction_site': True})
leandro = get_or_create('res.partner', [('name', '=', f'{P} Leandro (instalación)')],
                        {'name': f'{P} Leandro (instalación)', 'is_company': True})
gonza = get_or_create('res.partner', [('name', '=', f'{P} Armado Gonza')],
                      {'name': f'{P} Armado Gonza', 'is_company': True})

print('=== Actividades y tarifas (P-14) ===')
ACTIVITIES = [
    # código, nombre, etapa, unidad, tarifa base, tarifa de la obra, extras
    ('TOR', 'Armado módulo tornillo', 'assembly', unit, 6.00, None, {'module_level': True}),
    ('TAR', 'Armado módulo tarugo', 'assembly', unit, 8.00, None, {'module_level': True}),
    ('MIC', 'Armado microondas', 'assembly', unit, 10.00, None, {'module_level': True}),
    ('CAM', 'Armado módulo de campana', 'assembly', unit, 7.00, None, {'module_level': True}),
    ('CAJ', 'Armado cajonera', 'assembly', unit, 7.00, None, {'module_level': True}),
    ('PUE', 'Colocación de puertas', 'assembly', unit, 3.00, None, {}),
    ('ENT', 'Entarugado de muebles', 'assembly', unit, 3.00, None, {}),
    ('INB', 'Instalación mueble bajo', 'installation', meter, 16.00, 18.00,
     {'ml_based': True, 'ml_group': 'low'}),
    ('RGB', 'Regulación puerta mueble bajo', 'installation', meter, 2.50, 2.50, {}),
    ('INA', 'Instalación mueble alto', 'installation', meter, 16.00, 18.00,
     {'ml_based': True, 'ml_group': 'high'}),
    ('RGA', 'Regulación puertas mueble alto', 'installation', meter, 2.50, 2.50, {}),
    ('TAP', 'Colocación tapas de cajones', 'installation', unit, 1.50, 1.50, {}),
    ('REC', 'Recortes de muebles', 'installation', unit, 4.00, 4.00, {}),
    ('PIN', 'Colocación pines y repisas', 'installation', unit, 1.00, 1.00, {}),
    ('PUS', 'Instalación sistema push tip on', 'installation', unit, 1.00, 1.00, {}),
    ('LMB', 'Limpieza mueble bajo', 'finishing', meter, 6.00, 6.00,
     {'ml_based': True, 'ml_group': 'low'}),
    ('LMA', 'Limpieza mueble alto', 'finishing', meter, 6.00, 6.00,
     {'ml_based': True, 'ml_group': 'high'}),
    ('ENP', 'Entrega y protección (ajuste demo)', 'finishing', unit, 1.00, None, {}),
]
act = {}
for code, name, stage, uom, base, site, extra in ACTIVITIES:
    full_code = f'DEMO-{code}'
    activity = env['construction.labor.activity'].search([('code', '=', full_code)], limit=1)
    if not activity:
        activity = env['construction.labor.activity'].create(dict({
            'code': full_code, 'name': f'{P} {name}', 'stage': stage, 'uom_id': uom.id,
            'default_price': base, 'productivity_source': 'estimated'}, **extra))
        env['construction.labor.rate'].create({
            'activity_id': activity.id, 'price': base, 'retention_pct': 10.0})
        if site is not None:
            env['construction.labor.rate'].create({
                'activity_id': activity.id, 'project_id': project.id, 'price': site,
                'retention_pct': 10.0})
    act[code] = activity

print('=== Materiales ===')
MATERIALS = [
    # clave, código del maestro, nombre, unidad, costo (E), etapa de consumo
    ('MDP', '3101508', 'Melamina MDP blanco fantasía', unit, 168.00, 'production'),
    ('COÑ', '3101318', 'Melamina coñac', unit, 185.00, 'production'),
    ('RH', '3101305', 'Melamina blanco RH fantasía', unit, 195.00, False),
    ('BIS', '3105001', 'Bisagra lateral Danco', unit, 1.20, 'assembly'),
    ('TOR', '3105983', 'Tornillos 4×50', unit, 0.05, 'installation'),
    ('TAP', '3200018', 'Tapatornillo blanco', unit, 0.03, 'finishing'),
]
prod, cost = {}, {}
for key, ref, name, uom, price, _stage in MATERIALS:
    prod[key] = get_or_create('product.product', [('default_code', '=', f'DEMO-{ref}')], {
        'name': f'{P} {name}', 'default_code': f'DEMO-{ref}', 'type': 'consu',
        'is_storable': True, 'uom_id': uom.id, 'standard_price': price})
    cost[key] = price
stage_of = {key: stage for key, _r, _n, _u, _p, stage in MATERIALS}

# Tipologías 01 a 08 del piso 05. Solo la 01 trae del maestro su BOM y sus
# actividades por ambiente; las otras son E con los totales del piso X.
TYPOLOGIES = {
    #       módulos (tor, tar, mic, cam, caj), ML bajo, ML alto,
    #       (reg. bajo, reg. alto, tapas, recortes, pines, push), (puertas, entarugado),
    #       BOM (MDP, COÑ, RH, BIS, TOR, TAP), material, contrata
    '01': ((1, 3, 1, 1, 1), 2.12, 2.10, (1.60, 1.60, 4, 2, 7, 2), (1.93, 8.5),
           (1.9591, 0.9360, 0.2544, 10, 121, 78), 735.29, 258.37),
    '02': ((1, 4, 1, 1, 1), 2.55, 2.45, (2.00, 1.70, 3, 1, 2, 2), (2, 9),
           (2.1500, 1.0000, 0.2800, 12, 140, 90), 795.84, 272.80),
    '03': ((2, 5, 1, 1, 1), 2.80, 2.72, (2.20, 1.80, 3, 2, 3, 2), (2, 11),
           (2.4000, 1.1000, 0.3000, 14, 150, 95), 897.68, 307.30),
    '04': ((1, 4, 1, 1, 1), 2.70, 2.50, (2.00, 1.60, 3, 1, 2, 2), (2, 9),
           (2.2000, 1.0000, 0.2800, 12, 135, 85), 830.00, 288.00),
    '05': ((1, 4, 1, 1, 1), 2.90, 2.60, (2.10, 1.70, 3, 2, 3, 2), (2, 9),
           (2.2500, 1.0500, 0.2900, 12, 140, 90), 845.50, 290.50),
    '06': ((1, 4, 1, 1, 1), 2.60, 2.45, (2.00, 1.60, 3, 1, 2, 2), (2, 9),
           (2.1500, 1.0000, 0.2700, 12, 135, 85), 820.25, 285.40),
    '07': ((1, 4, 1, 1, 1), 2.85, 2.64, (2.10, 1.60, 3, 2, 3, 2), (2, 9),
           (2.2500, 1.0500, 0.2900, 12, 140, 90), 852.35, 292.16),
    '08': ((1, 5, 1, 1, 1), 2.75, 2.60, (2.12, 1.57, 2, 1, 2, 2), (2, 10),
           (2.3000, 1.0800, 0.3000, 14, 139, 87), 866.00, 307.00),
}
MODULE_KINDS = [('Tornillo', 'TOR', 'low'), ('Tarugo', 'TAR', 'low'),
                ('Microondas', 'MIC', 'high'), ('Campana', 'CAM', 'hood'),
                ('Cajonera', 'CAJ', 'drawer')]


def rate(code):
    return act[code]._get_rate(project)[0]


qty_digits = env['decimal.precision'].precision_get('Product Unit')


def money(value):
    return round(value + 1e-9, 2)


print('=== Tipologías (P-12) ===')
typologies = {}
for code, (mix, ml_low, ml_high, inst, armado, bom_qty, material, contract) in TYPOLOGIES.items():
    typology = env['construction.typology'].search(
        [('project_id', '=', project.id), ('code', '=', code)], limit=1)
    if not typology:
        modules = []
        for (label, act_code, mtype), count in zip(MODULE_KINDS, mix):
            for n in range(1, count + 1):
                name = label if count == 1 and act_code not in ('TOR', 'TAR') else f'{label} {n}'
                modules.append((0, 0, {'sequence': len(modules) + 1, 'code': name,
                                       'module_type': mtype,
                                       'assembly_activity_id': act[act_code].id}))
        lines = [('PUE', armado[0]), ('ENT', armado[1]), ('INB', ml_low), ('INA', ml_high),
                 ('RGB', inst[0]), ('RGA', inst[1]), ('TAP', inst[2]), ('REC', inst[3]),
                 ('PIN', inst[4]), ('PUS', inst[5]), ('LMB', ml_low), ('LMA', ml_high)]
        assembly = sum(rate(c) * n for (_l, c, _t), n in zip(MODULE_KINDS, mix))
        spent = assembly + sum(money(rate(c) * q) for c, q in lines)
        adjust = money(contract - spent)
        assert adjust > 0, (code, adjust)
        lines.append(('ENP', adjust))
        tmpl = env['product.template'].create({
            'name': f'{P} Cocina tipo {code}', 'type': 'consu', 'is_storable': True})
        bom_lines = [(key, qty) for key, qty in zip(('MDP', 'COÑ', 'RH', 'BIS', 'TOR', 'TAP'),
                                                     bom_qty)]
        # La BOM guarda las cantidades con la precisión «Product Unit» de la base.
        spent = sum(money(cost[key] * round(qty, qty_digits)) for key, qty in bom_lines)
        extra_cost = money(material - spent)
        assert extra_cost > 0, (code, extra_cost)
        # Ajuste E: herrajes de la tipología a un costo que cuadra con el maestro.
        extra = env['product.product'].create({
            'name': f'{P} Herrajes y accesorios tipología {code}',
            'default_code': f'DEMO-HER-{code}', 'type': 'consu', 'uom_id': unit.id,
            'standard_price': extra_cost})
        prod[f'HER-{code}'] = extra
        cost[f'HER-{code}'] = extra_cost
        stage_of[f'HER-{code}'] = 'assembly'
        bom = env['mrp.bom'].create({
            'product_tmpl_id': tmpl.id, 'product_qty': 1.0,
            'bom_line_ids': [(0, 0, {
                'product_id': prod[key].id, 'product_qty': qty,
                'construction_consumption_stage': stage_of[key]})
                for key, qty in bom_lines + [(f'HER-{code}', 1)]]})
        typology = env['construction.typology'].create({
            'project_id': project.id, 'code': code, 'name': f'Cocina {code}',
            'family': 'kitchen', 'product_tmpl_id': tmpl.id, 'bom_id': bom.id,
            'ml_low': ml_low, 'ml_high': ml_high, 'module_line_ids': modules,
            'activity_line_ids': [(0, 0, {'sequence': i, 'activity_id': act[c].id, 'qty': q})
                                  for i, (c, q) in enumerate(lines, 1)]})
    else:
        for line in typology.bom_id.bom_line_ids:
            key = next((k for k, p in prod.items() if p == line.product_id), None)
            if not key:
                key = f'HER-{code}'
                prod[key] = line.product_id
                cost[key] = line.product_id.standard_price
    typologies[code] = typology

print('=== Árbol del piso 05 ===')
Task = env['project.task']


def node(name, level, parent=None, **vals):
    domain = [('project_id', '=', project.id), ('name', '=', name),
              ('construction_level', '=', level),
              ('parent_id', '=', parent.id if parent else False)]
    return Task.search(domain, limit=1) or Task.create(dict({
        'name': name, 'project_id': project.id, 'construction_level': level,
        'parent_id': parent.id if parent else False, 'user_ids': False}, **vals))


floor = node('Piso 05', 'floor')
for n, code in enumerate(TYPOLOGIES, 1):
    apartment = node(f'Dpto 50{n}', 'apartment', floor)
    node('Cocina', 'space', apartment, construction_typology_id=typologies[code].id)

print('=== Plan y generación (W-01) ===')
Plan = env['construction.resource.plan']
# La versión 1: si ya se aprobó (planner_demo_baseline.py), no se regenera.
plan = Plan.search([('project_id', '=', project.id), ('version', '=', 1)], limit=1) \
    or Plan.create({'project_id': project.id, 'date_start': '2026-10-12',
                    'date_end': '2027-01-29'})
if plan.state == 'draft':
    wizard = env['construction.plan.generate.wizard'].create({'plan_id': plan.id})
    wizard.action_generate()
    # W-12 simulado: el planificador aplica el costo del maestro.
    for line in plan.line_ids.filtered(lambda l: l.resource_type == 'material'):
        key = next(k for k, p in prod.items() if p == line.product_id)
        line.write({'price_unit_planned': cost[key], 'price_basis': 'Costo del maestro (demo)'})

env.flush_all()
print('Plan', plan.display_name, 'líneas', plan.line_count)
print('Material', plan.amount_material, 'Contrata', plan.amount_contract,
      'Total', plan.amount_total)
modules = Task.search_count([('project_id', '=', project.id),
                             ('construction_level', '=', 'module')])
ml = sum(t.ml_low + t.ml_high for t in typologies.values())
print('Módulos', modules, 'ML', round(ml, 2))
apt = Task.search([('project_id', '=', project.id), ('name', '=', 'Dpto 501')])
lines_501 = plan.line_ids.filtered(lambda l: l.apartment_task_id == apt)
print('Dpto 501', sum(lines_501.filtered(lambda l: l.resource_type == 'material')
                      .mapped('amount_planned')),
      sum(lines_501.filtered(lambda l: l.resource_type == 'contract').mapped('amount_planned')))
inst = plan.line_ids.filtered(lambda l: l.stage == 'installation' and l.resource_type == 'contract')
print('Instalación del piso', round(sum(inst.mapped('amount_planned')), 2), 'en', len(inst), 'líneas')
assert round(plan.amount_material, 2) == 6642.91, plan.amount_material
assert round(plan.amount_contract, 2) == 2301.53, plan.amount_contract
assert round(plan.amount_total, 2) == 8944.44, plan.amount_total
assert modules == 66 and round(ml, 2) == 41.33
env.cr.commit()
print('OK')

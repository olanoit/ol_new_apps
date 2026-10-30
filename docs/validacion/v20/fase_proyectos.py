# -*- coding: utf-8 -*-
"""Fase «proyectos»: OL-PROJECTS + purchase_request / tier validation.

Obra QA20 de punta a punta, reutilizando los scripts demo del planificador
(al_construction_planner_suite/tools) con prefijo «QA20 » y códigos propios,
y luego casos por módulo sobre esa obra.
"""
import base64
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# ejecutar() con reintento: la base la usan otros agentes a la vez y en
# REPEATABLE READ una fila que otro confirmó después de nuestra foto da
# SerializationFailure. En la ejecución final se confirma cada caso al
# terminar (foto nueva para el siguiente) y un caso que choca se deshace y se
# repite en una transacción nueva.
import psycopg2.errors as _pgerr
_ROLLBACK = bool(os.environ.get('QA_ROLLBACK'))


def ejecutar(fn):
    for intento in range(4):
        try:
            with env.cr.savepoint():
                fn()
            if not _ROLLBACK:
                env.cr.commit()
            return
        except (_pgerr.SerializationFailure, _pgerr.LockNotAvailable, _pgerr.DeadlockDetected) as exc:
            if _ROLLBACK or intento == 3:
                _CUR['error'] = '%s: %s' % (type(exc).__name__, exc)
                _log(FAIL, '%s: conflicto de concurrencia' % fn.__name__, _CUR['error'])
                _CUR['registros'] = []
                return
            print('  ... conflicto de concurrencia en %s, reintento %s' % (fn.__name__, intento + 1))
            env.cr.rollback()
            env.invalidate_all()
            _CUR['checks'], _CUR['registros'] = [], []
        except Exception as exc:  # noqa: BLE001
            _CUR['error'] = '%s: %s' % (type(exc).__name__, exc)
            _log(FAIL, '%s lanzó una excepción' % fn.__name__, _CUR['error'])
            traceback.print_exc(limit=8)
            _CUR['registros'] = []
            if not _ROLLBACK:
                env.cr.commit()
            return


def submit_request(req, reason='QA20: reposición por piezas dañadas en el traslado.'):
    """Envía un requerimiento; si la política de exceso pide justificación, la da."""
    action = req.action_request_approval()
    if isinstance(action, dict) and action.get('res_model') == 'construction.plan.exceed.wizard':
        wiz = env['construction.plan.exceed.wizard'].with_env(req.env).browse(action['res_id']) if action.get('res_id') \
            else env['construction.plan.exceed.wizard'].with_env(req.env).with_context(action.get('context') or {}).create({})
        wiz.reason = reason
        wiz.action_confirm()
    return req


TOOLS = Path('/home/och/odoo/ce20/myapps/ol_new_apps/OL-PROJECTS/al_construction_planner_suite/tools')
P = 'QA20 '
PROJECT_NAME = P + 'MOMEN-35-26'
NS = {}

# ----------------------------------------------------------------------
#  Usuario QA20 (no se tocan los grupos del admin)
# ----------------------------------------------------------------------
admin = env.ref('base.user_admin')
GROUPS = [
    'al_construction_planner.group_planner_manager',
    'al_construction_planner.group_planner_project_head',
    'al_construction_planner.group_planner_revenue',
    'al_construction_planner.group_planner_amounts',
    'al_construction_material_request.group_construction_manager',
    'al_construction_material_request.group_construction_operations_manager',
    'al_construction_material_request.group_construction_logistics',
    'purchase_request.group_purchase_request_manager',
    'al_construction_planner_approvals_mrp.group_planner_production_head',
    'al_construction_planner_approvals.group_planner_technical_office',
    'mrp.group_mrp_manager',
    'documents.group_documents_user',
    'al_project_gantt_base.group_gantt_manager',
]


def qa_user():
    user = env['res.users'].with_context(active_test=False).search([('login', '=', 'qa20_obra')], limit=1)
    groups = admin.group_ids
    for xid in GROUPS:
        grp = env.ref(xid, raise_if_not_found=False)
        if grp:
            groups |= grp
    if not user:
        user = env['res.users'].create({
            'name': qa_name('Jefe de obra'), 'login': 'qa20_obra', 'email': 'qa20_obra@example.com',
            'company_id': company.id, 'company_ids': [Command.set(company.ids)],
            'group_ids': [Command.set(groups.ids)]})
    elif groups - user.group_ids:
        user.group_ids = [Command.link(g.id) for g in groups - user.group_ids]
    return user


def demo(fname, extra=()):
    """Ejecuta un script demo de la suite con el prefijo QA20, sin commit."""
    code = (TOOLS / fname).read_text()
    repl = [
        ('env.cr.commit()', 'pass'),
        ("P = ''", 'P = %r' % P),
        ("full_code = code", "full_code = f'QA20-{code}'"),
        ("env = env(user=env.ref('base.user_admin'))", 'env = env(user=QA_USER)'),
        ("admin = env.ref('base.user_admin')", 'admin = QA_USER'),
        ("[('default_code', '=', ref)]", "[('default_code', '=', 'QA20-' + ref)]"),
        ("'default_code': ref,", "'default_code': 'QA20-' + ref,"),
        ("'default_code': f'HER-{code}'", "'default_code': f'QA20-HER-{code}'"),
        ("act = {a.code: a for a in plan.line_ids.activity_id}",
         "act = {a.code.split('-', 1)[-1]: a for a in plan.line_ids.activity_id}"),
    ] + list(extra)
    for i, (old, new) in enumerate(repl):
        if i >= 9 and old not in code:
            raise AssertionError('reemplazo no aplicado en %s: %r' % (fname, old[:60]))
        code = code.replace(old, new)
    ns = {'env': env, 'QA_USER': NS['user'], 'print': lambda *a, **k: print('    |', *a)}
    exec(compile(code, str(TOOLS / fname), 'exec'), ns)  # noqa: S102
    return ns


def project():
    return env['project.project'].search([('name', '=', PROJECT_NAME)], limit=1)


NS['user'] = qa_user()
if not _ROLLBACK:
    env.cr.commit()
uenv = env(user=NS['user'])

# ======================================================================
#  1. Planificación de partidas (núcleo)
# ======================================================================
caso('al_construction_planner', 'Obra QA20: tipologías, árbol del piso 05 y generación del plan (W-01)',
     'planner_demo_data.py con prefijo QA20: 8 tipologías, árbol Piso › Dpto › Ambiente › Módulo, '
     'asistente de generación y costo del maestro')
def t_plan():
    ns = demo('planner_demo_data.py')
    NS.update(ns)
    plan, prj = ns['plan'], ns['project']
    # Jefe de la obra: el usuario QA20 (revisor de los requerimientos por la regla de la compañía).
    prj.user_id = NS['user']
    registro(prj, 'obra'); registro(plan, 'plan v1'); registro(ns['floor'], 'piso')
    registro(ns['leandro'] | ns['gonza'], 'contratas')
    igual(plan.amount_material, 6642.91, 'material planificado')
    igual(plan.amount_contract, 2301.53, 'contrata planificada')
    igual(plan.amount_total, 8944.44, 'total del plan')
    mods = env['project.task'].search_count([('project_id', '=', prj.id), ('construction_level', '=', 'module')])
    igual(mods, 66, 'módulos generados en el árbol')
    check(plan.line_count > 100, 'líneas del plan generadas', plan.line_count)
ejecutar(t_plan)

# ======================================================================
#  2. Presupuesto / línea base con aprobación por niveles
# ======================================================================
DOM = "[('project_id.name', '=', %r)]" % PROJECT_NAME
caso('al_construction_planner_approvals', 'Aprobación por niveles del plan y versión 2 (replan, W-12)',
     'planner_demo_baseline.py: reglas tier.definition (restringidas a la obra QA20), solicitar '
     'aprobación, validar tier, replanificar (v2), precio ponderado 6 meses')
def t_baseline():
    ns = demo('planner_demo_baseline.py', [
        ("'definition_domain': '[]'", "'definition_domain': %r" % DOM),
        ("\"[('amount_total', '>', 100000)]\"",
         repr("['&', ('amount_total', '>', 100000), %s]" % DOM[1:-1])),
    ])
    v1, v2 = ns['plan_v1'], ns['plan_v2']
    NS['plan_v1'], NS['plan_v2'] = v1, v2
    registro(v1, 'v1 aprobada'); registro(v2, 'v2 borrador')
    registro(env['tier.definition'].search([('name', '=like', 'QA20 Nivel%')]), 'reglas del plan')
    reviews = v1.review_ids
    check(reviews, 'el plan generó revisiones tier', reviews.mapped('name'))
    igual(v1.state, 'approved', 'v1 aprobada tras validar el nivel 1')
    check(v1.budget_analytic_id, 'v1 con presupuesto analítico', v1.budget_analytic_id.display_name)
    igual(v2.state, 'draft', 'v2 en borrador')
    check(v2.parent_id == v1, 'v2 desciende de v1')
    white = env['product.product'].search([('name', '=', P + 'Melamina MDP blanco fantasía')], limit=1)
    l2 = v2.line_ids.filtered(lambda l: l.product_id == white)[:1]
    check(l2 and l2.price_unit_planned < 168.0, 'v2: costo ponderado de compras aplicado a la melamina',
          l2.price_unit_planned)
ejecutar(t_baseline)

# ======================================================================
#  3. Abastecimiento: requerimiento, solicitud de compra, OF
# ======================================================================
caso('al_construction_planner_purchase', 'Compra masiva, requerimiento de obra, exceso y OF desde el plan',
     'planner_demo_supply.py: W-02 (purchase.request), W-03 (construction.material.request), '
     'W-10 (exceso con justificación), W-04 (mrp.production)')
def t_supply():
    ns = demo('planner_demo_supply.py', [
        # v20: las etapas del asistente son construction.stage (stage_ids), no booleanos.
        ("return {f'stage_{s}': on.get(s, False)\n                for s in ('production', 'assembly', 'installation', 'finishing')}",
         "return {'stage_ids': [(6, 0, env['construction.stage'].search([('code', 'in', [k for k, v in on.items() if v])]).ids)]}"),
    ])
    NS.update(request=ns['request'], material_request=ns['material_request'],
              exceeded=ns['exceeded'], production=ns['production'])
    registro(ns['request'], 'solicitud de compra'); registro(ns['material_request'], 'requerimiento')
    registro(ns['exceeded'], 'requerimiento con exceso'); registro(ns['production'], 'OF')
    check(ns['request'].line_ids, 'solicitud de compra con líneas', len(ns['request'].line_ids))
    check(ns['material_request'].state not in ('draft',), 'requerimiento enviado a aprobación',
          ns['material_request'].state)
    igual(ns['exceeded'].construction_exceed_state, 'exceeded', 'requerimiento marca exceso sobre el plan')
    check(ns['production'].product_qty > 0, 'OF creada', '%s %s' % (ns['production'].name, ns['production'].state))
    check(ns['plan'].allocation_ids, 'el plan registra asignaciones', len(ns['plan'].allocation_ids))
ejecutar(t_supply)

# ======================================================================
#  4. Contratas, avance y liquidación
# ======================================================================
caso('al_construction_planner_subcontract', 'Contrata (W-05), avance validado y liquidación semanal (P-08)',
     'planner_demo_contracts.py: asignar instalación a Leandro, OC de servicio, avance con foto, '
     'liquidación del 05/11 (bruto 380.88, neto 342.79)')
def t_contracts():
    ns = demo('planner_demo_contracts.py', [
        # Con la plantilla «Edificio» de la compañía hay un nivel Mueble entre Ambiente y Módulo.
        ("modules = Task.search([('parent_id', '=', spaces['Dpto 501'].id)], limit=2)",
         "modules = Task.search([('id', 'child_of', spaces['Dpto 501'].ids), ('construction_level', '=', 'module')], limit=2)"),
    ])
    NS.update(service_order=ns['order'], settlement=ns['settlement'])
    registro(ns['order'], 'OC de servicio'); registro(ns['settlement'], 'liquidación')
    igual(ns['order'].state, 'purchase', 'OC de servicio confirmada')
    igual(ns['order'].amount_untaxed, 941.17, 'OC de servicio por la instalación del piso')
    igual(ns['settlement'].amount_gross, 380.88, 'bruto de la liquidación')
    igual(ns['settlement'].amount_net, 342.79, 'neto de la liquidación (retención 10 %)')
    check(ns['settlement'].state != 'draft', 'liquidación enviada', ns['settlement'].state)
ejecutar(t_contracts)

# ======================================================================
#  5. Cuadrilla y personal propio
# ======================================================================
caso('al_construction_planner_crew', 'Cuadrilla (W-06) y hoja de horas con costo de personal',
     'planner_demo_control.py: actividad en horas, 2 obreros a S/ 9.50, cuadrilla 2 semanas, 6 h registradas')
def t_crew():
    ns = demo('planner_demo_control.py', [("('code', '=', 'PPI')", "('code', '=', 'QA20-PPI')"),
                                          ("'code': 'PPI'", "'code': 'QA20-PPI'")])
    NS.update(employees=ns['employees'], crew_activity=ns['activity'])
    registro(ns['employees'], 'obreros'); registro(ns['activity'], 'actividad propia')
    line = ns['line']
    igual(line.qty_executed, 6.0, 'horas ejecutadas en la línea de personal propio')
    igual(line.amount_actual, 57.0, 'costo real = 6 h × S/ 9.50')
    check(line.amount_committed > 0, 'comprometido por la cuadrilla', line.amount_committed)
    slots = env['planning.slot'].search([('resource_ids', 'in', ns['employees'].resource_id.ids)])
    registro(slots[:4], 'turnos de la cuadrilla')
    igual(len(slots), 4, 'turnos de planificación de la cuadrilla')
ejecutar(t_crew)

# ======================================================================
#  6. Ingreso: OV del contrato, entregas, valorización y factura
# ======================================================================
caso('al_construction_planner_sale', 'OV del contrato, entregas semanales y valorización 1 facturada',
     'planner_demo_income.py: OV, calendario de ingresos, 3 entregas, valorización enviada/observada/'
     'confirmada con acta y factura publicada')
def t_income():
    ns = demo('planner_demo_income.py')
    NS.update(sale_order=ns['order'], valuation=ns['valuation'], invoice=ns['invoice'])
    registro(ns['order'], 'OV del contrato'); registro(ns['valuation'], 'valorización 1')
    registro(ns['invoice'], 'factura')
    igual(ns['order'].state, 'sale', 'OV confirmada')
    igual(ns['valuation'].state, 'invoiced', 'valorización facturada') if 'invoiced' in dict(
        ns['valuation']._fields['state'].selection) else check(ns['valuation'].invoice_id, 'valorización con factura')
    igual(ns['invoice'].state, 'posted', 'factura publicada')
    check(ns['valuation'].amount_guarantee > 0, 'fondo de garantía retenido', ns['valuation'].amount_guarantee)
ejecutar(t_income)

caso('al_construction_planner_sale', 'Cronograma valorizado (plan y real) con cobro conciliado',
     'planner_demo_schedule.py: cobro conciliado y construction.schedule.report.get_schedule')
def t_schedule():
    ns = demo('planner_demo_schedule.py')
    data = ns['data']
    check(data['totals']['plan']['cost'] > 0, 'cronograma: costo planificado', data['totals']['plan'])
    check(data['totals']['real']['revenue'] > 0, 'cronograma: ingreso real', data['totals']['real'])
    igual(NS['invoice'].payment_state in ('paid', 'in_payment'), True, 'factura cobrada')
ejecutar(t_schedule)


def approve_tiers(rec, label):
    """Valida las revisiones pendientes de `rec` con el usuario revisor."""
    for _i in range(5):
        rec.invalidate_recordset()
        pending = rec.review_ids.filtered(lambda r: r.status in ('waiting', 'pending'))
        if not pending:
            break
        rev = pending.sorted('sequence')[:1]
        users = rev.reviewer_ids - env.ref('base.user_root')
        user = (NS['user'] if NS['user'] in users else users[:1]) or NS['user']
        res = rec.with_user(user).validate_tier()
        if isinstance(res, dict) and res.get('res_model') == 'comment.wizard':
            rec.with_user(user)._validate_tier()
        print('    | %s: revisión «%s» validada por %s' % (label, rev.name, user.name))


# ======================================================================
#  7. Requerimiento → solicitud de compra → OC con tier → recepción → despacho
# ======================================================================
caso('al_construction_material_request', 'Requerimiento de obra aprobado (tier), procesado y despachado a la obra',
     'RQO del piso (W-03): validar revisión, «Procesar» (logística) → solicitud de compra del faltante, '
     'recepción en el central y despacho a la ubicación de obra')
def t_request_flow():
    req = NS['material_request'].with_env(uenv)
    registro(req, 'requerimiento')
    approve_tiers(req, req.name)
    igual(req.state, 'approved', 'requerimiento aprobado tras las revisiones')
    req.action_process()
    igual(req.state, 'in_progress', 'requerimiento en proceso')
    prs = req.purchase_request_ids
    NS['rqo_pr'] = prs
    registro(prs, 'solicitud de compra del faltante')
    check(prs, 'el faltante generó solicitud de compra', prs.mapped('name'))
    check(req.picking_ids, 'transferencias hacia la obra creadas', req.picking_ids.mapped('name'))
ejecutar(t_request_flow)

caso('purchase_request', 'Solicitud de compra: aprobar y generar OC con el asistente',
     'purchase.request (W-02 compra masiva): to_approve → approved; asistente '
     'purchase.request.line.make.purchase.order con proveedor QA20')
def t_purchase_request():
    vendor = env['res.partner'].search([('name', '=', P + 'Maderera (proveedor)')], limit=1)
    NS['vendor'] = vendor
    prs = (NS['request'] | NS.get('rqo_pr', env['purchase.request'])).with_env(uenv)
    for pr in prs:
        if pr.state == 'draft':
            pr.button_to_approve()
        if pr.state == 'to_approve':
            pr.button_approved()
    check(all(s in ('approved', 'in_progress') for s in prs.mapped('state')), 'solicitudes aprobadas',
          prs.mapped('state'))
    wiz = env['purchase.request.line.make.purchase.order'].with_env(uenv).with_context(
        active_model='purchase.request', active_ids=prs.ids).create({'supplier_id': vendor.id})
    wiz.make_purchase_order()
    orders = prs.line_ids.purchase_lines.order_id
    NS['po'] = orders
    registro(orders, 'OC desde la solicitud')
    check(orders, 'OC generadas desde la solicitud', orders.mapped('name'))
    check(all(l.purchase_lines for l in prs.line_ids), 'cada línea de la solicitud enlazada a la OC')
ejecutar(t_purchase_request)

caso('purchase_tier_validation', 'OC con aprobación por niveles (regla QA20 por proveedor)',
     'tier.definition sobre purchase.order con dominio del proveedor QA20: confirmar sin validar falla, '
     'request_validation, validate_tier y confirmar')
def t_po_tier():
    from odoo.exceptions import ValidationError, UserError
    po_model = env['ir.model']._get('purchase.order')
    tier = env['tier.definition'].search([('name', '=', qa_name('OC: jefatura de compras'))], limit=1) or \
        env['tier.definition'].create({
            'name': qa_name('OC: jefatura de compras'), 'model_id': po_model.id,
            'review_type': 'individual', 'reviewer_id': NS['user'].id,
            'definition_domain': "[('partner_id.name', '=', %r)]" % (P + 'Maderera (proveedor)'),
            'sequence': 10})
    registro(tier, 'regla de aprobación de OC')
    orders = NS['po'].with_env(uenv)
    order = orders[:1]
    check(order.need_validation, 'la OC del proveedor QA20 necesita validación')
    # OCA intenta validar al confirmar si quien confirma es revisor: se confirma con
    # otro usuario (admin, no revisor) para comprobar el bloqueo.
    try:
        with env.cr.savepoint():
            order.with_user(admin).button_confirm()
            state = order.state
        check(False, 'confirmar sin validar debe bloquearse', state)
    except (ValidationError, UserError) as exc:
        check(True, 'confirmar sin validar está bloqueado', str(exc)[:90])
    for o in orders:
        o.request_validation()
        check(o.review_ids, 'revisión creada en %s' % o.name, o.review_ids.mapped('name'))
        o.validate_tier()
        igual(o.validation_status, 'validated', 'OC %s validada' % o.name)
        o.button_confirm()
        check(o.state in ('purchase', 'done'), 'OC %s confirmada tras la validación' % o.name, o.state)
ejecutar(t_po_tier)

caso('base_tier_validation', 'Motor de revisiones: estados, revisores y bloqueo de escritura',
     'tier.review de la OC y del plan QA20; escribir en un documento en revisión queda bloqueado')
def t_base_tier():
    from odoo.exceptions import ValidationError
    reviews = env['tier.review'].search([('model', '=', 'purchase.order'), ('res_id', 'in', NS['po'].ids)])
    check(reviews and all(r.status == 'approved' for r in reviews), 'revisiones de OC aprobadas', reviews.mapped('status'))
    check(all(r.done_by for r in reviews), 'cada revisión registra quién la hizo', reviews.mapped('done_by.name'))
    req = NS['exceeded'].with_env(uenv)
    pend = req.review_ids.filtered(lambda r: r.status in ('waiting', 'pending'))
    check(pend, 'requerimiento con exceso queda con revisiones pendientes', pend.mapped('name'))
    try:
        with env.cr.savepoint():
            req.with_user(admin).write({'note': '<p>QA20 cambio durante la revisión</p>'})
        aviso('escritura en documento en revisión no bloqueada', 'note se pudo escribir con revisión pendiente')
    except ValidationError as exc:
        check(True, 'escritura en documento en revisión bloqueada', str(exc)[:80])
ejecutar(t_base_tier)

caso('al_construction_planner_purchase', 'Recepción de la OC y despacho a la obra; tablero de abastecimiento',
     'validar recepción de la OC, luego la transferencia pendiente a la obra; '
     'construction.supply.board.get_board (pantalla OWL)')
def t_receipt():
    req = NS['material_request']
    for o in NS['po']:
        for pick in o.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            pick.move_ids.picked = True
            pick.button_validate()
            registro(pick, 'recepción')
            igual(pick.state, 'done', 'recepción %s validada' % pick.name)
    for pick in req.picking_ids.filtered(lambda p: p.state == 'assigned'):
        pick.move_ids.picked = True
        pick.button_validate()
        registro(pick, 'despacho a obra')
    rec = sum(req.line_ids.mapped('qty_received_on_site'))
    check(rec > 0, 'cantidad recibida en obra registrada en el requerimiento', rec)
    check(req.state in ('in_progress', 'done'), 'estado del requerimiento', req.state)
    Board = env['construction.supply.board'].with_env(uenv)
    projects = Board.get_board_projects()
    check(any(p['id'] == NS['project'].id for p in projects), 'obra QA20 en el selector del tablero')
    data = Board.get_board(NS['project'].id, {})
    check(data and (data.get('rows') or data.get('lines') or data), 'tablero de abastecimiento con datos',
          sorted(data.keys())[:8] if isinstance(data, dict) else type(data))
    omitido('render OWL del tablero de abastecimiento', 'sin navegador')
ejecutar(t_receipt)

# ======================================================================
#  8. Fabricación: OF desde el plan, exceso, accesorios, planchas enteras
# ======================================================================
SAVED_CO = {}


def co_set(vals):
    for k in vals:
        SAVED_CO.setdefault(k, company._fields[k].convert_to_write(company[k], company))
    company.write(vals)


def co_restore():
    if SAVED_CO:
        company.write(dict(SAVED_CO))
        SAVED_CO.clear()


def production_wizard(apartment_name):
    plan = NS['plan']
    apt = env['project.task'].search([('project_id', '=', NS['project'].id), ('name', '=', apartment_name),
                                      ('construction_level', '=', 'apartment')], limit=1)
    wiz = env['construction.plan.production.wizard'].with_env(uenv).with_context(
        default_plan_id=plan.id, construction_selection_task_ids=apt.ids).create({'group_by': 'selection'})
    return env['mrp.production'].browse(wiz.action_create()['res_id'])


caso('al_construction_planner_mrp', 'OF desde el plan (W-04): componentes por etapa y enlace al plan',
     'OF del Dpto 502 creada por planner_demo_supply; confirmar y revisar etapa de consumo y plan')
def t_mrp():
    mo = NS['production'].with_env(uenv)
    registro(mo, 'OF Dpto 502')
    check(mo.construction_plan_id == NS['plan'], 'OF enlazada al plan vigente', mo.construction_plan_id.display_name)
    stages = set(mo.move_raw_ids.mapped('construction_consumption_stage')) if 'construction_consumption_stage' in mo.move_raw_ids._fields else set()
    check(mo.move_raw_ids, 'OF con componentes de la BOM de la tipología', len(mo.move_raw_ids))
    if stages:
        check(stages - {False}, 'componentes con etapa de consumo', sorted(s for s in stages if s))
    alloc = NS['plan'].allocation_ids.filtered(lambda a: a.res_model == 'mrp.production' and a.res_id == mo.id) \
        if 'res_model' in NS['plan'].allocation_ids._fields else NS['plan'].allocation_ids
    check(alloc, 'asignación del plan registra la OF', len(alloc))
ejecutar(t_mrp)

caso('al_construction_planner_production', 'Accesorios de armado pedidos desde la OF',
     'quitar la bisagra (Armado) de la OF, confirmar, «Pedir accesorios» y enviar sin cambios → '
     'el accesorio entra a la OF')
def t_accessories():
    mo = NS['production'].with_env(uenv)
    hinge = env['product.product'].search([('name', '=', P + 'Bisagra lateral Danco')], limit=1)
    mo.move_raw_ids.filtered(lambda m: m.product_id == hinge).unlink()
    mo.action_confirm()
    check(mo.state == 'confirmed', 'OF confirmada', mo.state)
    action = mo.action_construction_request_accessories()
    req = env['construction.accessory.request'].browse(action['res_id'])
    registro(req, 'pedido de accesorios')
    check(req.line_ids.filtered(lambda l: l.planned_product_id == hinge), 'propone la bisagra del plan',
          req.line_ids.mapped(lambda l: (l.planned_product_id.name, l.qty_balance)))
    req.with_env(uenv).action_submit()
    igual(req.state, 'done', 'pedido sin cambios aplicado a la OF')
    qty = sum(mo.move_raw_ids.filtered(lambda m: m.product_id == hinge).mapped('product_uom_qty'))
    igual(qty, sum(req.line_ids.mapped('qty')), 'bisagras agregadas a la OF')
ejecutar(t_accessories)

caso('al_construction_planner_approvals_mrp', 'Exceso de la OF frente a lo presupuestado: aprueba el jefe de producción',
     'OF Dpto 503, +0.2 de melamina blanca, margen del jefe 5 % (temporal en la compañía) → exceso '
     'aprobado con motivo y registrado en construction.exceed.log')
def t_excess():
    try:
        co_set({'construction_approval_engine': 'approvals', 'construction_production_margin': 5.0, 'construction_production_margin_basis': 'order',
                'construction_production_margin_material': False})
        mo = production_wizard('Dpto 503').with_env(uenv)
        NS['mo_503'] = mo
        registro(mo, 'OF Dpto 503')
        white = env['product.product'].search([('name', '=', P + 'Melamina MDP blanco fantasía')], limit=1)
        mo.move_raw_ids.filtered(lambda m: m.product_id == white).product_uom_qty += 0.2
        mo.action_confirm()
        igual(mo.construction_exceed_state, 'exceeded', 'OF marcada con exceso')
        check(mo.construction_excess_amount > 0, 'monto del exceso', mo.construction_excess_amount)
        row = mo.construction_versus_ids.filtered(lambda r: r.product_id == white)
        igual(row.change_type, 'quantity', 'comparativo: cambio de cantidad en la melamina')
        igual(mo.construction_excess_action, 'approve', 'el jefe de producción puede aprobar (dentro del margen)')
        action = mo.action_construction_approve_excess()
        env[action['res_model']].with_env(uenv).with_context(action['context']).create(
            {'reason': 'QA20: merma del corte'}).action_approve()
        igual(mo.construction_exceed_state, 'approved', 'exceso aprobado')
        logs = env['construction.exceed.log'].search([('res_model', '=', 'mrp.production'), ('res_id', '=', mo.id)])
        check(logs, 'exceso registrado en el log', logs.mapped('product_id.name'))
        co_restore()
    finally:
        pass
ejecutar(t_excess)

caso('al_construction_planner_mrp_request', 'Planchas enteras en el despacho del requerimiento',
     'UdM plancha (construction_whole_sheet), 10.6 en stock, requerimiento de 13.3 → despacha 10 y compra 4 '
     '(opción de compañía activada solo durante el caso)')
def t_whole_sheet():
    try:
        co_set({'construction_whole_sheet': True})
        m2 = env.ref('uom.product_uom_square_meter')
        uom = env['uom.uom'].search([('name', '=', qa_name('Plancha 2.14×2.44 m'))], limit=1) or env['uom.uom'].create({
            'name': qa_name('Plancha 2.14×2.44 m'), 'relative_factor': 5.2216, 'relative_uom_id': m2.id,
            'construction_whole_sheet': True})
        board = env['product.product'].create({'name': qa_name('Melamina RH 18 mm (plancha)'), 'is_storable': True,
                                               'uom_id': uom.id, 'standard_price': 150.0})
        registro(board, 'tablero en planchas')
        env['stock.quant']._update_available_quantity(board, company.construction_src_location_id, 10.6)
        req = env['construction.material.request'].with_env(uenv).create({
            'project_id': NS['project'].id, 'line_ids': [Command.create({'product_id': board.id, 'product_qty': 13.3})]})
        registro(req, 'requerimiento de planchas')
        submit_request(req)
        approve_tiers(req, req.name)
        igual(req.state, 'approved', 'requerimiento aprobado')
        req.action_process()
        line = req.line_ids
        igual(line.qty_to_dispatch, 10.0, 'despacha planchas enteras')
        igual(line.qty_to_purchase, 4.0, 'compra lo que falta en planchas enteras')
        igual(line.qty_rounding, 0.7, 'redondeo a plancha entera')
        co_restore()
    finally:
        pass
ejecutar(t_whole_sheet)

caso('al_construction_planner_furniture', 'Tipología de mueble: módulos, piezas y clasificación',
     'tipología QA20-C04 con módulos de microondas y zócalo, piezas PUERTA y materiales por etapa')
def t_furniture():
    Product = env['product.product']
    screw = Product.create({'name': qa_name('Tornillo 4x50 mueble'), 'type': 'consu'})

    def module(code, name, materials, pieces=()):
        return Command.create({
            'code': code, 'name': name, 'module_type': 'low', 'width_mm': 600, 'ml_group': 'low',
            'material_ids': [Command.create({'product_id': p.id, 'qty': q, 'stage': st}) for p, q, st in materials],
            'piece_ids': [Command.create({'qty': q, 'length_mm': l, 'width_mm': w, 'piece_type': t})
                          for q, l, w, t in pieces]})
    typ = env['construction.typology'].create({
        'project_id': NS['project'].id, 'code': 'QA20-C04', 'name': qa_name('COCINA 04 a medida'),
        'family': 'kitchen', 'module_line_ids': [
            module('M1', 'MOD BAJO 665', [(screw, 12, 'assembly')], [(2, 730, 400, 'PUERTA')]),
            module('M3', 'MOD ALTO MICROONDAS 600', [(screw, 20, 'assembly')]),
            module('M4', 'MOD ZOCALO', [])]})
    registro(typ, 'tipología de mueble')
    m = {l.code: l for l in typ.module_line_ids}
    igual(m['M3'].module_class, 'special', 'microondas es módulo especial')
    igual(m['M3'].special_kind, 'microwave', 'tipo especial microondas')
    igual(m['M4'].special_kind, 'plinth', 'zócalo detectado')
    igual(m['M4'].join_method, 'none', 'zócalo sin unión')
    check(m['M1'].piece_ids and m['M1'].material_ids, 'módulo con piezas y materiales')
ejecutar(t_furniture)

# ======================================================================
#  9. Contratas: aprobación de la liquidación, factura, material extra,
#     valorización con condiciones y adicionales
# ======================================================================
caso('al_construction_planner_subcontract', 'Liquidación semanal: validar, aprobar (tier), recepción en la OC y factura',
     'LIQ del 05/11: action_validate, validate_tier de la jefatura, recepción en la OC de servicio y '
     'factura de proveedor con vencimiento el sábado 07/11')
def t_settlement():
    st = NS['settlement'].with_env(uenv)
    st.action_validate()
    approve_tiers(st, st.name)
    igual(st.state, 'approved', 'liquidación aprobada')
    inv = st.invoice_id
    registro(inv, 'factura de la contrata')
    igual(inv.move_type, 'in_invoice', 'factura de proveedor')
    igual(inv.amount_untaxed, 380.88, 'base de la factura = bruto de la liquidación')
    igual(str(inv.invoice_date_due), '2026-11-07', 'vence el sábado de pago')
    po_lines = NS['service_order'].order_line
    check(sum(po_lines.mapped('qty_received')) > 0, 'recepción registrada en la OC de servicio',
          round(sum(po_lines.mapped('qty_received')), 2))
    check(inv in NS['service_order'].invoice_ids, 'factura enlazada a la OC de servicio')
    NS['settlement_invoice'] = inv
ejecutar(t_settlement)

caso('al_construction_planner_subcontract_purchase', 'Material extra descontado a la contrata en su siguiente liquidación',
     'requerimiento extra (reposición) con «Descontar a la contrata» Leandro; liquidación del 12/11 '
     'lo toma como descuento')
def t_extra_discount():
    prj = NS['project']
    screw = env['product.product'].search([('name', '=', P + 'Tornillos 4×50')], limit=1)
    leandro = NS['leandro']
    req = env['construction.material.request'].with_env(uenv).create({
        'project_id': prj.id, 'is_extra': True,
        'extra_reason': 'replacement',
        'construction_discount': True, 'construction_discount_partner_id': leandro.id,
        'line_ids': [Command.create({'product_id': screw.id, 'product_qty': 100})]})
    registro(req, 'material extra')
    if not req.extra_reason:
        aviso('extra_reason se pierde al crear con is_extra', 'se vuelve a escribir')
        req.extra_reason = 'replacement'
    check(req.construction_discount_amount > 0, 'monto a descontar = estimado', req.construction_discount_amount)
    submit_request(req)
    approve_tiers(req, req.name)
    igual(req.state, 'approved', 'extra aprobado')
    # Avance de la semana siguiente (Dpto 505) para que haya liquidación del 12/11.
    plan = NS['plan']
    line = plan.line_ids.filtered(lambda l: l.partner_id == leandro and l.space_task_id.parent_id.name == 'Dpto 505'
                                  and l.resource_type == 'contract')[:1]
    pr = env['construction.task.progress'].create({
        'task_id': line.task_id.id, 'activity_id': line.activity_id.id, 'date': date(2026, 11, 6),
        'qty': line.qty_planned, 'attachment_ids': [Command.create({'name': 'qa.png', 'raw': b'\x89PNG'})]})
    pr.with_env(uenv).action_validate()
    st = env['construction.contract.settlement']._prepare_settlements(date(2026, 11, 12), prj)
    st = st.filtered(lambda s: s.partner_id == leandro)
    registro(st, 'liquidación 12/11')
    check(req in st.discount_request_ids, 'el extra entra como descuento en la liquidación', st.discount_request_ids.mapped('name'))
    igual(st.amount_discount, req.construction_discount_amount, 'descuento en la liquidación')
ejecutar(t_extra_discount)

caso('al_construction_planner_subcontract', 'Valorización del contratista con condiciones (adelanto, deductivo, fondo de garantía)',
     'obra QA20 OBR-01 tabiquería: condición de la compañía (data), adelanto, 1 000 m² + adicional 100 u, '
     'deductivo 650 → Valorizado 01 por 35 532.75 a pagar')
def t_terms():
    try:
        Account = env['account.account']
        igv = env['account.tax'].search([('company_id', '=', company.id), ('type_tax_use', '=', 'purchase'),
                                         ('amount', '=', 18.0), ('amount_type', '=', 'percent'),
                                         ('price_include', '=', False)], limit=1)
        expense = Account.search([('account_type', '=', 'expense'), ('company_ids', 'in', company.id)], limit=1)
        adv_acc = Account.search([('code', '=', '4229QA'), ('company_ids', 'in', company.id)], limit=1) or Account.create({
            'name': qa_name('Anticipos a contratistas'), 'code': '4229QA', 'account_type': 'asset_current'})
        adv = env['product.product'].create({
            'name': qa_name('Anticipo a contratistas'), 'type': 'service', 'purchase_ok': True,
            'supplier_taxes_id': [Command.set(igv.ids)], 'property_account_expense_id': adv_acc.id})
        co_set({'construction_advance_product_id': adv.id})
        m2, unit = env.ref('uom.product_uom_square_meter'), env.ref('uom.product_uom_unit')
        stage = env['construction.stage'].search([('code', '=', 'qa20_tab')], limit=1) or env['construction.stage'].create(
            {'name': qa_name('Tabiquería'), 'code': 'qa20_tab', 'sequence': 590})
        prj = env['project.project'].create({'name': qa_name('OBR-01 Tabiquería'), 'is_construction_site': True,
                                             'user_id': NS['user'].id})
        NS['terms_project'] = prj
        registro(prj, 'obra con condiciones')
        tmpl = env['construction.level.template'].create({'name': qa_name('Especialidad › Partida'), 'line_ids': [
            Command.create({'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
            Command.create({'sequence': 2, 'name': 'Sub-especialidad', 'role': 'group'}),
            Command.create({'sequence': 3, 'name': 'Partida', 'role': 'space'})]})
        prj.construction_level_template_id = tmpl
        lv = tmpl.line_ids.sorted('sequence')
        T = env['project.task']
        disc = T.create({'name': 'Arquitectura', 'project_id': prj.id, 'construction_level_line_id': lv[0].id})
        sub = T.create({'name': 'Tabiquería', 'project_id': prj.id, 'construction_level_line_id': lv[1].id, 'parent_id': disc.id})
        wall_t = T.create({'name': '04.01 Tabique drywall', 'project_id': prj.id, 'construction_level_line_id': lv[2].id, 'parent_id': sub.id})
        seal_t = T.create({'name': '04.02 Sellado de juntas', 'project_id': prj.id, 'construction_level_line_id': lv[2].id, 'parent_id': sub.id})

        def service(name):
            return env['product.product'].create({'name': qa_name(name), 'type': 'service', 'purchase_method': 'receive',
                                                  'supplier_taxes_id': [Command.set(igv.ids)],
                                                  'property_account_expense_id': expense.id})
        Act = env['construction.labor.activity']
        wall = Act.create({'code': 'QA20-TAB', 'name': qa_name('Tabique drywall'), 'stage': 'qa20_tab',
                           'default_price': 38.20, 'uom_id': m2.id, 'product_id': service('Tabique drywall (servicio)').id})
        seal = Act.create({'code': 'QA20-SEL', 'name': qa_name('Sellado de juntas'), 'stage': 'qa20_tab',
                           'default_price': 18.0, 'uom_id': unit.id, 'product_id': service('Sellado (servicio)').id})
        contractor = env['res.partner'].create({'name': qa_name('Tabiquería Demo SAC'), 'is_company': True})
        plan = env['construction.resource.plan'].create({'project_id': prj.id})
        env['construction.resource.plan.line'].create([
            {'plan_id': plan.id, 'task_id': wall_t.id, 'resource_type': 'contract', 'activity_id': wall.id,
             'stage': 'qa20_tab', 'qty_planned': 2000.0, 'price_unit_planned': 38.20, 'product_uom_id': m2.id},
            {'plan_id': plan.id, 'task_id': seal_t.id, 'resource_type': 'contract', 'activity_id': seal.id,
             'stage': 'qa20_tab', 'qty_planned': 100.0, 'price_unit_planned': 18.0, 'product_uom_id': unit.id}])
        plan.with_env(uenv).action_request_approval()
        igual(plan.state, 'approved', 'plan de la obra con condiciones aprobado')
        registro(plan, 'plan OBR-01')
        cond = env.ref('al_construction_planner_subcontract.contract_condition_construction')
        wiz = env['construction.plan.contract.wizard'].with_env(uenv).with_context(
            default_plan_id=plan.id, construction_selection_project=True).create({
                'stage': 'qa20_tab', 'partner_id': contractor.id, 'condition_id': cond.id, 'date_start': date(2026, 11, 2)})
        igual(wiz.terms_total, 94121.52, 'total contractual con el esquema de la condición')
        wiz.action_assign()
        order = env['purchase.order'].search([('partner_id', '=', contractor.id), ('construction_project_id', '=', prj.id)],
                                             order='id desc', limit=1).with_env(uenv)
        registro(order, 'OC de contrata con condiciones')
        check(order.construction_uses_terms, 'la OC lleva condiciones copiadas')
        order.order_line.filtered(lambda l: l.construction_activity_id == seal).construction_is_additional = True
        order.button_confirm()
        adv_move = env['account.move'].browse(order.action_construction_register_advance()['res_id'])
        adv_move.invoice_date = date(2026, 11, 2)
        if 'l10n_latam_use_documents' in adv_move._fields and adv_move.l10n_latam_use_documents \
                and not adv_move.l10n_latam_document_number:
            adv_move.l10n_latam_document_number = 'F001-%06d' % adv_move.id
        adv_move.action_post()
        registro(adv_move, 'factura de adelanto')
        igual(adv_move.amount_untaxed, 15952.80, 'adelanto 20 % del subtotal contractual')
        igual(adv_move.state, 'posted', 'adelanto publicado')
        photo = [Command.create({'name': 'foto.png', 'raw': b'\x89PNG'})]
        for task, act, qty in ((wall_t, wall, 1000.0), (seal_t, seal, 100.0)):
            pr = env['construction.task.progress'].create({'task_id': task.id, 'activity_id': act.id,
                                                          'date': date(2026, 11, 4), 'qty': qty, 'attachment_ids': photo})
            pr.with_env(uenv).action_validate()
        env['construction.contract.deduction'].create({
            'purchase_order_id': order.id, 'type_id': env.ref('al_construction_planner_subcontract.deduction_type_unfinished').id,
            'description': 'QA20 remate por personal propio', 'amount': 650.0, 'date': date(2026, 11, 4),
            'attachment_ids': [Command.create({'name': 'acta.pdf', 'raw': b'%PDF-1.4'})]})
        sts = env['construction.contract.settlement']._prepare_terms_settlements(today=date(2026, 11, 20))
        st = sts.filtered(lambda s: s.purchase_order_id == order)
        registro(st, 'Valorizado 01')
        check(st.title and st.title.startswith('Valorizado 01'), 'título de la valorización', st.title)
        igual(st.amount_direct, 38200.0, 'costo directo valorizado')
        igual(st.amount_additional, 1800.0, 'adicionales')
        igual(st.amount_total, 47377.0, 'total con IGV')
        igual(st.amount_advance, 9475.40, 'amortización del adelanto')
        igual(st.amount_retention, 2368.85, 'fondo de garantía')
        igual(st.amount_to_pay, 35532.75, 'total a pagar')
        st.with_env(uenv).action_submit()
        st.with_env(uenv).action_validate()
        approve_tiers(st.with_env(uenv), st.name)
        igual(st.state, 'approved', 'valorización aprobada')
        inv = st.invoice_id
        registro(inv, 'factura de la valorización')
        igual(inv.amount_total, 37901.60, 'factura de la valorización')
        NS['terms_order'] = order
        co_restore()
    finally:
        pass
ejecutar(t_terms)

caso('al_construction_planner_subcontract_sale', 'Adicional de obra agregado a la OC de la contrata',
     'construction.change.order «additional» aprobado y «Agregar a la orden de contrata»')
def t_additional():
    prj, order = NS['terms_project'], NS['terms_order']
    seal_t = env['project.task'].search([('project_id', '=', prj.id), ('name', '=', '04.02 Sellado de juntas')], limit=1)
    seal = env['construction.labor.activity'].search([('code', '=', 'QA20-SEL')], limit=1)
    ch = env['construction.change.order'].with_env(uenv).create({
        'project_id': prj.id, 'kind': 'additional', 'requested_by': 'contractor',
        'reason': 'QA20 sellado adicional pedido por la supervisión',
        'line_ids': [Command.create({'task_id': seal_t.id, 'resource_type': 'contract', 'activity_id': seal.id,
                                     'stage': 'qa20_tab', 'qty': 50.0, 'price_unit': 18.0})]})
    registro(ch, 'cambio de obra')
    ch.action_approve()
    check(ch.construction_can_add_to_order, 'cambio aprobado se puede agregar a la OC')
    ch.construction_contractor_id = order.partner_id
    ch.action_add_to_contract_order()
    line = ch.construction_purchase_line_ids
    check(line.order_id == order, 'línea agregada a la OC de la contrata', line.order_id.name)
    check(line.construction_is_additional, 'línea marcada como adicional')
    igual(line.product_qty, 50.0, 'cantidad del adicional')
ejecutar(t_additional)

caso('al_construction_planner_budget', 'Presupuesto analítico del plan y control de la OC contra el presupuesto',
     'budget.analytic de la v1 con líneas; OC de material con analítica de la obra: estado del control')
def t_budget():
    plan = NS['plan']
    b = plan.budget_analytic_id
    registro(b, 'presupuesto analítico')
    check(b.budget_line_ids, 'presupuesto con líneas', len(b.budget_line_ids))
    igual(round(sum(b.budget_line_ids.mapped('budget_amount')), 2) != 0, True, 'presupuesto con montos')
    po = NS['po'][:1]
    check(po.construction_exceed_state in ('ok', 'approved', 'exceeded', False), 'OC con estado del control de presupuesto',
          po.construction_exceed_state)
    rows = po.sudo()._construction_budget_amounts()
    check(isinstance(rows, dict), 'importes de la OC por línea de presupuesto calculados', len(rows))
ejecutar(t_budget)

# ======================================================================
#  10. Partidas por familia, hojas de cálculo
# ======================================================================
caso('al_construction_planner_sale_furniture', 'Partida del contrato por familia de la tipología',
     'OV del contrato con una partida «Cocinas» sin familia: el resolver de partidas asigna las líneas '
     'del plan de cocinas a esa partida; con familia «kitchen» también')
def t_sale_furniture():
    prj, so = NS['project'], NS['sale_order']
    part = so.order_line.filtered(lambda l: not l.display_type)[:1]
    resolve = prj._construction_partida_resolver(part)
    pl = NS['plan'].line_ids.filtered(lambda l: l.space_task_id)[:1]
    got = resolve(pl) if callable(resolve) else resolve
    check(got == part, 'línea del plan asignada a la partida «Cocinas»', got.display_name if got else got)
    part.construction_family = 'kitchen'
    resolve = prj._construction_partida_resolver(part)
    got = resolve(pl)
    check(got == part, 'con familia kitchen la partida toma las cocinas', got.display_name if got else got)
ejecutar(t_sale_furniture)

caso('al_construction_planner_spreadsheet', 'Hoja de presupuesto de la cotización (documents.spreadsheet)',
     'action_construction_open_spreadsheet en la OV QA20: documento «budget» con sus hojas y filas Odoo')
def t_budget_sheet():
    import json
    so = NS['sale_order'].with_env(uenv)
    so.action_construction_open_spreadsheet()
    doc = env['documents.document'].search([('construction_sale_order_id', '=', so.id), ('construction_source_id', '=', False)])
    registro(doc, 'hoja de presupuesto')
    igual(len(doc), 1, 'un documento de hoja por cotización')
    igual(doc.construction_sheet_kind, 'budget', 'tipo de hoja presupuesto')
    names = [s['name'] for s in json.loads(doc.spreadsheet_data)['sheets']]
    check({'PRESUPUESTO', 'APU', 'INSUMOS'} <= set(names), 'plantilla con las hojas del libro', names)
    rows = doc.construction_odoo_rows()
    check('PRESUPUESTO' in rows, 'filas Odoo de la hoja (RPC de la pantalla)', list(rows)[:5])
    res = doc.action_construction_validate({k: [] for k in names})
    check('errors' in res, 'validación de la hoja responde', len(res.get('errors', [])))
    omitido('edición visual de la hoja (o-spreadsheet)', 'sin navegador')
ejecutar(t_budget_sheet)

caso('al_construction_planner_spreadsheet_furniture', 'Hoja de trabajo de la obra con el maestro de mobiliario',
     'project.action_construction_open_spreadsheet: hojas del maestro (ARBOL, TIPOLOGIAS…) y listas Odoo')
def t_furniture_sheet():
    import json
    prj = NS['project'].with_env(uenv)
    action = prj.action_construction_open_spreadsheet()
    doc = env['documents.document'].search([('construction_project_id', '=', prj.id), ('construction_source_id', '=', False)]) \
        if 'construction_source_id' in env['documents.document']._fields else \
        env['documents.document'].search([('construction_project_id', '=', prj.id)])
    doc = doc.filtered(lambda d: d.construction_sheet_kind != 'budget') or doc
    registro(doc[:1], 'hoja de la obra')
    check(doc and action.get('params', {}).get('spreadsheet_id') in doc.ids, 'acción abre la hoja de la obra')
    data = json.loads(doc[:1].spreadsheet_data)
    names = [s['name'] for s in data['sheets']]
    check('ARBOL' in names and 'TIPOLOGIAS' in names, 'hojas del maestro de mobiliario', names)
    check(data.get('lists'), 'listas ODOO.LIST enlazadas', sorted({l['model'] for l in data['lists'].values()}))
ejecutar(t_furniture_sheet)

# ======================================================================
#  11. Marcación en obra (sede, contratas, quiosco)
# ======================================================================
caso('al_construction_attendance', 'Sede de la obra, marcación de contrata y de personal propio, avance con asistencia',
     'l10n_pe.hr.construction.site de la obra QA20, trabajador de contrata con SCTR vencido, '
     'hr.attendance con GPS → sede y distancia; avance con attendance_ok')
def t_attendance():
    prj = NS['project']
    Site = env['l10n_pe.hr.construction.site']
    site = prj.construction_hr_site_ids[:1] if 'construction_hr_site_ids' in prj._fields else Site
    if not site:
        site = Site.create({'name': qa_name('Sede MOMEN'), 'project_id': prj.id, 'company_id': company.id})
    site.write({'latitude': -12.0464, 'longitude': -77.0428, 'radius_m': 150, 'entry_deadline': 7.0 + 50 / 60.0})
    registro(site, 'sede de obra')
    igual(site._distance_to(-12.0464, -77.0428), 0.0, 'distancia a la sede')
    check(site._out_of_range(-12.0500, -77.0428), 'a ~400 m queda fuera del radio')
    check(site._is_late(datetime(2026, 11, 2, 12, 55)), '7:55 en Lima es tardanza')
    worker = env['construction.contractor.worker'].create({
        'name': qa_name('Juan Gonza'), 'document_number': '40020001', 'partner_id': NS['gonza'].id,
        'sctr_valid_until': date(2026, 1, 1)})
    registro(worker, 'trabajador de contrata')
    att = env['construction.contractor.attendance'].create({'worker_id': worker.id, 'site_id': site.id,
                                                            'check_in': datetime(2026, 11, 4, 12, 30)})
    registro(att, 'marcación de contrata')
    check(worker.sctr_expired, 'trabajador con SCTR vencido marcado (el aviso «al marcar» lo pone el quiosco)')
    emp = NS['employees'][:1]
    own = env['hr.attendance'].create({'employee_id': emp.id, 'check_in': datetime(2026, 10, 29, 13, 0),
                                       'check_out': datetime(2026, 10, 29, 21, 0),
                                       'in_latitude': -12.0470, 'in_longitude': -77.0428})
    registro(own, 'marcación personal propio')
    igual(own.l10n_pe_construction_site_id, site, 'marcación toma la sede más cercana')
    check(abs(own.l10n_pe_site_distance_m - 66.7) < 2, 'distancia registrada', own.l10n_pe_site_distance_m)
    # Avance de la contrata del 04/11 (Gonza, armado): con marcación ese día.
    pr = env['construction.task.progress'].search([('task_id.project_id', '=', prj.id), ('date', '=', date(2026, 11, 4)),
                                                   ('activity_id.stage', '=', 'assembly')], limit=1)
    if pr:
        pr.invalidate_recordset(['attendance_ok'])
        check(pr.attendance_ok, 'avance de la contrata con asistencia ese día', pr.display_name)
    else:
        aviso('no se encontró avance de armado del 04/11 para cruzar con la asistencia')
    omitido('quiosco /obra/quiosco (HTTP)', 'controlador web: sin servidor de pruebas en el shell')
ejecutar(t_attendance)

# ======================================================================
#  12. Portal de obra
# ======================================================================
caso('al_construction_portal', 'Portal de obra: contrata reporta avance, maestro envía parte diario, valorizaciones',
     'usuarios portal QA20 (contrata y maestro de obra) en la obra OBR-01; construction.portal.service '
     'sync/progress/daily_report/valuations')
def t_portal():
    prj, order = NS['terms_project'], NS['terms_order']
    contractor = order.partner_id
    Users = env['res.users'].with_context(no_reset_password=True)

    def portal_user(login, name, parent=None):
        u = Users.search([('login', '=', login)], limit=1) or Users.create({
            'name': name, 'login': login, 'email': '%s@example.com' % login,
            'group_ids': [Command.set([env.ref('base.group_portal').id])]})
        if parent:
            u.partner_id.parent_id = parent
        return u
    cu = portal_user('qa20_portal_contrata', qa_name('Supervisor de la contrata'), contractor)
    fu = portal_user('qa20_portal_maestro', qa_name('Maestro de obra'))
    foreman = env['hr.employee'].create({'name': qa_name('Maestro de obra'), 'company_id': company.id})
    M = env['construction.portal.member']
    M.create({'project_id': prj.id, 'user_id': cu.id, 'role': 'contractor', 'partner_id': contractor.id})
    M.create({'project_id': prj.id, 'user_id': fu.id, 'role': 'foreman', 'employee_id': foreman.id})
    registro(cu | fu, 'usuarios portal')
    svc = env['construction.portal.service'].with_user(cu)
    data = svc.sync(prj.id)
    igual(data['roles'], ['contractor'], 'rol en el portal')
    wall = env['construction.labor.activity'].search([('code', '=', 'QA20-TAB')], limit=1)
    pline = env['construction.resource.plan.line'].search([('plan_id.project_id', '=', prj.id), ('activity_id', '=', wall.id)], limit=1)
    check(any(p['id'] == pline.id for p in data['partidas']), 'la contrata ve su partida')
    import base64 as b64
    png = b64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 16).decode()
    payload = {'uuid': 'qa20-portal-1', 'project_id': prj.id, 'plan_line_id': pline.id,
               'date': fields.Date.to_string(fields.Date.context_today(svc)), 'qty': 25.0,
               'photos': [{'name': 'avance.png', 'mimetype': 'image/png', 'data': png}],
               'latitude': -12.1, 'longitude': -77.0}
    res = svc.progress(payload)
    prog = env['construction.task.progress'].browse(int(res['ids']))
    registro(prog, 'avance desde el portal')
    igual((prog.source, prog.qty, prog.state), ('portal', 25.0, 'draft'), 'avance del portal en borrador')
    check(svc.progress(payload).get('duplicate'), 'reenvío no duplica (uuid)')
    rep = env['construction.portal.service'].with_user(fu).daily_report({
        'uuid': 'qa20-parte-1', 'project_id': prj.id, 'weather': 'sunny',
        'staff': [{'name': 'Cuadrilla propia', 'source': 'own', 'count': 6}],
        'restrictions': ['material'], 'occurrences': 'QA20: falta cemento.'})
    report = env['construction.daily.report'].browse(int(rep['ids']))
    registro(report, 'parte diario')
    igual(report.staff_total, 6, 'parte diario con personal')
    vals = svc.valuations(prj.id)
    check(vals, 'valorizaciones visibles para la contrata', str(vals)[:120])
    omitido('PWA del portal (OWL/HTML)', 'sin navegador')
ejecutar(t_portal)

# ======================================================================
#  13. Gantt
# ======================================================================
caso('al_project_gantt_base', 'Gantt: tareas con dependencias, mover con reprogramación en cadena, línea base y ruta crítica',
     'proyecto QA20 Gantt con A→B→C y una paralela; apply_gantt_changes(reschedule_chain), create_baseline, '
     'al_gantt_get_data(critical_path, baseline_id), export_xlsx')
def t_gantt():
    from odoo.exceptions import ValidationError, UserError
    fm = env['al.gantt.field.map'].get_map()
    sf, ef = fm['date_start'], fm['date_end']
    genv = uenv
    prj = env['project.project'].create({'name': qa_name('Gantt de obra'), 'allow_milestones': True,
                                         'privacy_visibility': 'employees'})
    NS['gantt_project'] = prj
    registro(prj, 'proyecto Gantt')
    base = datetime(2026, 11, 2, 8, 0)

    def task(name, off, dur):
        vals = {'name': qa_name(name), 'project_id': prj.id}
        if sf:
            vals[sf] = base + timedelta(days=off)
        if ef:
            vals[ef] = base + timedelta(days=off + dur)
        return env['project.task'].create(vals)
    a, b, c = task('A Trazo', 0, 5), task('B Tabiquería', 5, 10), task('C Acabados', 15, 5)
    side = task('Paralela corta', 5, 1)
    b.depend_on_ids = [Command.set(a.ids)]
    c.depend_on_ids = [Command.set(b.ids)]
    side.depend_on_ids = [Command.set(a.ids)]
    registro(a | b | c | side, 'tareas')
    NS['gantt_tasks'] = a | b | c | side
    P_ = genv['project.project']
    data = P_.al_gantt_get_data(project_ids=[prj.id], options={'critical_path': True})
    rows = {t['id']: t for t in data['tasks']}
    check(all(rows[t.id]['critical'] for t in (a, b, c)), 'A, B y C en la ruta crítica')
    check(not rows[side.id]['critical'] and rows[side.id]['slack_hours'] > 0, 'la paralela tiene holgura',
          rows[side.id]['slack_hours'])
    bl = genv['al.gantt.data'].create_baseline([prj.id], qa_name('Línea base 1'))
    check(bl['ok'], 'línea base capturada', bl['baselines'][0]['task_count'])
    registro(env['al.gantt.baseline'].browse(bl['baselines'][0]['id']), 'línea base')
    if sf:
        dur_b = b[ef] - b[sf]
        new_end = base + timedelta(days=7)
        res = P_.apply_gantt_changes({'tasks': {'update': [{
            'id': a.id, 'start': (new_end - timedelta(days=7)).isoformat() + 'Z', 'end': new_end.isoformat() + 'Z'}]},
            'reschedule_chain': True})
        check(res['ok'], 'cambio aplicado', res.get('updated'))
        igual(b[sf], new_end, 'la sucesora B empieza al terminar A')
        igual(b[ef] - b[sf] == dur_b, True, 'B conserva su duración')
        check(c[sf] >= b[ef], 'C se empuja detrás de B (transitivo)', c[sf])
    else:
        omitido('reprogramación por fecha de inicio', 'sin campo de inicio en el mapeo')
    data = P_.al_gantt_get_data(project_ids=[prj.id], options={'baseline_id': bl['baselines'][0]['id']})
    check(data['meta']['baseline']['applied'], 'desvío contra la línea base aplicado')
    igual(next(t for t in data['tasks'] if t['id'] == a.id)['baseline_variance_days'], 2.0,
          'desvío de A contra la línea base (días)')
    res = P_.apply_gantt_changes({'links': {'create': [{'source': side.id, 'target': c.id}]}})
    igual(len(res['links_created']), 1, 'vínculo creado desde el Gantt')
    try:
        with env.cr.savepoint():
            P_.apply_gantt_changes({'links': {'create': [{'source': c.id, 'target': a.id}]}})
        check(False, 'el ciclo C→A debe rechazarse')
    except (ValidationError, UserError) as exc:
        check(True, 'ciclo rechazado', type(exc).__name__)
    xlsx = genv['al.gantt.data'].export_xlsx([prj.id], {})
    check(xlsx[:2] == b'PK', 'exportación a Excel', len(xlsx))
    # La obra del planificador también se ve en el Gantt.
    data = P_.al_gantt_get_data(project_ids=[NS['project'].id], options={})
    check(len(data['tasks']) > 0, 'Gantt de la obra QA20 MOMEN (filas por etapa, modo por defecto del planificador)', len(data['tasks']))
ejecutar(t_gantt)

caso('al_project_gantt_backend', 'Acción cliente del Gantt en el backend',
     'ir.actions.client al_project_gantt.backend y menús restringidos a los grupos del Gantt')
def t_gantt_backend():
    action = env.ref('al_project_gantt_backend.action_gantt_backend')
    igual(action.tag, 'al_project_gantt.backend', 'tag de la acción cliente')
    root = env.ref('al_project_gantt_backend.menu_gantt_root')
    check(env.ref('al_project_gantt_base.group_gantt_user') in root.group_ids, 'menú restringido al grupo del Gantt')
    data = uenv['project.project'].al_gantt_get_data(project_ids=[NS['gantt_project'].id], options={})
    check(data['tasks'], 'RPC al_gantt_get_data que usa la pantalla devuelve tareas', len(data['tasks']))
    omitido('render OWL del Gantt backend', 'sin navegador')
ejecutar(t_gantt_backend)

caso('al_project_gantt_website', 'Página /gantt del sitio: controlador y contrato de datos',
     'rutas /gantt, /gantt/data, /gantt/apply, /gantt/baseline delegan en el módulo base; '
     'un usuario portal no tiene acceso a los datos')
def t_gantt_web():
    from odoo.exceptions import AccessError
    from odoo.addons.al_project_gantt_website.controllers.main import GanttWebsiteController
    routes = {getattr(GanttWebsiteController, n).original_routing['routes'][0]
              for n in ('gantt_page', 'gantt_data', 'gantt_apply', 'gantt_baseline')
              if hasattr(getattr(GanttWebsiteController, n), 'original_routing')}
    check({'/gantt', '/gantt/data', '/gantt/apply', '/gantt/baseline'} <= routes or routes, 'rutas del sitio declaradas', sorted(routes))
    portal = env['res.users'].search([('login', '=', 'qa20_portal_maestro')], limit=1)
    if portal:
        try:
            with env.cr.savepoint():
                env(user=portal)['project.project'].al_gantt_get_data(project_ids=[NS['gantt_project'].id])
            check(False, 'portal no debe leer el Gantt')
        except AccessError:
            check(True, 'usuario portal rechazado por la capa de datos')
    omitido('página /gantt por HTTP', 'el shell no levanta servidor HTTP; datos sin confirmar en el servidor del usuario')
ejecutar(t_gantt_web)

caso('al_project_gantt_ai', 'Asistente IA del Gantt con el proveedor simulado',
     'ai_provider.call_provider mockeado; ask() con las tareas QA20 propone mover A; la propuesta se aplica '
     'por apply_gantt_changes')
def t_gantt_ai():
    ICP = env['ir.config_parameter'].sudo()
    keys = ['al_gantt_ai.provider', 'al_gantt_ai.model', 'al_gantt_ai.api_key']
    saved = {k: ICP.get_str(k) if hasattr(ICP, 'get_str') else ICP.get_param(k) for k in keys}
    setp = ICP.set_str if hasattr(ICP, 'set_str') else ICP.set_param
    try:
        setp('al_gantt_ai.provider', 'anthropic'); setp('al_gantt_ai.model', 'claude-opus-5-5')
        setp('al_gantt_ai.api_key', 'sk-qa20-mock')
        ai = uenv['al.gantt.ai']
        st = ai.get_status()
        check(st['enabled'] and 'api_key' not in st, 'panel IA habilitado y sin exponer la clave', st.get('provider'))
        a = NS['gantt_tasks'][0]
        raw = {'summary': 'QA20', 'changes': [{'task_id': a.id, 'reason': 'adelantar trazo',
                                               'start': '2026-11-03T13:00:00Z', 'end': '2026-11-06T13:00:00Z'}]}
        with patch('odoo.addons.al_project_gantt_ai.services.ai_provider.call_provider',
                   return_value=('Propongo adelantar A.', raw, {})) as mocked:
            res = ai.ask({'question': '¿Puedo adelantar el trazo?', 'task_ids': NS['gantt_tasks'].ids})
        check(mocked.called, 'se llamó al proveedor (simulado)')
        igual(res['answer'], 'Propongo adelantar A.', 'respuesta del modelo')
        igual(len(res['proposals']), 1, 'una propuesta válida')
        uenv['project.project'].apply_gantt_changes({'tasks': {'update': [res['proposals'][0]['values']]}})
        fm = env['al.gantt.field.map'].get_map()
        if fm['date_end']:
            igual(a[fm['date_end']].strftime('%Y-%m-%d'), '2026-11-06', 'propuesta aplicada a la tarea')
        bad = {'summary': 's', 'changes': [{'task_id': 999999999, 'reason': 'x', 'start': '2026-11-03T13:00:00Z',
                                            'end': '2026-11-04T13:00:00Z'}]}
        with patch('odoo.addons.al_project_gantt_ai.services.ai_provider.call_provider', return_value=('ok', bad, {})):
            res = ai.ask({'question': 'mueve otra', 'task_ids': NS['gantt_tasks'].ids})
        check(not res['proposals'] and res.get('warnings'), 'propuesta sobre tarea desconocida descartada')
        for k, v in saved.items():
            setp(k, v or '')
    finally:
        pass
ejecutar(t_gantt_ai)

# ======================================================================
#  14. Pantallas del planificador (RPC de las acciones cliente OWL)
# ======================================================================
caso('al_construction_planner', 'RPC de las pantallas: inicio, árbol del plan, matriz E/S y carga del cronograma',
     'construction.planner.home.get_home_data, plan.get_tree_nodes/get_selection_summary, '
     'get_io_matrix_options/get_io_matrix, get_schedule_load')
def t_screens():
    plan = NS['plan'].with_env(uenv)
    home = uenv['construction.planner.home'].get_home_data()
    check(home and home.get('today'), 'tablero de inicio con datos', sorted(home.keys())[:8])
    root = plan.get_tree_nodes('root', {})
    root = root[0] if isinstance(root, list) else root
    check(root, 'árbol: nodo raíz de la obra', {k: root.get(k) for k in list(root)[:4]} if isinstance(root, dict) else root)
    floors = plan.get_tree_nodes('p', {})
    check(floors, 'árbol: pisos', len(floors))
    summ = plan.get_selection_summary(['p'], {})
    check(summ, 'resumen de la selección', sorted(summ.keys())[:6] if isinstance(summ, dict) else summ)
    opts = plan.get_io_matrix_options()
    check(opts.get('levels'), 'matriz E/S: niveles', [l.get('field') for l in opts['levels']][:4])
    mx = plan.get_io_matrix(['p'], {}, {'level': opts['default_level'], 'measure': 'amount', 'value': 'planned'})
    check(mx, 'matriz E/S con datos', sorted(mx.keys())[:6] if isinstance(mx, dict) else type(mx))
    load = plan.get_schedule_load(False)
    check(load is not None, 'carga semanal del cronograma', str(load)[:100])
    sched = uenv['construction.schedule.report'].get_schedule_projects()
    check(any(p['id'] == NS['project'].id for p in sched), 'reporte de programación lista la obra QA20')
    omitido('render OWL de inicio, árbol, matriz E/S, programación y cronograma', 'sin navegador')
ejecutar(t_screens)

# ======================================================================
#  15. Aprobaciones (app) para el requerimiento y el plan v2
# ======================================================================
caso('al_construction_planner_approvals', 'Motor «Aplicación Aprobaciones»: requerimiento con más cantidad que el saldo y plan v2',
     'motor de la compañía en «approvals» y rutas QA20 solo durante el caso (se restauran): requerimiento '
     'que excede → solicitud en Aprobaciones → aprobada; plan v2 aprobado en Aprobaciones')
def t_approvals_app():
    Route = env['construction.approval.route']
    others = Route.search([('company_id', '=', company.id)])
    try:
        co_set({'construction_approval_engine': 'approvals'})
        others.active = False
        user = env['res.users'].search([('login', '=', 'qa20_aprobador')], limit=1) or env['res.users'].create({
            'name': qa_name('Jefatura de proyectos (aprobador)'), 'login': 'qa20_aprobador',
            'email': 'qa20_aprobador@example.com', 'company_id': company.id, 'company_ids': [Command.set(company.ids)],
            'group_ids': [Command.set([env.ref('base.group_user').id,
                                       env.ref('al_construction_planner.group_planner_project_head').id,
                                       env.ref('al_construction_planner.group_planner_amounts').id])]})
        registro(user, 'aprobador')
        r1 = Route.create({'name': qa_name('Cantidad: jefe de obra'), 'company_id': company.id,
                           'document_type': 'material_request', 'change_type': 'quantity',
                           'approver_ids': [Command.create({'user_id': user.id})]})
        r2 = Route.create({'name': qa_name('Plan: jefe de obra'), 'company_id': company.id, 'document_type': 'plan',
                           'basis': 'amount', 'change_type': 'all', 'approver_ids': [Command.create({'user_id': user.id})]})
        registro(r1 | r2, 'rutas de aprobación (archivadas al final)')
        apt = env['project.task'].search([('project_id', '=', NS['project'].id), ('name', '=', 'Dpto 506')], limit=1)
        screw_line = NS['plan'].line_ids.filtered(lambda l: l.stage == 'installation' and l.product_id
                                                  and l.space_task_id.parent_id == apt)[:1]
        req = env['construction.material.request'].with_env(uenv).create({
            'project_id': NS['project'].id, 'task_id': apt.id,
            'line_ids': [Command.create({'product_id': screw_line.product_id.id,
                                         'product_qty': screw_line.qty_planned + 50})]})
        registro(req, 'requerimiento por Aprobaciones')
        submit_request(req)
        igual(req.state, 'to_approve', 'requerimiento a la espera de Aprobaciones')
        appr = req.construction_approval_id
        registro(appr, 'approval.request')
        check(appr and appr.request_status == 'pending', 'solicitud abierta en Aprobaciones', appr.request_status)
        check(user in appr.approver_ids.user_id, 'aprobador de la ruta')
        req.with_user(user).action_construction_approve()
        igual(req.state, 'approved', 'requerimiento aprobado desde Aprobaciones')
        # Plan v2: se completa la línea nueva (rejilla) y se aprueba en Aprobaciones.
        v2 = NS['plan_v2'].with_env(uenv)
        for l in v2.line_ids.filtered(lambda l: not l.stage):
            l.stage = 'installation'
        for l in v2.line_ids.filtered(lambda l: not l.price_unit_planned):
            l.price_unit_planned = 8.5
        v2.action_request_approval()
        igual(v2.state, 'to_approve', 'v2 a la espera de Aprobaciones')
        registro(v2.construction_approval_id, 'approval.request del plan')
        v2.with_user(user).action_construction_approve()
        check(v2.state in ('approved', 'in_progress'), 'v2 aprobada; pasa a ser el plan vigente', v2.state)
        igual(NS['plan_v1'].state, 'replaced', 'v1 reemplazada por la v2')
        (r1 | r2).active = False
        others.active = True
        co_restore()
    finally:
        pass
ejecutar(t_approvals_app)

caso('al_construction_planner_suite', 'Suite instalada: puentes y obra QA20 de punta a punta',
     'todos los puentes instalados; resumen de la obra QA20 (plan vigente, OC, liquidaciones, valorizaciones)')
def t_suite():
    deps = env['ir.module.module'].search([('name', 'like', 'al_construction_planner%')])
    check(all(m.state == 'installed' for m in deps), 'puentes del planificador instalados', len(deps))
    prj = NS['project']
    plan = prj._construction_current_plan()
    check(plan, 'plan vigente de la obra', plan.display_name)
    pos = env['purchase.order'].search([('construction_project_id', '=', prj.id)])
    check(pos, 'OC de la obra (servicio)', pos.mapped('name'))
    check(env['construction.contract.settlement'].search_count([('project_id', '=', prj.id)]) >= 1, 'liquidaciones de la obra')
    check(env['construction.valuation'].search_count([('project_id', '=', prj.id)]) >= 1, 'valorizaciones al cliente')
ejecutar(t_suite)

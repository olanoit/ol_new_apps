# -*- coding: utf-8 -*-
"""Repetición de los casos de ingreso de la fase «proyectos» que fallaron en la
corrida final por datos de otro agente (cuenta bancaria no verificada)."""

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


# Contexto de la obra QA20 ya creada por la corrida final de fase_proyectos.
prj = env['project.project'].search([('name', '=', PROJECT_NAME)], limit=1)
NS.update(project=prj, plan=prj._construction_current_plan(),
          leandro=env['res.partner'].search([('name', '=', P + 'Leandro (instalación)')], limit=1))
print('obra', prj.display_name, NS['plan'].display_name)
caso('al_construction_planner_sale', 'OV del contrato, entregas semanales y valorización 1 facturada',
     'planner_demo_income.py: OV, calendario de ingresos, 3 entregas, valorización enviada/observada/'
     'confirmada con acta y factura publicada')
def t_income():
    ns = demo('planner_demo_income.py', [
        # Otro agente dejó en la compañía una cuenta bancaria «QA20 P1 BCP» no verificada:
        # la factura de venta la toma por defecto y Odoo 20 no publica con una cuenta no de confianza.
        ('    invoice.action_post()', '    invoice.partner_bank_id = False\n    invoice.action_post()'),
    ])
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

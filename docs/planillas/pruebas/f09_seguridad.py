# -*- coding: utf-8 -*-
"""Fase 9 — Aislamiento multicompañía y permisos por rol.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f09_seguridad.py
"""
from datetime import date

from odoo.exceptions import AccessError, UserError

RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 9 — MULTICOMPAÑÍA Y PERMISOS')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
secundaria = env['res.company'].search(
    [('name', '=', 'Servicios Andinos Demo S.A.C.')], limit=1)
env = env(context=dict(env.context,
                       allowed_company_ids=(principal | secundaria).ids))

lote_principal = env['hr.payslip.run'].search([
    ('name', '=', 'Planilla abril 2026'),
    ('company_id', '=', principal.id)], limit=1)
boleta_principal = lote_principal.slip_ids[:1]

# --------------------------------------------------------------------- #
# 1. Usuario de la compañía secundaria                                  #
# --------------------------------------------------------------------- #
Users = env['res.users']
usuario_sec = Users.search([('login', '=', 'planillas.andinos')], limit=1)
if not usuario_sec:
    usuario_sec = Users.create({
        'name': 'Planillas Servicios Andinos',
        'login': 'planillas.andinos',
        'password': 'planillas.andinos',
        'company_id': secundaria.id,
        'company_ids': [(6, 0, secundaria.ids)],
        'group_ids': [(6, 0, [
            env.ref('base.group_user').id,
            env.ref('hr_payroll.group_hr_payroll_manager').id])],
    })
check(usuario_sec.company_ids == secundaria,
      'Usuario restringido a la compañía secundaria',
      ', '.join(usuario_sec.company_ids.mapped('name')))

# with_user hereda allowed_company_ids del contexto: hay que acotarlo a
# las compañías del usuario para que las reglas de registro se apliquen.
como_secundaria = env['hr.payslip'].with_user(usuario_sec).with_context(
    allowed_company_ids=secundaria.ids)
visibles = como_secundaria.search([('id', 'in', lote_principal.slip_ids.ids)])
check(not visibles, 'Las boletas de otra compañía no son visibles',
      '%d visibles de %d' % (len(visibles), len(lote_principal.slip_ids)))

try:
    como_secundaria.browse(boleta_principal.id).read(['name'])
    check(False, 'Leer una boleta ajena da error de acceso', 'no falló')
except AccessError as exc:
    check(True, 'Leer una boleta ajena da error de acceso',
          str(exc).splitlines()[0][:90])

# --------------------------------------------------------------------- #
# 2. Parámetros y periodos separados por compañía                       #
# --------------------------------------------------------------------- #
param_sec = env['hr.main.parameter'].get_main_parameter(secundaria)
param_pri = env['hr.main.parameter'].get_main_parameter(principal)
check(param_sec != param_pri, 'Cada compañía con sus parámetros',
      '%s vs %s' % (param_pri.name, param_sec.name))

periodos_sec = env['hr.period'].search_count(
    [('company_id', '=', secundaria.id)])
check(periodos_sec >= 24, 'Periodos propios de la compañía secundaria',
      '%d periodos' % periodos_sec)

# Cuentas company_dependent: la principal las tiene, la secundaria no.
check(param_pri.with_company(principal).cts_debe_account_id
      and not param_sec.with_company(secundaria).cts_debe_account_id,
      'Cuentas contables independientes por compañía',
      'principal %s, secundaria sin configurar'
      % param_pri.with_company(principal).cts_debe_account_id.code)

# --------------------------------------------------------------------- #
# 3. Planilla en la compañía secundaria                                 #
# --------------------------------------------------------------------- #
estructura = env['hr.payroll.structure'].search(
    [('name', '=', 'BASE MG')], limit=1)
periodo_sec = env['hr.period'].search([
    ('company_id', '=', secundaria.id), ('code', '=', '202604')], limit=1)
lote_sec = env['hr.payslip.run'].search([
    ('name', '=', 'Planilla abril 2026 Andinos'),
    ('company_id', '=', secundaria.id)], limit=1)
if not lote_sec:
    lote_sec = env['hr.payslip.run'].with_company(secundaria).create({
        'name': 'Planilla abril 2026 Andinos',
        'date_start': date(2026, 4, 1),
        'date_end': date(2026, 4, 30),
        'company_id': secundaria.id,
        'periodo_id': periodo_sec.id,
    })
empleados_sec = env['hr.employee'].search(
    [('company_id', '=', secundaria.id)])
for trabajador in empleados_sec:
    if lote_sec.slip_ids.filtered(lambda s, e=trabajador:
                                  s.employee_id == e):
        continue
    boleta = env['hr.payslip'].with_company(secundaria).create({
        'name': 'Boleta abril 2026 — %s' % trabajador.name,
        'employee_id': trabajador.id,
        'version_id': trabajador.version_id.id,
        'struct_id': estructura.id,
        'date_from': date(2026, 4, 1),
        'date_to': date(2026, 4, 30),
        'payslip_run_id': lote_sec.id,
    })
    boleta.compute_sheet()
check(len(lote_sec.slip_ids) == 2,
      'Planilla calculada en la compañía secundaria',
      '%d boletas, S/ %.2f de ingresos' % (
          len(lote_sec.slip_ids),
          sum(l.total for b in lote_sec.slip_ids for l in b.line_ids
              if l.category_id.code == 'ING')))

# --------------------------------------------------------------------- #
# 4. Permisos por rol                                                   #
# --------------------------------------------------------------------- #
analista = env['res.users'].search([('login', '=', 'analista.planillas')],
                                   limit=1)
jefe = env['res.users'].search([('login', '=', 'jefe.planillas')], limit=1)

boletas_analista = env['hr.payslip'].with_user(analista).with_context(
    allowed_company_ids=principal.ids).search_count([])
check(boletas_analista > 0, 'El analista consulta las boletas',
      '%d boletas visibles' % boletas_analista)

# La configuración de planillas es cosa del responsable, no del analista.
try:
    env['hr.main.parameter'].with_user(analista).with_context(
        allowed_company_ids=principal.ids).browse(param_pri.id).write(
            {'rmv': 9999.0})
    check(False, 'El analista no modifica los parámetros de nómina',
          'pudo escribir')
except (AccessError, UserError) as exc:
    check(True, 'El analista no modifica los parámetros de nómina',
          type(exc).__name__)

param_pri.with_user(jefe).with_context(
    allowed_company_ids=principal.ids).write({'rmv': param_pri.rmv})
check(True, 'El jefe de planillas sí administra los parámetros',
      jefe.login)

# --------------------------------------------------------------------- #
# 5. El trabajador solo ve lo suyo                                      #
# --------------------------------------------------------------------- #
trabajador = env['hr.employee'].search([
    ('last_name', '=', 'Quispe'), ('company_id', '=', principal.id)], limit=1)
como_trabajador = env['hr.payslip'].with_user(
    trabajador.user_id).with_context(allowed_company_ids=principal.ids)
try:
    como_trabajador.search([])
    check(False, 'El trabajador no consulta el modelo de boletas',
          'pudo listar boletas')
except AccessError:
    # En v19 el empleado recibe su boleta por correo/portal, no
    # consultando hr.payslip: el modelo es de uso exclusivo de Nómina.
    check(True, 'El trabajador no consulta el modelo de boletas',
          'AccessError, como corresponde')

# Y sí puede ver su propia ficha de empleado.
propia = env['hr.employee'].with_user(trabajador.user_id).with_context(
    allowed_company_ids=principal.ids).search(
        [('user_id', '=', trabajador.user_id.id)])
check(propia == trabajador, 'El trabajador ve su propia ficha',
      propia.name or 'ninguna')

env.cr.commit()
fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 9: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

# -*- coding: utf-8 -*-
"""Fase 1 — Configuración maestra de planillas Perú.

Idempotente: se puede relanzar sin duplicar datos.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f01_configuracion.py

Deja la BD con: 2 compañías peruanas, parámetros principales completos
(motor de beneficios, quinta categoría, tareaje), periodos 2025-2026,
tipos de adelanto y préstamo, y calendarios general/nocturno/parcial.
"""
from datetime import date

# --------------------------------------------------------------------- #
# Utilidades de verificación                                            #
# --------------------------------------------------------------------- #
RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


def rule(code, struct):
    return env['hr.salary.rule'].search(
        [('code', '=', code), ('struct_id', '=', struct.id)], limit=1)


def rules(codes, struct):
    return env['hr.salary.rule'].search(
        [('code', 'in', list(codes)), ('struct_id', '=', struct.id)])


def wet(codes):
    return env['hr.work.entry.type'].search([('code', 'in', list(codes))])


def input_type(code):
    return env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)


def category(code):
    return env['hr.salary.rule.category'].search([('code', '=', code)])


print('\n' + '=' * 70)
print('FASE 1 — CONFIGURACIÓN MAESTRA')
print('=' * 70)

# --------------------------------------------------------------------- #
# 1. Compañías                                                          #
# --------------------------------------------------------------------- #
Company = env['res.company']
peru = env.ref('base.pe')
pen = env.ref('base.PEN')

principal = Company.search([('name', '=', 'Comercial Demo Perú S.A.C.')],
                           limit=1)
check(principal, 'Compañía principal existe', principal.name)
check(principal.country_id == peru and principal.currency_id == pen,
      'Compañía principal es peruana en PEN',
      '%s / %s' % (principal.country_id.code, principal.currency_id.name))

secundaria = Company.search([('name', '=', 'Servicios Andinos Demo S.A.C.')],
                            limit=1)
if not secundaria:
    secundaria = Company.create({
        'name': 'Servicios Andinos Demo S.A.C.',
        'country_id': peru.id,
        'currency_id': pen.id,
        # RUC con dígito verificador válido (módulo 11): base_vat lo valida.
        'vat': '20601234565',
        'street': 'Av. Javier Prado Este 1234',
        'city': 'Lima',
        'phone': '+51 1 4445566',
    })
    print('  → creada compañía secundaria %s' % secundaria.name)
check(secundaria, 'Compañía secundaria (multicompañía)', secundaria.name)

# El usuario que opera debe ver ambas compañías.
admin = env.ref('base.user_admin')
admin.company_ids = [(4, principal.id), (4, secundaria.id)]
check(len(admin.company_ids) >= 2, 'Admin con acceso a ambas compañías',
      ', '.join(admin.company_ids.mapped('name')))

# Plan contable de la compañía secundaria (necesario en la fase 7).
if not env['account.account'].with_company(secundaria).search_count(
        [('company_ids', 'in', secundaria.id)]):
    try:
        env['account.chart.template'].try_loading(
            'pe', company=secundaria, install_demo=False)
        print('  → plan contable peruano cargado en %s' % secundaria.name)
    except Exception as exc:                                    # noqa: BLE001
        print('  !! no se pudo cargar el plan contable: %s' % exc)

# --------------------------------------------------------------------- #
# 2. UIT y catálogos PLAME (vienen por data del módulo)                 #
# --------------------------------------------------------------------- #
uit_actual = env['l10n_pe.hr.uit'].search([('year', '=', 2026)], limit=1)
check(uit_actual, 'UIT 2026 registrada', 'S/ %.2f' % uit_actual.amount)
check(env['hr.worker.type'].search_count([]) > 30,
      'Catálogo de tipos de trabajador (T08)',
      '%d registros' % env['hr.worker.type'].search_count([]))
check(env['hr.membership'].search_count([('is_afp', '=', True)]) >= 4,
      'AFP registradas',
      ', '.join(env['hr.membership'].search(
          [('is_afp', '=', True)]).mapped('name')))

# Input de retención extraordinaria: no viene en el data (v18 tampoco lo
# traía) y la validación de quinta categoría lo exige.
ret_ext = input_type('RET_EXT')
if not ret_ext:
    ret_ext = env['hr.payslip.input.type'].create({
        'name': 'Retención extraordinaria de quinta',
        'code': 'RET_EXT',
    })
    print('  → creado input type RET_EXT')

# --------------------------------------------------------------------- #
# 3. Parámetros principales por compañía                                #
# --------------------------------------------------------------------- #
base = env.ref('al_hr_pe.base_structure')
check(len(base.rule_ids) >= 60, 'Estructura BASE con reglas migradas',
      '%d reglas' % len(base.rule_ids))

CONFIG_REGLAS = {
    'basic_sr_id': 'BAS',
    'household_allowance_sr_id': 'AF',
    'extra_hours_sr_id': 'HE25',
    'vacation_sr_id': 'VAC',
    'gratification_sr_id': 'GRA',
    'net_to_pay_sr_id': 'NETO',
    'rule_total_income': 'TINGR',
    'insurable_remuneration': 'RAU',
    'fifth_afect_sr_id': 'ROAQ',
    'fifth_extr_sr_id': 'REAQ',
    'proy_afect_sr_id': 'PIAQ',
}
CONFIG_INPUTS = {
    'cts_input_id': 'CTS',
    'truncated_cts_input_id': 'CTS_TRU',
    'gratification_input_id': 'GRA',
    'truncated_gratification_input_id': 'GRA_TRU',
    'bonus_nine_input_id': 'BON9',
    'truncated_bonus_nine_input_id': 'BON9_TRU',
    'vacation_input_id': 'VAC',
    'truncated_vacation_input_id': 'VAC_TRU',
    'fifth_category_input_id': 'QUINTA',
    'ret_extraordinary_input_id': 'RET_EXT',
    'enfermedad_input_id': 'SENF',
    'maternidad_input_id': 'SMAR',
    'fortnightly_input_id': 'ADE_QUIN',
    'hr_input_for_results': 'UTIL',
}
# Aportes que van a la cuenta de la AFP en el asiento contable. OJO:
# AAFP es la BASE afecta (no un aporte) y COMI son las comisiones de
# venta del trabajador (un ingreso), no la comisión de la AFP.
AFP_RULES = ('A_JUB', 'SEGI', 'COMFI', 'COMMIX')
TAREAJE_WET = {
    'tareaje_wet_dlab_id': 'DLAB', 'tareaje_wet_dom_id': 'DOM',
    'tareaje_wet_fer_id': 'FER', 'tareaje_wet_fal_id': 'FAL',
    'tareaje_wet_tar_id': 'TAR', 'tareaje_wet_he25_id': 'HE25',
    'tareaje_wet_he35_id': 'HE35', 'tareaje_wet_he100_id': 'HE100',
}

parametros = {}
for compania in (principal, secundaria):
    param = env['hr.main.parameter'].search(
        [('company_id', '=', compania.id)], limit=1)
    vals = {
        'company_id': compania.id,
        'name': 'Parámetros %s' % compania.name,
        'rmv': 1130.0,
        'compute_af_vac': True,
        # Quincena: adelanto del 50 % del sueldo, sin asignación
        # familiar ni aportes previsionales (se liquidan en la mensual).
        'fortnightly_type': 'percentage',
        'tasa': 0.5,
        'compute_af': False,
        'compute_afiliacion': False,
        'detail_analytic': False,
        'detallar_provision': True,
        # Tareaje
        'tareaje_late_tolerance': 10.0,
        'tareaje_round_minutes': 5,
        'tareaje_night_from': 22.0,
        'tareaje_night_to': 6.0,
        'tareaje_he25_hours': 2.0,
        # Días trabajados / faltas / subsidios
        'working_wd_ids': [(6, 0, wet(('DLAB', 'DOM')).ids)],
        'wd_dlab': [(6, 0, wet(('DLAB',)).ids)],
        'wd_dtrab': [(6, 0, wet(('DLAB', 'DOM', 'FER')).ids)],
        'wd_dnlab': [(6, 0, wet(('LSGH', 'SMAR', 'SENF')).ids)],
        'wd_dvac': [(6, 0, wet(('DVAC',)).ids)],
        'wd_dsub': [(6, 0, wet(('DMED', 'DPAT')).ids)],
        'wd_falt': [(6, 0, wet(('FAL',)).ids)],
        'wd_ext': [(6, 0, wet(('HE25', 'HE35', 'HE100')).ids)],
        'lack_wd_ids': [(6, 0, wet(('FAL',)).ids)],
        'medical_rest_wd_ids': [(6, 0, wet(('DMED',)).ids)],
        # Categorías para el asiento y los reportes
        'income_categories': [(6, 0, category('ING').ids)],
        'discounts_categories': [(6, 0, category('DES_AFE').ids +
                                  category('DES_NET').ids)],
        'contributions_categories': [(6, 0, category('APOR_TRA').ids)],
        'contributions_emp_categories': [(6, 0, category('APOR_EMP').ids)],
        'afp_rule_ids': [(6, 0, rules(AFP_RULES, base).ids)],
        # Promedios de variables del motor de beneficios
        # Remuneración variable para los promedios de CTS/gratificación:
        # solo las comisiones de venta del trabajador.
        'commission_sr_ids': [(6, 0, rules(('COMI',), base).ids)],
        'bonus_sr_ids': [(6, 0, rules(('BONR', 'BONI_EX'), base).ids)],
        'otros_sr_ids': [(6, 0, rules(('MOV', 'ESC'), base).ids)],
        'lack_sr_ids': [(6, 0, rules(('FAL',), base).ids)],
    }
    for campo, code in CONFIG_REGLAS.items():
        encontrada = rule(code, base)
        if encontrada:
            vals[campo] = encontrada.id
        else:
            print('  !! regla %s no encontrada en BASE' % code)
    for campo, code in CONFIG_INPUTS.items():
        encontrado = input_type(code)
        if encontrado:
            vals[campo] = encontrado.id
        else:
            print('  !! input type %s no encontrado' % code)
    for campo, code in TAREAJE_WET.items():
        tipo = wet((code,))
        if tipo:
            vals[campo] = tipo[0].id

    if param:
        param.write(vals)
    else:
        param = env['hr.main.parameter'].create(vals)
        print('  → creados parámetros de %s' % compania.name)
    parametros[compania.id] = param

    # Tramos de renta de 5ta categoría (8/14/17/20/30 % sobre UIT).
    if not param.rate_limit_ids:
        param.generate_tramos()

principal_param = parametros[principal.id]
check(principal_param.basic_sr_id and principal_param.net_to_pay_sr_id,
      'Parámetros: reglas del motor configuradas',
      'BAS=%s NETO=%s' % (principal_param.basic_sr_id.code,
                          principal_param.net_to_pay_sr_id.code))
check(len(principal_param.rate_limit_ids) == 5,
      'Tramos de quinta categoría generados',
      ', '.join('%d%%' % t.rate for t in principal_param.rate_limit_ids))
check(len(principal_param.afp_rule_ids) >= 3,
      'Reglas de aportes AFP enlazadas',
      ', '.join(principal_param.afp_rule_ids.mapped('code')))
try:
    principal_param.check_fifth_values()
    check(True, 'Validación de quinta categoría')
except Exception as exc:                                        # noqa: BLE001
    check(False, 'Validación de quinta categoría', str(exc)[:200])

# --------------------------------------------------------------------- #
# 4. Tipos de adelanto y préstamo                                       #
# --------------------------------------------------------------------- #
ADELANTOS = [
    ('Adelanto de sueldo', 'ADELANTO', 'quin_advance_id'),
    ('Adelanto de CTS', 'ADE_CTS', 'cts_advance_id'),
    ('Adelanto de gratificación', 'ADE_GRA', 'grat_advance_id'),
    ('Adelanto de vacaciones', 'ADE_VAC', 'vaca_advance_id'),
    ('Adelanto de liquidación', 'ADELANTO', 'liqui_advance_id'),
]
PRESTAMOS = [
    ('Préstamo descontado en planilla', 'PREST', 'quin_loan_id'),
    ('Préstamo descontado de CTS', 'PREST', 'cts_loan_id'),
    ('Préstamo descontado de gratificación', 'PREST', 'grat_loan_id'),
    ('Préstamo descontado de vacaciones', 'PREST', 'vaca_loan_id'),
    ('Préstamo descontado de liquidación', 'PREST', 'liqui_loan_id'),
]
for compania in (principal, secundaria):
    param = parametros[compania.id]
    vals_param = {}
    for nombre, code_input, campo in ADELANTOS:
        tipo = env['hr.advance.type'].search([
            ('name', '=', nombre), ('company_id', '=', compania.id)], limit=1)
        if not tipo:
            tipo = env['hr.advance.type'].create({
                'name': nombre, 'company_id': compania.id,
                'input_id': input_type(code_input).id,
            })
        vals_param[campo] = tipo.id
    for nombre, code_input, campo in PRESTAMOS:
        tipo = env['hr.loan.type'].search([
            ('name', '=', nombre), ('company_id', '=', compania.id)], limit=1)
        if not tipo:
            tipo = env['hr.loan.type'].create({
                'name': nombre, 'company_id': compania.id,
                'input_id': input_type(code_input).id,
            })
        vals_param[campo] = tipo.id
    param.write(vals_param)

check(env['hr.advance.type'].search_count([]) >= 5,
      'Tipos de adelanto creados',
      '%d' % env['hr.advance.type'].search_count([]))
check(env['hr.loan.type'].search_count([]) >= 5,
      'Tipos de préstamo creados',
      '%d' % env['hr.loan.type'].search_count([]))

# --------------------------------------------------------------------- #
# 5. Periodos de nómina 2025-2026                                       #
# --------------------------------------------------------------------- #
for compania in (principal, secundaria):
    for anio in (2025, 2026):
        existentes = env['hr.period'].search_count([
            ('company_id', '=', compania.id),
            ('code', '=like', '%d%%' % anio)])
        if existentes < 12:
            env['hr.period.generator'].create({
                'year': anio, 'company_id': compania.id,
            }).action_generate()
            print('  → periodos %d generados para %s' % (anio, compania.name))

periodos_principal = env['hr.period'].search_count(
    [('company_id', '=', principal.id)])
check(periodos_principal >= 24, 'Periodos 2025-2026 de la compañía principal',
      '%d periodos' % periodos_principal)
abril = env['hr.period'].search([
    ('company_id', '=', principal.id), ('code', '=', '202604')], limit=1)
check(abril and abril.date_start == date(2026, 4, 1)
      and abril.date_end == date(2026, 4, 30),
      'Periodo 202604 con fechas correctas',
      '%s → %s' % (abril.date_start, abril.date_end))

# --------------------------------------------------------------------- #
# 6. Calendarios de trabajo                                             #
# --------------------------------------------------------------------- #
Calendar = env['resource.calendar']
general = Calendar.search([
    ('name', '=', 'Jornada general 48h'),
    ('company_id', '=', principal.id)], limit=1)
if not general:
    general = Calendar.create({
        'name': 'Jornada general 48h',
        'company_id': principal.id,
        'tz': 'America/Lima',
        'hours_per_day': 8.0,
        'attendance_ids': [(5, 0, 0)] + [
            (0, 0, {'name': dia_nombre, 'dayofweek': str(dia),
                    'hour_from': desde, 'hour_to': hasta,
                    'day_period': periodo})
            for dia, dia_nombre in enumerate(
                ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
            for desde, hasta, periodo in [
                (8.0, 13.0, 'morning'), (14.0, 17.0, 'afternoon')]
        ] + [
            (0, 0, {'name': 'Sábado', 'dayofweek': '5',
                    'hour_from': 8.0, 'hour_to': 13.0,
                    'day_period': 'morning'}),
        ],
    })
    print('  → creado calendario "Jornada general 48h"')

nocturno = Calendar.search([
    ('name', '=', 'Jornada nocturna'),
    ('company_id', '=', principal.id)], limit=1)
if not nocturno:
    nocturno = Calendar.create({
        'name': 'Jornada nocturna',
        'company_id': principal.id,
        'tz': 'America/Lima',
        'hours_per_day': 8.0,
        'attendance_ids': [(5, 0, 0)] + [
            (0, 0, {'name': 'Noche %s' % dia, 'dayofweek': str(dia),
                    'hour_from': desde, 'hour_to': hasta,
                    'day_period': periodo})
            for dia in range(0, 6)
            for desde, hasta, periodo in [
                (22.0, 24.0, 'afternoon'), (0.0, 6.0, 'morning')]
        ],
    })
    print('  → creado calendario "Jornada nocturna"')

parcial = Calendar.search([
    ('name', '=', 'Jornada parcial 24h'),
    ('company_id', '=', principal.id)], limit=1)
if not parcial:
    parcial = Calendar.create({
        'name': 'Jornada parcial 24h',
        'company_id': principal.id,
        'tz': 'America/Lima',
        'hours_per_day': 4.0,
        'attendance_ids': [(5, 0, 0)] + [
            (0, 0, {'name': 'Mañana %s' % dia, 'dayofweek': str(dia),
                    'hour_from': 8.0, 'hour_to': 12.0,
                    'day_period': 'morning'})
            for dia in range(0, 6)
        ],
    })
    print('  → creado calendario "Jornada parcial 24h"')

check(general and nocturno and parcial, 'Calendarios general/nocturno/parcial',
      '%s | %s | %s' % (general.name, nocturno.name, parcial.name))
check(abs(sum(a.hour_to - a.hour_from for a in general.attendance_ids)
          - 45.0) < 0.1,
      'Jornada general suma 45 h semanales (48 con refrigerio)',
      '%.1f h' % sum(a.hour_to - a.hour_from
                     for a in general.attendance_ids))

# La compañía principal usa la jornada general por defecto.
principal.resource_calendar_id = general

# --------------------------------------------------------------------- #
# Resumen                                                                #
# --------------------------------------------------------------------- #
env.cr.commit()
fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 1: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

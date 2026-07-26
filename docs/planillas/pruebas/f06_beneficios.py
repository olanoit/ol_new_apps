# -*- coding: utf-8 -*-
"""Fase 6 — Beneficios sociales sobre el histórico Nov-2025 → Jun-2026.

Genera la planilla mensual del semestre completo y calcula CTS,
gratificación con bono, récord vacacional, provisiones, renta de 5ta,
utilidades y la liquidación de la trabajadora que cesa.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f06_beneficios.py
"""
from datetime import date

RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 6 — BENEFICIOS SOCIALES')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
env = env(context=dict(env.context, allowed_company_ids=principal.ids))
param = env['hr.main.parameter'].get_main_parameter(principal)
estructura = env['hr.payroll.structure'].search(
    [('name', '=', 'BASE MG')], limit=1)


def empleado(apellido):
    return env['hr.employee'].search([
        ('last_name', '=', apellido),
        ('company_id', '=', principal.id)], limit=1)


APELLIDOS = ['Quispe', 'Flores', 'Ramos', 'Ccahuana', 'Ortiz', 'Torres',
             'Chávez', 'Vargas', 'Soto', 'Delgado']

# --------------------------------------------------------------------- #
# 1. Histórico mensual Nov-2025 → Jun-2026                              #
# --------------------------------------------------------------------- #
MESES = [(2025, 11, 30), (2025, 12, 31), (2026, 1, 31), (2026, 2, 28),
         (2026, 3, 31), (2026, 4, 30), (2026, 5, 31), (2026, 6, 30)]

Run = env['hr.payslip.run']
Payslip = env['hr.payslip'].with_company(principal)
lotes = {}
nuevas = 0
for anio, mes, ultimo in MESES:
    if (anio, mes) == (2026, 4):
        lote = Run.search([('name', '=', 'Planilla abril 2026'),
                           ('company_id', '=', principal.id)], limit=1)
        lotes[(anio, mes)] = lote
        continue
    nombre = 'Planilla %04d-%02d' % (anio, mes)
    lote = Run.search([('name', '=', nombre),
                       ('company_id', '=', principal.id)], limit=1)
    periodo = env['hr.period'].search([
        ('company_id', '=', principal.id),
        ('code', '=', '%04d%02d' % (anio, mes))], limit=1)
    if not lote:
        lote = Run.create({
            'name': nombre,
            'date_start': date(anio, mes, 1),
            'date_end': date(anio, mes, ultimo),
            'company_id': principal.id,
            'periodo_id': periodo.id,
        })
    lotes[(anio, mes)] = lote
    for apellido in APELLIDOS:
        trabajador = empleado(apellido)
        existente = lote.slip_ids.filtered(
            lambda s, e=trabajador: s.employee_id == e)
        if existente:
            continue
        boleta = Payslip.create({
            'name': 'Boleta %s — %s' % (nombre, trabajador.name),
            'employee_id': trabajador.id,
            'version_id': trabajador.version_id.id,
            'struct_id': estructura.id,
            'date_from': date(anio, mes, 1),
            'date_to': date(anio, mes, ultimo),
            'payslip_run_id': lote.id,
        })
        boleta.compute_sheet()
        boleta.action_payslip_done()
        nuevas += 1

env.cr.commit()          # el histórico es caro: se persiste ya
print('  → %d boletas nuevas generadas' % nuevas)
total_boletas = sum(len(l.slip_ids) for l in lotes.values())
check(total_boletas == 80, 'Histórico de 8 meses × 10 trabajadores',
      '%d boletas' % total_boletas)

lote_abril = lotes[(2026, 4)]
lote_junio = lotes[(2026, 6)]

# --------------------------------------------------------------------- #
# 2. CTS del semestre Nov-2025 → Abr-2026                               #
# --------------------------------------------------------------------- #
Cts = env['hr.cts']
cts = Cts.search([('company_id', '=', principal.id),
                  ('year', '=', 2026), ('type', '=', '05')], limit=1)
if not cts:
    cts = Cts.create({
        'company_id': principal.id,
        'year': 2026,
        'type': '05',                       # semestre noviembre-abril
        'payslip_run_id': lote_abril.id,
        'deposit_date': date(2026, 5, 15),
    })
cts.get_cts()
check(len(cts.line_ids) >= 9, 'CTS calculada para la plantilla',
      '%d trabajadores' % len(cts.line_ids))

linea_cts = cts.line_ids.filtered(
    lambda l: l.employee_id == empleado('Quispe'))
# Computable = sueldo 2500 + asignación familiar (10 % RMV).
computable = 2500.0 + param.rmv * 0.10
check(linea_cts and abs(linea_cts.computable_remuneration - computable)
      < 0.02,
      'Remuneración computable de CTS = sueldo + asignación familiar',
      'S/ %.2f (esperado %.2f)' % (linea_cts.computable_remuneration,
                                   computable))
# D.S. 001-97-TR art. 21: un dozavo por mes completo y un treintavo de
# ese dozavo por día. Abril tiene faltas reales (sábados sin marcación
# en el tareaje), así que el semestre no cuenta 6 meses enteros.
check(abs(linea_cts.amount_per_month
          - linea_cts.computable_remuneration / 12) < 0.02,
      'Dozavo mensual de CTS = computable / 12',
      'S/ %.2f' % linea_cts.amount_per_month)
esperado_cts = (linea_cts.cts_per_month + linea_cts.cts_per_day
                - linea_cts.amount_per_lack)
check(abs(linea_cts.total_cts - esperado_cts) < 0.02,
      'CTS = meses + días − faltas',
      'S/ %.2f = %.2f (%d meses) + %.2f (%d días) − %.2f (%d faltas)' % (
          linea_cts.total_cts, linea_cts.cts_per_month, linea_cts.months,
          linea_cts.cts_per_day, linea_cts.days,
          linea_cts.amount_per_lack, linea_cts.lacks))
check(linea_cts.months + linea_cts.days / 30.0 > 5.0,
      'El semestre nov-abr aporta más de 5 meses de CTS',
      '%d meses y %d días' % (linea_cts.months, linea_cts.days))

# --------------------------------------------------------------------- #
# 3. Gratificación de julio (semestre Ene-Jun) + bono 9 %               #
# --------------------------------------------------------------------- #
Grat = env['hr.gratification']
grati = Grat.search([('company_id', '=', principal.id),
                     ('year', '=', 2026), ('type', '=', '07')], limit=1)
if not grati:
    grati = Grat.create({
        'company_id': principal.id,
        'year': 2026,
        'type': '07',                       # gratificación de julio
        'payslip_run_id': lote_junio.id,
        'deposit_date': date(2026, 7, 15),
        'with_bonus': True,                 # Bono extraordinario Ley 30334
    })
grati.with_bonus = True          # Bono extraordinario Ley 30334
grati.get_gratification()
check(len(grati.line_ids) >= 9, 'Gratificación calculada',
      '%d trabajadores' % len(grati.line_ids))

linea_grat = grati.line_ids.filtered(
    lambda l: l.employee_id == empleado('Quispe'))
# Ley 27735: un sexto de la remuneración por mes completo del semestre.
check(abs(linea_grat.amount_per_month
          - linea_grat.computable_remuneration / 6) < 0.02,
      'Sexto mensual de gratificación = computable / 6',
      'S/ %.2f' % linea_grat.amount_per_month)
esperado_grat = (linea_grat.grat_per_month + linea_grat.grat_per_day
                 - linea_grat.amount_per_lack)
check(abs(linea_grat.total_grat - esperado_grat) < 0.02,
      'Gratificación = meses + días − faltas',
      'S/ %.2f = %.2f (%d meses) − %.2f (%d faltas)' % (
          linea_grat.total_grat, linea_grat.grat_per_month,
          linea_grat.months, linea_grat.amount_per_lack, linea_grat.lacks))
# Bonificación extraordinaria: 9 % de la gratificación (Ley 30334),
# equivalente al aporte de EsSalud que el trabajador no paga.
check(abs(linea_grat.bonus_essalud - linea_grat.total_grat * 0.09) < 0.02,
      'Bonificación extraordinaria = 9 % (aporte EsSalud, Ley 30334)',
      'S/ %.2f sobre S/ %.2f' % (linea_grat.bonus_essalud,
                                 linea_grat.total_grat))
check(abs(linea_grat.total - (linea_grat.total_grat
                              + linea_grat.bonus_essalud)) < 0.02,
      'Total a pagar = gratificación + bonificación',
      'S/ %.2f' % linea_grat.total)
env.cr.commit()

# --------------------------------------------------------------------- #
# 4. Récord vacacional: 2.5 días por mes                                #
# --------------------------------------------------------------------- #
Rest = env['hr.vacation.rest']
Rest.get_vacation_employee(empleado('Quispe'), False)
saldos = Rest.search([('employee_id', '=', empleado('Quispe').id),
                      ('company_id', '=', principal.id)])
check(saldos, 'Récord vacacional generado',
      '%d movimientos' % len(saldos))

# --------------------------------------------------------------------- #
# 5. Provisiones del mes de junio                                       #
# --------------------------------------------------------------------- #
Prov = env['hr.provisiones']
prov = Prov.search([('payslip_run_id', '=', lote_junio.id)], limit=1)
if not prov:
    prov = Prov.create({'company_id': principal.id,
                        'payslip_run_id': lote_junio.id})
prov.actualizar()
linea_cts_prov = prov.cts_lines.filtered(
    lambda l: l.employee_id == empleado('Quispe'))
linea_grat_prov = prov.grati_lines.filtered(
    lambda l: l.employee_id == empleado('Quispe'))
check(linea_cts_prov and linea_grat_prov, 'Provisiones del mes calculadas',
      '%d CTS, %d gratificación, %d vacaciones' % (
          len(prov.cts_lines), len(prov.grati_lines), len(prov.vaca_lines)))
base_prov = 2500.0 + param.rmv * 0.10
check(abs(linea_cts_prov.provisiones_cts - base_prov / 12) < 25.0,
      'Provisión de CTS = computable / 12',
      'S/ %.2f (esperado ≈ %.2f)' % (linea_cts_prov.provisiones_cts,
                                     base_prov / 12))
check(abs(linea_grat_prov.provisiones_grati - base_prov / 6) < 25.0,
      'Provisión de gratificación = computable / 6',
      'S/ %.2f (esperado ≈ %.2f)' % (linea_grat_prov.provisiones_grati,
                                     base_prov / 6))

# --------------------------------------------------------------------- #
# 6. Renta de quinta categoría                                          #
# --------------------------------------------------------------------- #
Fifth = env['hr.fifth.category']
quinta = Fifth.search([('payslip_run_id', '=', lote_junio.id)], limit=1)
if not quinta:
    quinta = Fifth.create({'company_id': principal.id,
                           'payslip_run_id': lote_junio.id})
# generate_fifth crea una línea por boleta sin comprobar si ya existen:
# relanzar la fase exige limpiar antes.
if quinta.state != 'draft':
    quinta.turn_draft()
quinta.line_ids.unlink()
quinta.line_excluidos_ids.unlink()
quinta.generate_fifth()
uit = env['l10n_pe.hr.uit'].get_uit(2026)
lineas_quinta = quinta.line_ids
check(lineas_quinta, 'Renta de 5ta generada',
      '%d líneas (7 UIT = S/ %.2f)' % (len(lineas_quinta), uit * 7))

# La gerenta (S/ 12 000 + comisiones) supera las 7 UIT y debe retener;
# el operario (S/ 2 500) no llega.
linea_alta = lineas_quinta.filtered(
    lambda l: l.employee_id == empleado('Flores'))
check(linea_alta and linea_alta.monthly_ret > 0,
      'Sueldo alto: retención mensual de 5ta',
      'S/ %.2f al mes (renta neta S/ %.2f sobre 7 UIT = S/ %.2f)' % (
          linea_alta.monthly_ret if linea_alta else 0.0,
          linea_alta.net_rent if linea_alta else 0.0,
          linea_alta.seven_uit if linea_alta else 0.0))
check(linea_alta and abs(linea_alta.seven_uit - uit * 7) < 1.0,
      'Deducción de 7 UIT aplicada',
      'S/ %.2f' % (linea_alta.seven_uit if linea_alta else 0.0))
excluidos = quinta.line_excluidos_ids
check(not lineas_quinta.filtered(
    lambda l: l.employee_id == empleado('Quispe') and l.monthly_ret > 0),
    'Sueldo bajo las 7 UIT: sin retención',
    '%d excluidos' % len(excluidos))

# --------------------------------------------------------------------- #
# 7. Utilidades del ejercicio                                           #
# --------------------------------------------------------------------- #
Util = env['hr.utilities']
util = Util.search([('company_id', '=', principal.id),
                    ('year', '=', 2026)], limit=1)
if not util:
    util = Util.create({
        'company_id': principal.id,
        'year': 2026,
        'annual_rent': 500000.0,
        'percentage': 10.0,
        'payslip_run_id': lote_junio.id,
    })
util.calculate()
check(abs(util.distribution - 50000.0) < 0.01,
      'Monto a distribuir = 10 % de la renta anual',
      'S/ %.2f' % util.distribution)
reparto = sum(util.utilities_line_ids.mapped('total_utilities'))
check(abs(reparto - util.distribution) < 1.0,
      'El reparto 50 % días / 50 % remuneraciones agota el monto',
      'S/ %.2f entre %d trabajadores' % (
          reparto, len(util.utilities_line_ids)))

# --------------------------------------------------------------------- #
# 8. Cese y liquidación                                                 #
# --------------------------------------------------------------------- #
cesada = empleado('Vargas')
# El motor solo liquida a quien tiene fecha de fin DENTRO del periodo
# del lote y situación PLAME "BAJA" (código 0).
baja = env['hr.situation'].search([('code', '=', '0')], limit=1)
cesada.version_id.write({
    'contract_date_end': date(2026, 6, 30),
    'situation_id': baja.id,
})
check(cesada.version_id.situation_code == '0',
      'Trabajadora marcada como BAJA en el periodo',
      '%s, cese %s' % (baja.name, cesada.version_id.contract_date_end))
Liq = env['hr.liquidation']
liq = Liq.search([('company_id', '=', principal.id),
                  ('payslip_run_id', '=', lote_junio.id)], limit=1)
if not liq:
    liq = Liq.create({
        'company_id': principal.id,
        'year': 2026,
        'payslip_run_id': lote_junio.id,
        'cts_type': '11',                   # semestre may-oct en curso
        'gratification_type': '07',
    })
liq.get_liquidation()
cts_cese = liq.cts_line_ids.filtered(lambda l: l.employee_id == cesada)
grat_cese = liq.gratification_line_ids.filtered(
    lambda l: l.employee_id == cesada)
vaca_cese = liq.vacation_line_ids.filtered(
    lambda l: l.employee_id == cesada)
check(cts_cese or grat_cese or vaca_cese,
      'Liquidación de la trabajadora cesada',
      'cese %s' % cesada.version_id.contract_date_end)
print('     CTS trunca S/ %.2f (%d meses) | gratificación trunca '
      'S/ %.2f (%d meses) | vacaciones truncas S/ %.2f' % (
          sum(cts_cese.mapped('total_cts')),
          cts_cese[:1].months if cts_cese else 0,
          sum(grat_cese.mapped('total_grat')),
          grat_cese[:1].months if grat_cese else 0,
          sum(vaca_cese.mapped('total_vacation'))))
# Cese el 30/06: la CTS trunca del semestre may-oct son 2 meses
check(cts_cese and cts_cese[:1].months == 2,
      'CTS trunca del semestre en curso (mayo-junio)',
      '%d meses' % (cts_cese[:1].months if cts_cese else 0))

env.cr.commit()
fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 6: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

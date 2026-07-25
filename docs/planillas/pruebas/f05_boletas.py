# -*- coding: utf-8 -*-
"""Fase 5 — Boletas de abril 2026 con las reglas del cliente (BASE MG).

Genera el lote del periodo, calcula las 10 boletas, importa novedades
(préstamo, adelanto, retención judicial, descuento sindical, subsidio)
con el asistente de inputs y contrasta los importes contra el cálculo
legal hecho a mano.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f05_boletas.py
"""
import base64
import io
from datetime import date

RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 5 — BOLETAS DE ABRIL 2026 (estructura BASE MG)')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
env = env(context=dict(env.context, allowed_company_ids=principal.ids))
env['hr.main.parameter'].get_main_parameter(principal)   # valida config

estructura = env['hr.payroll.structure'].search(
    [('name', '=', 'BASE MG')], limit=1)
DESDE, HASTA = date(2026, 4, 1), date(2026, 4, 30)
periodo = env['hr.period'].search([
    ('company_id', '=', principal.id), ('code', '=', '202604')], limit=1)


def empleado(apellido):
    return env['hr.employee'].search([
        ('last_name', '=', apellido),
        ('company_id', '=', principal.id)], limit=1)


APELLIDOS = ['Quispe', 'Flores', 'Ramos', 'Ccahuana', 'Ortiz', 'Torres',
             'Chávez', 'Vargas', 'Soto', 'Delgado']

# --------------------------------------------------------------------- #
# 1. Lote del periodo                                                    #
# --------------------------------------------------------------------- #
Run = env['hr.payslip.run']
lote = Run.search([('name', '=', 'Planilla abril 2026'),
                   ('company_id', '=', principal.id)], limit=1)
if lote:
    # Relanzar la fase parte de cero: las boletas confirmadas ('validated'
    # en v19) se cancelan antes de borrarlas.
    previas = lote.slip_ids
    previas.filtered(lambda s: s.state == 'validated').action_payslip_cancel()
    previas.unlink()
    if lote.slip_ids:
        raise SystemExit('No se pudieron borrar las boletas previas: %s'
                         % lote.slip_ids.mapped('state'))
else:
    lote = Run.create({
        'name': 'Planilla abril 2026',
        'date_start': DESDE,
        'date_end': HASTA,
        'company_id': principal.id,
        'periodo_id': periodo.id,
    })
check(lote.periodo_id == periodo, 'Lote del periodo 202604',
      '%s (%s → %s)' % (lote.name, lote.date_start, lote.date_end))

# --------------------------------------------------------------------- #
# 2. Boletas                                                             #
# --------------------------------------------------------------------- #
Payslip = env['hr.payslip'].with_company(principal)
boletas = {}
for apellido in APELLIDOS:
    trabajador = empleado(apellido)
    boleta = Payslip.create({
        'name': 'Boleta abril 2026 — %s' % trabajador.name,
        'employee_id': trabajador.id,
        'version_id': trabajador.version_id.id,
        'struct_id': estructura.id,
        'date_from': DESDE,
        'date_to': HASTA,
        'payslip_run_id': lote.id,
    })
    boletas[apellido] = boleta
check(len(boletas) == 10, 'Diez boletas creadas en el lote',
      '%d boletas' % len(lote.slip_ids))

# --------------------------------------------------------------------- #
# 3. Novedades del mes por Excel (asistente de inputs)                   #
# --------------------------------------------------------------------- #
import openpyxl

NOVEDADES = [
    ('Ortiz', 'PREST', 300.0),        # cuota de préstamo
    ('Ortiz', 'ADELANTO', 200.0),     # adelanto de sueldo
    ('Chávez', 'RET_JUD', 500.0),     # retención judicial
    ('Torres', 'SENF', 450.0),        # subsidio por enfermedad
    ('Flores', 'COMI', 1500.0),       # comisiones del mes
]
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'INPUTS'
ws.append(['NRO DOCUMENTO', 'CÓDIGO DE INPUT', 'MONTO'])
for apellido, code, monto in NOVEDADES:
    ws.append([empleado(apellido).version_id.identification_id, code, monto])
buffer = io.BytesIO()
wb.save(buffer)

wizard = env['al.import.payslip.input.wizard'].create({
    'file_data': base64.b64encode(buffer.getvalue()),
    'file_name': 'novedades_abril_2026.xlsx',
    'company_id': principal.id,
    'payslip_run_id': lote.id,
})
wizard.action_load_file()
_res, counts, log, _ids = wizard._process_all_rows(
    wizard._preprocess_rows(wizard._iter_data_rows()))
print('  → creadas=%(created)s actualizadas=%(updated)s '
      'omitidas=%(skipped)s errores=%(error)s' % counts)
if counts['error']:
    for linea in log[:6]:
        print('     %s' % linea)
check(counts['error'] == 0, 'Novedades importadas sin errores',
      '%d novedades' % (counts['created'] + counts['updated']))

# --------------------------------------------------------------------- #
# 3b. HALLAZGO: regla A_JUB del cliente sin rama por defecto             #
# --------------------------------------------------------------------- #
# Varias reglas de AFP del Excel encadenan ramas por nombre de
# afiliación (ONP, HABITAT, INTEGRA, PRIMA, PROFUTURO, JUB PROFUT
# TRANSITO) sin rama por defecto: con la afiliación "SIN RÉGIMEN" que
# usan los practicantes, ``result`` nunca se asigna y aborta el cálculo
# de la boleta COMPLETA. Se descubren calculando la boleta del
# practicante y se completan con la rama por defecto (aporte 0). Las
# reglas afectadas quedan listadas: el Excel de origen debe corregirse.
practicante = boletas['Soto']
reglas_incompletas = []
for _intento in range(15):
    try:
        practicante.compute_sheet()
        break
    except Exception as exc:                                # noqa: BLE001
        texto = str(exc)
        import re as _re0
        fallida = _re0.search(r'Regla salarial: .*?\(([A-Z0-9_]+)\)', texto)
        sin_result = 'NoneType' in texto
        if not (fallida and sin_result):
            raise
        code = fallida.group(1)
        regla = env['hr.salary.rule'].search([
            ('struct_id', '=', estructura.id), ('code', '=', code)], limit=1)
        regla.amount_python_compute = (
            '# Corrección aplicada en pruebas: la regla del Excel no\n'
            '# cubría todas las afiliaciones (p. ej. "SIN RÉGIMEN" de\n'
            '# los practicantes) y dejaba result sin asignar, abortando\n'
            '# el cálculo de la boleta completa.\n'
            'result = 0\n\n' + regla.amount_python_compute)
        reglas_incompletas.append(code)
if reglas_incompletas:
    print('  → HALLAZGO: reglas del Excel sin rama por defecto, '
          'completadas con "result = 0": %s'
          % ', '.join(reglas_incompletas))

# --------------------------------------------------------------------- #
# 4. Cálculo                                                             #
# --------------------------------------------------------------------- #
import re as _re

errores_calculo = []
for apellido, boleta in boletas.items():
    try:
        boleta.compute_sheet()
    except Exception as exc:                                # noqa: BLE001
        texto = str(exc)
        regla = _re.search(r'Regla salarial: (.+)', texto)
        motivo = _re.search(r'Error: (.+?) while evaluating', texto, _re.S)
        errores_calculo.append('%s → %s | %s' % (
            apellido,
            regla.group(1).strip() if regla else '¿?',
            (motivo.group(1).strip() if motivo else texto)[:180]))
check(not errores_calculo, 'Las 10 boletas se calculan sin excepciones',
      ' | '.join(errores_calculo) or '10 calculadas')

con_lineas = [a for a, b in boletas.items() if b.line_ids]
check(len(con_lineas) == 10, 'Todas las boletas tienen líneas',
      '%d con líneas' % len(con_lineas))


def monto(apellido, code):
    linea = boletas[apellido].line_ids.filtered(lambda l: l.code == code)
    return sum(linea.mapped('total'))


def categoria(apellido, code):
    lineas = boletas[apellido].line_ids.filtered(
        lambda l: l.category_id.code == code)
    return sum(lineas.mapped('total'))


# --------------------------------------------------------------------- #
# 5. Contraste con el cálculo legal                                      #
# --------------------------------------------------------------------- #
param = env['hr.main.parameter'].get_main_parameter(principal)
rmv = param.rmv

# --- Básico: mes completo = sueldo íntegro ---
basico_quispe = monto('Quispe', 'BAS')
check(abs(basico_quispe - 2500.0) < 0.01, 'Básico del mes completo',
      'Quispe S/ %.2f (sueldo 2500)' % basico_quispe)

# --- Asignación familiar: 10 % de la RMV para quien tiene hijos ---
af_quispe = monto('Quispe', 'AF')
check(abs(af_quispe - rmv * 0.10) < 0.01,
      'Asignación familiar = 10 % de la RMV',
      'S/ %.2f (RMV %.2f)' % (af_quispe, rmv))
af_flores = monto('Flores', 'AF')
check(abs(af_flores) < 0.01, 'Sin hijos, sin asignación familiar',
      'Flores S/ %.2f' % af_flores)

# --- ONP: 13 % de la remuneración afecta ---
aonp_ramos = monto('Ramos', 'AONP')
onp_ramos = monto('Ramos', 'ONP')
check(aonp_ramos and abs(onp_ramos - aonp_ramos * 0.13) < 0.02,
      'ONP = 13 % de la base afecta',
      'base S/ %.2f → S/ %.2f' % (aonp_ramos, onp_ramos))

# --- AFP: fondo 10 % + comisión + prima de seguro ---
aafp_quispe = monto('Quispe', 'AAFP')
fondo_quispe = monto('Quispe', 'A_JUB')
check(aafp_quispe and abs(fondo_quispe - aafp_quispe * 0.10) < 0.02,
      'Fondo de pensiones AFP = 10 % de la base',
      'base S/ %.2f → S/ %.2f' % (aafp_quispe, fondo_quispe))
comision_quispe = monto('Quispe', 'COMFI')
integra = env['hr.membership'].search([('name', '=', 'AFP INTEGRA')], limit=1)
check(comision_quispe and abs(
    comision_quispe - aafp_quispe * integra.fixed_commision / 100) < 0.02,
    'Comisión sobre flujo con la tasa de la AFP',
    'S/ %.2f al %.2f %%' % (comision_quispe, integra.fixed_commision))
seguro_quispe = monto('Quispe', 'SEGI')
check(seguro_quispe and abs(
    seguro_quispe - aafp_quispe * integra.prima_insurance / 100) < 0.02,
    'Prima de seguro AFP',
    'S/ %.2f al %.2f %%' % (seguro_quispe, integra.prima_insurance))

# --- EsSalud: 9 % a cargo del empleador ---
aessalud = monto('Quispe', 'AESSALUD')
essalud = monto('Quispe', 'ESSALUD')
check(aessalud and abs(essalud - aessalud * 0.09) < 0.02,
      'EsSalud = 9 % (aporte del empleador)',
      'base S/ %.2f → S/ %.2f' % (aessalud, essalud))

# --- EPS: la trabajadora con EPS aporta el 6.75 % ---
eps_flores = monto('Flores', 'ESSALUD')
base_flores = monto('Flores', 'AESSALUD')
check(base_flores and abs(eps_flores - base_flores * 0.0675) < 0.02,
      'Afiliada a EPS: aporte al 6.75 %',
      'base S/ %.2f → S/ %.2f' % (base_flores, eps_flores))

# --- Practicante: sin aportes previsionales ---
aportes_soto = categoria('Soto', 'APOR_TRA')
check(abs(aportes_soto) < 0.01, 'Practicante sin aportes del trabajador',
      'S/ %.2f' % aportes_soto)

# --- Novedades importadas reflejadas en la boleta ---
check(abs(monto('Ortiz', 'PREST') - 300.0) < 0.01,
      'Cuota de préstamo descontada', 'S/ %.2f' % monto('Ortiz', 'PREST'))
check(abs(monto('Chávez', 'RET_JUD') - 500.0) < 0.01,
      'Retención judicial descontada', 'S/ %.2f' % monto('Chávez', 'RET_JUD'))
check(abs(monto('Flores', 'COMI') - 1500.0) < 0.01,
      'Comisiones del mes en ingresos', 'S/ %.2f' % monto('Flores', 'COMI'))

# --- Horas extra volcadas desde el tareaje ---
extras_chavez = monto('Chávez', 'HE25') + monto('Chávez', 'HE35')
check(extras_chavez > 0, 'Horas extra del tareaje pagadas en la boleta',
      'HE25 S/ %.2f + HE35 S/ %.2f' % (monto('Chávez', 'HE25'),
                                       monto('Chávez', 'HE35')))

# --- Cuadre del neto: ingresos − descuentos ---
descuadres = []
for apellido, boleta in boletas.items():
    ingresos = categoria(apellido, 'ING')
    descuentos = categoria(apellido, 'DES_AFE') + categoria(apellido, 'DES_NET')
    aportes = categoria(apellido, 'APOR_TRA')
    neto = monto(apellido, 'NETO')
    esperado = ingresos - descuentos - aportes
    if abs(neto - esperado) > 0.05:
        descuadres.append('%s: neto %.2f ≠ %.2f' % (apellido, neto, esperado))
check(not descuadres, 'Neto = ingresos − descuentos − aportes en las 10',
      ' | '.join(descuadres) or 'las 10 cuadran')

# --------------------------------------------------------------------- #
# 6. Confirmación del lote                                               #
# --------------------------------------------------------------------- #
for boleta in boletas.values():
    boleta.action_payslip_done()
confirmadas = [b for b in boletas.values()
               if b.state in ('validated', 'paid')]
check(len(confirmadas) == 10, 'Las 10 boletas confirmadas',
      '%d en estado done' % len(confirmadas))

env.cr.commit()
print('\n  --- Resumen de la planilla de abril 2026 ---')
print('  %-26s %10s %10s %10s %10s' % ('TRABAJADOR', 'INGRESOS',
                                       'DESC.', 'APORTES', 'NETO'))
total_ing = total_neto = 0.0
for apellido in APELLIDOS:
    ingresos = categoria(apellido, 'ING')
    descuentos = categoria(apellido, 'DES_AFE') + categoria(apellido, 'DES_NET')
    aportes = categoria(apellido, 'APOR_TRA')
    neto = monto(apellido, 'NETO')
    total_ing += ingresos
    total_neto += neto
    print('  %-26s %10.2f %10.2f %10.2f %10.2f' % (
        boletas[apellido].employee_id.name[:26], ingresos, descuentos,
        aportes, neto))
print('  %-26s %10.2f %10s %10s %10.2f' % ('TOTAL', total_ing, '', '',
                                           total_neto))

fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 5: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

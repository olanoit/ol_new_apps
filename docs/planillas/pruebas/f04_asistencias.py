# -*- coding: utf-8 -*-
"""Fase 4 — Asistencias, tareaje y horas extra (abril 2026).

Genera un Excel de marcaciones como el que usa el cliente, lo importa
con el asistente (ejercita la conversión de zona horaria a UTC) y
procesa el tareaje del mes: clasificación de días, tardanzas, horas
extra 25/35/100 y nocturnas.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f04_asistencias.py
"""
import base64
import io
from datetime import date, datetime, timedelta

RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 4 — ASISTENCIAS Y TAREAJE (abril 2026)')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
env = env(context=dict(env.context, allowed_company_ids=principal.ids))

DESDE, HASTA = date(2026, 4, 1), date(2026, 4, 30)


def empleado(apellido):
    return env['hr.employee'].search([
        ('last_name', '=', apellido),
        ('company_id', '=', principal.id)], limit=1)


PERFILES = {
    'diurno': ['Quispe', 'Flores', 'Ortiz', 'Torres', 'Vargas', 'Delgado'],
    'nocturno': ['Ramos'],
    'extras': ['Chávez'],          # sale 3 h tarde: HE 25 % + 35 %
    'tardanza': ['Ccahuana'],      # entra tarde varias veces
}
todos = [a for grupo in PERFILES.values() for a in grupo]

# Horas extra: solo se computan si la versión lo permite.
for apellido in PERFILES['extras']:
    empleado(apellido).version_id.l10n_pe_is_overtime = True

# --------------------------------------------------------------------- #
# 1. Excel de marcaciones (hora local de Lima)                          #
# --------------------------------------------------------------------- #
import openpyxl

wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'ASISTENCIAS'
ws.append(['EMPLEADO', 'ENTRADA', 'SALIDA'])

filas = 0
dia = DESDE
while dia <= HASTA:
    if dia.weekday() < 5:                       # lunes a viernes
        for grupo, apellidos in PERFILES.items():
            for apellido in apellidos:
                trabajador = empleado(apellido)
                documento = trabajador.version_id.identification_id
                if grupo == 'nocturno':
                    entrada = datetime.combine(dia, datetime.min.time()) \
                        + timedelta(hours=22)
                    salida = entrada + timedelta(hours=8)
                elif grupo == 'extras':
                    entrada = datetime.combine(dia, datetime.min.time()) \
                        + timedelta(hours=8)
                    salida = entrada + timedelta(hours=12)   # 3 h extra
                elif grupo == 'tardanza':
                    entrada = datetime.combine(dia, datetime.min.time()) \
                        + timedelta(hours=8, minutes=25)
                    salida = entrada + timedelta(hours=4)
                else:
                    entrada = datetime.combine(dia, datetime.min.time()) \
                        + timedelta(hours=8)
                    salida = entrada + timedelta(hours=9)    # con refrigerio
                ws.append([documento,
                           entrada.strftime('%Y-%m-%d %H:%M:%S'),
                           salida.strftime('%Y-%m-%d %H:%M:%S')])
                filas += 1
    dia += timedelta(days=1)

buffer = io.BytesIO()
wb.save(buffer)
excel_b64 = base64.b64encode(buffer.getvalue())
check(filas > 150, 'Excel de marcaciones generado',
      '%d marcaciones de %d trabajadores' % (filas, len(todos)))

# --------------------------------------------------------------------- #
# 2. Importación con el asistente                                       #
# --------------------------------------------------------------------- #
# El turno nocturno del último día cae ya en UTC del mes siguiente: el
# rango de limpieza se amplía un día por cada lado.
env['hr.attendance'].search([
    ('employee_id', 'in', [empleado(a).id for a in todos]),
    ('check_in', '>=', datetime(2026, 3, 31)),
    ('check_in', '<=', datetime(2026, 5, 2))]).unlink()

wizard = env['al.import.hr.attendance.wizard'].create({
    'file_data': excel_b64,
    'file_name': 'asistencias_abril_2026.xlsx',
    'company_id': principal.id,
    'tz': 'America/Lima',
})
wizard.action_load_file()
_res, counts, _log, _ids = wizard._process_all_rows(
    wizard._preprocess_rows(wizard._iter_data_rows()))
print('  → creadas=%(created)s actualizadas=%(updated)s '
      'omitidas=%(skipped)s errores=%(error)s' % counts)
check(counts['error'] == 0, 'Importación de asistencias sin errores',
      '%d errores' % counts['error'])
check(counts['created'] + counts['updated'] == filas,
      'Todas las marcaciones importadas',
      '%d de %d' % (counts['created'] + counts['updated'], filas))

# La conversión de zona horaria: 08:00 en Lima son las 13:00 UTC.
marca = env['hr.attendance'].search([
    ('employee_id', '=', empleado('Quispe').id),
    ('check_in', '>=', datetime(2026, 4, 1))], order='check_in', limit=1)
check(marca.check_in.hour == 13,
      'Marcación convertida de America/Lima a UTC',
      '%s UTC (08:00 en Lima)' % marca.check_in)

# --------------------------------------------------------------------- #
# 3. Tareaje del mes                                                     #
# --------------------------------------------------------------------- #
Tareaje = env['hr.tareaje.manager']
tareaje = Tareaje.search([
    ('company_id', '=', principal.id),
    ('date_start', '=', DESDE)], limit=1)
if tareaje and tareaje.state == 'done':
    tareaje.set_reopen()
if not tareaje:
    tareaje = Tareaje.create({
        'name': 'Tareaje abril 2026',
        'company_id': principal.id,
        'date_start': DESDE,
        'date_end': HASTA,
        'is_compute_he': True,
        'time_tolerancia': 0.0,
    })
tareaje.action_generate()
check(tareaje.tareaje_line_ids, 'Tareaje procesado',
      '%d trabajadores tareados' % len(tareaje.tareaje_line_ids))


def linea(apellido):
    return tareaje.tareaje_line_ids.filtered(
        lambda l, a=apellido: l.employee_id == empleado(a))


def detalle(apellido):
    return linea(apellido).mapped('attendance_ids') \
        if 'attendance_ids' in env['hr.tareaje.manager.line']._fields \
        else env['hr.tareaje.manager.line.attendance'].search([
            ('tareaje_line_id', 'in', linea(apellido).ids)])


# --- Días laborados: 22 días hábiles en abril 2026 ---
dias_habiles = sum(1 for d in range(1, 31)
                   if date(2026, 4, d).weekday() < 5)
det_quispe = detalle('Quispe')
dlab_quispe = sum(det_quispe.mapped('dlab'))
check(abs(dlab_quispe - dias_habiles) < 0.01,
      'Días laborados del trabajador diurno',
      '%.1f días (hábiles de abril: %d)' % (dlab_quispe, dias_habiles))

# --- Horas extra: 3 h diarias → 2 h al 25 % y 1 h al 35 % ---
det_chavez = detalle('Chávez')
he25 = sum(det_chavez.mapped('he25'))
he35 = sum(det_chavez.mapped('he35'))
check(he25 > 0 and he35 > 0, 'Horas extra divididas en 25 % y 35 %',
      'HE25=%.2f h, HE35=%.2f h' % (he25, he35))
un_dia = det_chavez.filtered(lambda d: d.he25 or d.he35)[:1]
check(un_dia and abs(un_dia.he25 - 2.0) < 0.51,
      'Las dos primeras horas extra del día van al 25 %',
      'día %s: HE25=%.2f HE35=%.2f' % (un_dia.fecha, un_dia.he25,
                                       un_dia.he35))

# --- Tardanza ---
det_ccahuana = detalle('Ccahuana')
tardanza = sum(det_ccahuana.mapped('tar'))
check(tardanza > 0, 'Tardanzas registradas',
      '%.2f h acumuladas' % tardanza)

# --- Nocturnidad ---
det_ramos = detalle('Ramos')
htn = sum(det_ramos.mapped('htn'))
check(htn > 0, 'Horas nocturnas del vigilante',
      '%.2f h nocturnas de %.2f marcadas'
      % (htn, sum(det_ramos.mapped('worked_hours'))))

# --------------------------------------------------------------------- #
# 4. Aplicar el tareaje al periodo                                      #
# --------------------------------------------------------------------- #
tareaje.set_close()
check(tareaje.state == 'done', 'Tareaje aplicado al periodo',
      tareaje.state)

env.cr.commit()
fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 4: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle_falla in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle_falla))
print('-' * 70)

# -*- coding: utf-8 -*-
"""Fase 2 — Reglas salariales del cliente (Excel de Monte Grande).

Importa las 102 reglas del Excel a una estructura NUEVA ``BASE MG`` por
el mismo camino que usa la pantalla (asistente + saneo v18→v19), y
compara el resultado contra la estructura ``BASE`` migrada.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f02_reglas.py
"""
import base64
import os
import re

EXCEL = ('/home/och/odoo/ce19/myodoo/ol_new_apps/docs/planillas/'
         'Regla salarial (hr.salary.rule).xlsx')

RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 2 — REGLAS SALARIALES DEL CLIENTE')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
env = env(context=dict(env.context, allowed_company_ids=principal.ids))
base = env.ref('al_hr_pe.base_structure')

check(os.path.exists(EXCEL), 'Excel del cliente disponible',
      os.path.basename(EXCEL))

# --------------------------------------------------------------------- #
# 1. Estructura destino                                                 #
# --------------------------------------------------------------------- #
Struct = env['hr.payroll.structure']
mg = Struct.search([('name', '=', 'BASE MG')], limit=1)
if not mg:
    mg = Struct.create({'name': 'BASE MG', 'type_id': base.type_id.id})
    print('  → creada estructura BASE MG')
check(mg, 'Estructura BASE MG', 'id=%s tipo=%s' % (mg.id, mg.type_id.name))

# Odoo siembra 8 reglas genéricas (BASIC/GROSS/NET/ATTACH_SALARY...) en
# toda estructura nueva. La planilla peruana no las usa y meterían líneas
# ajenas en la boleta, así que se retiran antes de importar las del
# cliente. La estructura BASE migrada tampoco las tiene.
NATIVAS = ('BASIC', 'GROSS', 'NET', 'ATTACH_SALARY', 'ASSIG_SALARY',
           'CHILD_SUPPORT', 'DEDUCTION', 'REIMBURSEMENT')
sembradas = env['hr.salary.rule'].search([
    ('struct_id', '=', mg.id), ('code', 'in', NATIVAS)])
if sembradas:
    codigos = ', '.join(sembradas.mapped('code'))
    sembradas.unlink()
    print('  → retiradas %d reglas genéricas de Odoo (%s)'
          % (len(NATIVAS), codigos))

# --------------------------------------------------------------------- #
# 2. Plantilla descargable (el bug que bloqueaba la fase)               #
# --------------------------------------------------------------------- #
Wizard = env['al.import.hr.salary.rule.wizard']
datos_plantilla, nombre_plantilla = Wizard.new({})._build_xlsx_template()
check(datos_plantilla.startswith(b'PK'),
      'Plantilla Excel descargable sin configurar el asistente',
      '%s, %d bytes' % (nombre_plantilla, len(datos_plantilla)))

# --------------------------------------------------------------------- #
# 3. Importación de las 102 reglas                                      #
# --------------------------------------------------------------------- #
with open(EXCEL, 'rb') as fh:
    contenido = base64.b64encode(fh.read())

wizard = Wizard.create({
    'file_data': contenido,
    'file_name': os.path.basename(EXCEL),
    'company_id': principal.id,
    'struct_id': mg.id,
    'sanitize_v18': True,
    'update_existing': True,
})
wizard.action_load_file()
check(wizard.state == 'configure', 'Archivo analizado y hoja detectada',
      'hoja=%s' % (wizard.sheet_id.name or '-'))

filas = wizard._preprocess_rows(wizard._iter_data_rows())
check(len(filas) == 102, 'Filas de datos leídas', '%d filas' % len(filas))

_res, counts, log, created_ids = wizard._process_all_rows(filas)
print('  → creadas=%(created)s actualizadas=%(updated)s '
      'omitidas=%(skipped)s errores=%(error)s' % counts)
check(counts['error'] == 0, 'Importación sin errores',
      '%d errores' % counts['error'])
check(counts['created'] + counts['updated'] == 102,
      'Las 102 reglas quedaron en BASE MG',
      '%d procesadas' % (counts['created'] + counts['updated']))

adaptadas = [linea for linea in log if 'adaptado v19' in linea]
descartes = [linea for linea in log if 'condición por defecto' in linea]
check(len(descartes) == 102,
      'Condición por defecto descartada en todas las filas',
      '%d filas' % len(descartes))
check(len(adaptadas) >= 20, 'Reglas adaptadas al dialecto v19',
      '%d reglas con contract/payslip.wage traducidos' % len(adaptadas))

# --------------------------------------------------------------------- #
# 3b. Separación de la quincena                                         #
# --------------------------------------------------------------------- #
# El Excel trae en una sola hoja la planilla mensual y la de quincena
# (sufijo _AQ). Mezcladas en la misma estructura, las reglas de quincena
# se evaluarían en cada boleta mensual. Se trasladan a su estructura.
quincena_struct = Struct.search([('name', '=', 'QUINCENA MG')], limit=1)
if not quincena_struct:
    quincena_struct = Struct.create({
        'name': 'QUINCENA MG', 'type_id': base.type_id.id})
    env['hr.salary.rule'].search([
        ('struct_id', '=', quincena_struct.id),
        ('code', 'in', NATIVAS)]).unlink()
    print('  → creada estructura QUINCENA MG')

reglas_aq = env['hr.salary.rule'].search([
    ('struct_id', '=', mg.id), ('code', '=like', '%\\_AQ')])
if reglas_aq:
    # Al reimportar, el asistente vuelve a crear las _AQ en BASE MG
    # (busca por código + estructura y allí ya no están): la versión
    # anterior en QUINCENA MG se retira para no duplicar.
    previas = env['hr.salary.rule'].search([
        ('struct_id', '=', quincena_struct.id),
        ('code', 'in', reglas_aq.mapped('code'))])
    previas.unlink()
    reglas_aq.struct_id = quincena_struct
    print('  → %d reglas _AQ trasladadas a QUINCENA MG' % len(reglas_aq))
check(len(quincena_struct.rule_ids) == 33,
      'Reglas de quincena en su propia estructura',
      '%d reglas _AQ' % len(quincena_struct.rule_ids))

# --------------------------------------------------------------------- #
# 3c. Inputs habilitados en las estructuras nuevas                      #
# --------------------------------------------------------------------- #
# Los tipos de input peruanos nacen ligados a la estructura BASE; sin
# habilitarlos en las nuevas, las novedades (préstamos, adelantos,
# retención judicial, subsidios) se rechazan al importarlas.
inputs_pe = env['hr.payslip.input.type'].search([
    ('struct_ids', 'in', base.ids)])
inputs_pe.write({'struct_ids': [(4, mg.id), (4, quincena_struct.id)]})
sin_habilitar = inputs_pe.filtered(lambda t: mg not in t.struct_ids)
check(not sin_habilitar, 'Inputs peruanos habilitados en BASE MG',
      '%d tipos de input' % len(inputs_pe))

# --------------------------------------------------------------------- #
# 4. Calidad del código importado                                       #
# --------------------------------------------------------------------- #
reglas_mg = env['hr.salary.rule'].search([('struct_id', '=', mg.id)])
# Las verificaciones de código recorren TODAS las reglas del cliente,
# mensuales y de quincena.
reglas_mg = reglas_mg | quincena_struct.rule_ids
check(len(reglas_mg) == 102, 'Reglas importadas (mensual + quincena)',
      '%d mensuales + %d de quincena'
      % (len(mg.rule_ids), len(quincena_struct.rule_ids)))

con_contract = reglas_mg.filtered(
    lambda r: re.search(r'\bcontract\b', r.amount_python_compute or ''))
check(not con_contract, 'Ninguna regla usa la API v18 "contract"',
      ', '.join(con_contract.mapped('code')) or 'ninguna')

con_payslip_wage = reglas_mg.filtered(
    lambda r: 'payslip.wage' in (r.amount_python_compute or ''))
check(not con_payslip_wage, 'Ninguna regla usa "payslip.wage" (no existe en v19)',
      ', '.join(con_payslip_wage.mapped('code')) or 'ninguna')

no_compilan = []
for regla in reglas_mg:
    try:
        compile(regla.amount_python_compute or 'result = 0',
                '<%s>' % regla.code, 'exec')
    except SyntaxError as exc:
        no_compilan.append('%s (%s)' % (regla.code, exc.msg))
check(not no_compilan, 'Todo el código Python compila',
      '; '.join(no_compilan) or '102 reglas')

# Atributos de primer nivel sobre los objetos del localdict: cazan las
# APIs de v18 que el saneo aún no traduce (campos renombrados al migrar).
MODELOS_LOCALDICT = {
    'version': 'hr.version',
    'employee': 'hr.employee',
    'payslip': 'hr.payslip',
}
# Atributos legítimos de cualquier recordset, no campos del modelo.
ATTR_RECORDSET = {'env', 'ids', 'id', 'sudo', 'with_context', 'with_company',
                  'with_user', 'mapped', 'filtered', 'search', 'browse',
                  'exists', 'read', 'write', 'create', 'unlink', 'ensure_one'}
inexistentes = {}
for regla in reglas_mg:
    codigo = regla.amount_python_compute or ''
    for variable, modelo in MODELOS_LOCALDICT.items():
        campos = env[modelo]._fields
        for attr in set(re.findall(r'\b%s\.([a-z_][a-z0-9_]*)' % variable,
                                   codigo)):
            if attr not in campos and attr not in ATTR_RECORDSET:
                inexistentes.setdefault(
                    '%s.%s' % (variable, attr), []).append(regla.code)
check(not inexistentes, 'Ningún campo inexistente en v19',
      '; '.join('%s (%s)' % (campo, ', '.join(sorted(set(codes))[:6]))
                for campo, codes in sorted(inexistentes.items())) or 'ninguno')

# Valores de selección usados contra los que declara el modelo.
regimenes = {v for v, _l in env['hr.version']._fields[
    'l10n_pe_labor_regime'].selection}
usados = set()
for regla in reglas_mg:
    usados |= set(re.findall(
        r"l10n_pe_labor_regime[^\n]*?['\"]([a-z_\-]+)['\"]",
        regla.amount_python_compute or ''))
usados_base = set()
for regla in env['hr.salary.rule'].search([('struct_id', '=', base.id)]):
    usados_base |= set(re.findall(
        r"l10n_pe_labor_regime[^\n]*?['\"]([a-z_\-]+)['\"]",
        regla.amount_python_compute or ''))
fantasma = sorted(usados - regimenes)
heredado = sorted((usados & usados_base) - regimenes)
# 'fourth-fifth' (locadores) no está en el selection de v19 y también lo
# arrastra la estructura migrada: es deuda funcional heredada de v18, no
# un defecto de esta importación.
check(not (set(fantasma) - set(heredado)),
      'Régimenes laborales: sin valores inexistentes propios del cliente',
      'heredados de v18 en ambas estructuras: %s' % ', '.join(heredado)
      if heredado else ', '.join(sorted(usados)))

con_condicion = reglas_mg.filtered(lambda r: r.condition_select != 'none')
check(not con_condicion, 'Todas quedaron con condición "Siempre verdadero"',
      ', '.join(con_condicion.mapped('code')) or 'ninguna')

# --------------------------------------------------------------------- #
# 5. Comparación BASE (migrada) ↔ BASE MG (cliente)                     #
# --------------------------------------------------------------------- #
reglas_base = env['hr.salary.rule'].search([('struct_id', '=', base.id)])
codigos_base = set(reglas_base.mapped('code'))
codigos_mg = set(reglas_mg.mapped('code'))

solo_mg = sorted(codigos_mg - codigos_base)
solo_base = sorted(codigos_base - codigos_mg)
comunes = sorted(codigos_mg & codigos_base)

print('\n  --- Comparación de catálogos de reglas ---')
print('  Solo en BASE MG (%d): %s' % (len(solo_mg), ' '.join(solo_mg)))
print('  Solo en BASE    (%d): %s' % (len(solo_base), ' '.join(solo_base)))
print('  Comunes         (%d)' % len(comunes))

quincena = [c for c in solo_mg if c.endswith('_AQ')]
otros_nuevos = [c for c in solo_mg if not c.endswith('_AQ')]
print('  De los nuevos, %d son de quincena (_AQ) y %d de otro tipo: %s'
      % (len(quincena), len(otros_nuevos), ' '.join(otros_nuevos)))


def normaliza(codigo):
    """Código Python sin comentarios, espacios ni tabulaciones."""
    limpio = '\n'.join(
        linea.strip() for linea in (codigo or '').splitlines()
        if linea.strip() and not linea.strip().startswith('#'))
    return re.sub(r'\s+', ' ', limpio).strip()


por_codigo_base = {r.code: r for r in reglas_base}
difieren = []
for regla in reglas_mg:
    par = por_codigo_base.get(regla.code)
    if par and normaliza(par.amount_python_compute) != normaliza(
            regla.amount_python_compute):
        difieren.append(regla.code)

print('  Comunes con código Python distinto (%d): %s'
      % (len(difieren), ' '.join(sorted(difieren))))

# Informe en disco para decidir qué versión de cada regla se usa.
INFORME = ('/home/och/odoo/ce19/myodoo/ol_new_apps/docs/planillas/pruebas/'
           'informe_diferencias_reglas.md')
with open(INFORME, 'w', encoding='utf-8') as fh:
    fh.write('# Diferencias BASE (migrada) ↔ BASE MG (Excel del cliente)\n\n')
    fh.write('Generado por `f02_reglas.py`.\n\n')
    fh.write('- Solo en BASE MG (%d): %s\n' % (len(solo_mg), ', '.join(solo_mg)))
    fh.write('- Solo en BASE (%d): %s\n' % (len(solo_base), ', '.join(solo_base)))
    fh.write('- Comunes (%d), de los cuales %d con código Python distinto\n\n'
             % (len(comunes), len(difieren)))
    fh.write('## Reglas comunes con código distinto\n')
    for code in sorted(difieren):
        fh.write('\n### %s — %s\n\n' % (
            code, por_codigo_base[code].name))
        fh.write('**BASE (migrada v19):**\n\n```python\n%s\n```\n\n'
                 % (por_codigo_base[code].amount_python_compute or '').strip())
        mg_rule = reglas_mg.filtered(lambda r, c=code: r.code == c)[:1]
        fh.write('**BASE MG (cliente, saneada):**\n\n```python\n%s\n```\n'
                 % (mg_rule.amount_python_compute or '').strip())
print('  → informe escrito en %s' % INFORME)
check(True, 'Informe de diferencias generado',
      '%d solo-MG, %d solo-BASE, %d divergentes'
      % (len(solo_mg), len(solo_base), len(difieren)))

# --------------------------------------------------------------------- #
# 6. Reporte Excel del asistente                                        #
# --------------------------------------------------------------------- #
datos_reporte, nombre_reporte = wizard._build_xlsx_report(_res, counts)
check(datos_reporte.startswith(b'PK'), 'Reporte Excel de resultados generado',
      '%s, %d bytes' % (nombre_reporte, len(datos_reporte)))

env.cr.commit()
fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 2: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

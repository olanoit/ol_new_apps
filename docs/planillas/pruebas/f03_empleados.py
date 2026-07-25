# -*- coding: utf-8 -*-
"""Fase 3 — 10 empleados con usuarios y datos PLAME completos.

Cada perfil está diseñado para ejercitar una personalización distinta
(asignación familiar, EPS, nocturno, remuneración por horas, préstamos,
subsidios, retención judicial, cese, practicante, extranjero).

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f03_empleados.py
"""
from datetime import date

RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 3 — EMPLEADOS Y USUARIOS')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
secundaria = env['res.company'].search(
    [('name', '=', 'Servicios Andinos Demo S.A.C.')], limit=1)
env = env(context=dict(env.context,
                       allowed_company_ids=(principal | secundaria).ids))

estructura = env['hr.payroll.structure'].search(
    [('name', '=', 'BASE MG')], limit=1)
check(estructura, 'Estructura BASE MG disponible',
      '%d reglas' % len(estructura.rule_ids))

dni = env['l10n_latam.identification.type'].search(
    [('name', '=', 'DNI'), ('country_id.code', '=', 'PE')], limit=1)
carne_ext = env['l10n_latam.identification.type'].search(
    [('name', '=', 'ID Extranjera')], limit=1)
essalud = env['hr.social.insurance'].search([('name', '=', 'EsSalud')], limit=1)
eps = env['hr.social.insurance'].search([('name', '=', 'EPS')], limit=1)


def afp(nombre):
    return env['hr.membership'].search([('name', '=', nombre)], limit=1)


def calendario(nombre):
    return env['resource.calendar'].search(
        [('name', '=', nombre), ('company_id', '=', principal.id)], limit=1)


def worker_type(code):
    tipo = env['hr.worker.type'].search([('code', '=', code)], limit=1)
    return tipo or env['hr.worker.type'].search([], limit=1)


general = calendario('Jornada general 48h')
nocturno = calendario('Jornada nocturna')
parcial = calendario('Jornada parcial 24h')

# --------------------------------------------------------------------- #
# Los 10 perfiles                                                        #
# --------------------------------------------------------------------- #
# worker_type: 21 = empleado, 23 = obrero (tabla T08 de PLAME)
PLANTILLA = [
    {
        'ref': 'E01', 'names': 'Juan Carlos', 'last_name': 'Quispe',
        'm_last_name': 'Mamani', 'doc': '46271883', 'job': 'Operario de planta',
        'wage': 2500.0, 'children': 2, 'afp': 'AFP INTEGRA',
        'commission': 'flow', 'seguro': 'EsSalud', 'calendar': general,
        'regime': 'general', 'worker': '21', 'cuspp': '123456ABCDE1',
        'ejercita': 'asignación familiar (2 hijos), AFP comisión por flujo',
    },
    {
        'ref': 'E02', 'names': 'María Elena', 'last_name': 'Flores',
        'm_last_name': 'Huamán', 'doc': '40123456',
        'job': 'Gerenta comercial', 'wage': 12000.0, 'children': 0,
        'afp': 'AFP PRIMA', 'commission': 'mixed', 'seguro': 'EPS',
        'calendar': general, 'regime': 'general', 'worker': '21',
        'cuspp': '234567BCDEF2',
        'ejercita': 'renta de 5ta con retención, EPS, comisión mixta',
    },
    {
        'ref': 'E03', 'names': 'Carlos Alberto', 'last_name': 'Ramos',
        'm_last_name': 'Vega', 'doc': '41234567', 'job': 'Vigilante nocturno',
        'wage': 1600.0, 'children': 1, 'afp': 'ONP', 'commission': False,
        'seguro': 'EsSalud', 'calendar': nocturno, 'regime': 'general',
        'worker': '23', 'cuspp': False,
        'ejercita': 'jornada nocturna, horas extra, ONP',
    },
    {
        'ref': 'E04', 'names': 'Rosa María', 'last_name': 'Ccahuana',
        'm_last_name': 'Puma', 'doc': '42345678',
        'job': 'Asistente por horas', 'wage': 12.0, 'children': 0,
        'afp': 'AFP PROFUTURO', 'commission': 'flow', 'seguro': 'EsSalud',
        'calendar': parcial, 'regime': 'general', 'worker': '21',
        'cuspp': '345678CDEFG3', 'wage_type': 'hourly',
        'schedule_pay': 'monthly',
        'ejercita': 'remuneración por horas (wage_type = hourly)',
    },
    {
        'ref': 'E05', 'names': 'Luis Fernando', 'last_name': 'Ortiz',
        'm_last_name': 'Salas', 'doc': '43456789', 'job': 'Almacenero',
        'wage': 2200.0, 'children': 3, 'afp': 'AFP HABITAT',
        'commission': 'mixed', 'seguro': 'EsSalud', 'calendar': general,
        'regime': 'general', 'worker': '23', 'cuspp': '456789DEFGH4',
        'ejercita': 'préstamos y adelantos (descuentos al neto)',
    },
    {
        'ref': 'E06', 'names': 'Ana Lucía', 'last_name': 'Torres',
        'm_last_name': 'Quiroz', 'doc': '44567890', 'job': 'Analista contable',
        'wage': 3500.0, 'children': 1, 'afp': 'ONP', 'commission': False,
        'seguro': 'EsSalud', 'calendar': general, 'regime': 'general',
        'worker': '21', 'cuspp': False,
        'ejercita': 'subsidios por enfermedad y maternidad',
    },
    {
        'ref': 'E07', 'names': 'Pedro Pablo', 'last_name': 'Chávez',
        'm_last_name': 'Rojas', 'doc': '45678901', 'job': 'Supervisor de obra',
        'wage': 4200.0, 'children': 2, 'afp': 'AFP INTEGRA',
        'commission': 'flow', 'seguro': 'EsSalud', 'calendar': general,
        'regime': 'general', 'worker': '23', 'cuspp': '567890EFGHI5',
        'ejercita': 'retención judicial y descuento sindical',
    },
    {
        'ref': 'E08', 'names': 'Elena Sofía', 'last_name': 'Vargas',
        'm_last_name': 'Núñez', 'doc': '46789012', 'job': 'Contadora',
        'wage': 5000.0, 'children': 0, 'afp': 'AFP PRIMA',
        'commission': 'flow', 'seguro': 'EsSalud', 'calendar': general,
        'regime': 'general', 'worker': '21', 'cuspp': '678901FGHIJ6',
        'ejercita': 'cese y liquidación de beneficios truncos',
    },
    {
        'ref': 'E09', 'names': 'Miguel Ángel', 'last_name': 'Soto',
        'm_last_name': 'Guerrero', 'doc': '47890123',
        'job': 'Practicante de sistemas', 'wage': 1130.0, 'children': 0,
        'afp': 'SIN RÉGIMEN', 'commission': False, 'seguro': 'EsSalud',
        'calendar': parcial, 'regime': 'practicante', 'worker': '21',
        'cuspp': False,
        'ejercita': 'modalidad formativa (sin aportes ni AFP)',
    },
    {
        'ref': 'E10', 'names': 'Sofía Alejandra', 'last_name': 'Delgado',
        'm_last_name': 'Ríos', 'doc': '001234567', 'job': 'Traductora',
        'wage': 6000.0, 'children': 0, 'afp': 'ONP', 'commission': False,
        'seguro': 'EsSalud', 'calendar': general, 'regime': 'general',
        'worker': '21', 'cuspp': False, 'tipo_doc': 'ext',
        'ejercita': 'trabajador extranjero con carné de extranjería',
    },
]

INICIO_LABORAL = date(2024, 1, 15)
Employee = env['hr.employee'].with_company(principal)
empleados = {}

for perfil in PLANTILLA:
    tipo_doc = carne_ext if perfil.get('tipo_doc') == 'ext' else dni
    empleado = Employee.search([
        ('last_name', '=', perfil['last_name']),
        ('names', '=', perfil['names']),
        ('company_id', '=', principal.id)], limit=1)
    vals_empleado = {
        'names': perfil['names'],
        'last_name': perfil['last_name'],
        'm_last_name': perfil['m_last_name'],
        'company_id': principal.id,
        'job_title': perfil['job'],
        'l10n_latam_identification_type_id': tipo_doc.id,
        'country_id': env.ref('base.pe').id,
        'birthday': date(1990, 6, 15),
    }
    # v19 movió parte de los datos personales: solo se escriben los
    # campos que el modelo declara.
    vals_empleado = {k: v for k, v in vals_empleado.items()
                     if k in Employee._fields}
    if not empleado:
        empleado = Employee.create(dict(vals_empleado, **{
            'date_version': INICIO_LABORAL,
            'contract_date_start': INICIO_LABORAL,
            'wage': perfil['wage'],
            'structure_type_id': estructura.type_id.id,
        }))
        print('  → creado %s %s' % (perfil['ref'], empleado.name))
    else:
        empleado.write(vals_empleado)

    version = empleado.version_id
    vals_version = {
        'identification_id': perfil['doc'],
        'wage': perfil['wage'],
        'wage_type': perfil.get('wage_type', 'monthly'),
        'schedule_pay': perfil.get('schedule_pay', 'monthly'),
        'children': perfil['children'],
        'resource_calendar_id': perfil['calendar'].id,
        'structure_type_id': estructura.type_id.id,
        'contract_date_start': INICIO_LABORAL,
        'l10n_pe_labor_regime': perfil['regime'],
        'l10n_pe_work_type': 'N',
        'l10n_pe_is_older': False,
        'membership_id': afp(perfil['afp']).id,
        'social_insurance_id': (eps if perfil['seguro'] == 'EPS'
                                else essalud).id,
        'worker_type_id': worker_type(perfil['worker']).id,
        'l10n_pe_cuspp': perfil['cuspp'] or False,
    }
    if perfil['commission']:
        vals_version['l10n_pe_commission_type'] = perfil['commission']
    version.write(vals_version)
    empleados[perfil['ref']] = empleado

check(len(empleados) == 10, 'Diez empleados en la compañía principal',
      ', '.join(e.name for e in empleados.values())[:120] + '...')

# --------------------------------------------------------------------- #
# Nombre PLAME: apellidos + nombres                                      #
# --------------------------------------------------------------------- #
e01 = empleados['E01']
check(e01.name == 'Quispe Mamani Juan Carlos',
      'Nombre recompuesto al estilo PLAME', e01.name)

# --------------------------------------------------------------------- #
# Documentos únicos y tipos correctos                                    #
# --------------------------------------------------------------------- #
documentos = [e.version_id.identification_id for e in empleados.values()]
check(len(set(documentos)) == 10, 'Documentos de identidad únicos',
      '%d distintos' % len(set(documentos)))
check(empleados['E10'].l10n_latam_identification_type_id == carne_ext,
      'Extranjero con carné de extranjería',
      empleados['E10'].l10n_latam_identification_type_id.name)

# --------------------------------------------------------------------- #
# Usuarios: uno por empleado + analista y jefe de planillas             #
# --------------------------------------------------------------------- #
Users = env['res.users'].with_company(principal)
grupo_empleado = env.ref('base.group_user')


def alta_usuario(login, nombre, grupos, compania=None):
    compania = compania or principal
    usuario = Users.search([('login', '=', login)], limit=1)
    if usuario:
        return usuario
    return Users.create({
        'name': nombre,
        'login': login,
        'password': login,
        'company_id': compania.id,
        'company_ids': [(6, 0, compania.ids)],
        'group_ids': [(6, 0, [g.id for g in grupos])],
    })


import unicodedata


def sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn')


for perfil in PLANTILLA:
    empleado = empleados[perfil['ref']]
    login = sin_tildes('%s.%s' % (
        perfil['names'].split()[0].lower(), perfil['last_name'].lower()))
    usuario = alta_usuario(login, empleado.name, [grupo_empleado])
    if empleado.user_id != usuario:
        empleado.user_id = usuario
    if usuario.partner_id and not usuario.partner_id.email:
        usuario.partner_id.email = '%s@demo-pe.local' % login

analista = alta_usuario(
    'analista.planillas', 'Analista de planillas',
    [grupo_empleado, env.ref('hr_payroll.group_hr_payroll_user')])
jefe = alta_usuario(
    'jefe.planillas', 'Jefe de planillas',
    [grupo_empleado, env.ref('hr_payroll.group_hr_payroll_manager')])

con_usuario = [e for e in empleados.values() if e.user_id]
check(len(con_usuario) == 10, 'Cada empleado con su usuario',
      '%d usuarios enlazados' % len(con_usuario))
check(analista.has_group('hr_payroll.group_hr_payroll_user')
      and jefe.has_group('hr_payroll.group_hr_payroll_manager'),
      'Usuarios de rol analista y jefe de planillas',
      '%s / %s' % (analista.login, jefe.login))

# --------------------------------------------------------------------- #
# Cuentas bancarias de haberes y de CTS                                  #
# --------------------------------------------------------------------- #
Bank = env['res.partner.bank']
banco = env['res.bank'].search([('name', 'ilike', 'BCP')], limit=1)
if not banco:
    banco = env['res.bank'].create({'name': 'Banco de Crédito del Perú',
                                    'bic': 'BCPLPEPL'})
for indice, perfil in enumerate(PLANTILLA, start=1):
    empleado = empleados[perfil['ref']]
    contacto = empleado.work_contact_id or empleado.user_id.partner_id
    if not contacto:
        continue
    numero = '19100%08d0' % (indice * 137)
    cuenta = Bank.search([('acc_number', '=', numero)], limit=1)
    if not cuenta:
        cuenta = Bank.create({
            'acc_number': numero,
            'partner_id': contacto.id,
            'bank_id': banco.id,
            'company_id': principal.id,
        })
    if 'primary_bank_account_id' in empleado._fields:
        empleado.primary_bank_account_id = cuenta
    if 'cts_bank_account_id' in empleado._fields:
        empleado.cts_bank_account_id = cuenta

con_cuenta = [e for e in empleados.values()
              if e._fields.get('primary_bank_account_id')
              and e.primary_bank_account_id]
check(len(con_cuenta) == 10, 'Cuenta de haberes por empleado',
      '%d cuentas' % len(con_cuenta))

# --------------------------------------------------------------------- #
# Dos empleados en la compañía secundaria (aislamiento multicompañía)   #
# --------------------------------------------------------------------- #
EmployeeSec = env['hr.employee'].with_company(secundaria)
SECUNDARIOS = [
    ('Elsa', 'Paredes', 'Mendoza', '48901234', 2800.0),
    ('Raúl', 'Anco', 'Ticona', '49012345', 3100.0),
]
creados_sec = []
for names, last, m_last, doc, wage in SECUNDARIOS:
    empleado = EmployeeSec.search([
        ('last_name', '=', last), ('company_id', '=', secundaria.id)], limit=1)
    if not empleado:
        empleado = EmployeeSec.create({
            'names': names, 'last_name': last, 'm_last_name': m_last,
            'company_id': secundaria.id,
            'l10n_latam_identification_type_id': dni.id,
            'date_version': INICIO_LABORAL,
            'contract_date_start': INICIO_LABORAL,
            'wage': wage,
            'structure_type_id': estructura.type_id.id,
        })
        empleado.version_id.write({
            'identification_id': doc,
            'l10n_pe_labor_regime': 'general',
            'membership_id': afp('ONP').id,
            'social_insurance_id': essalud.id,
            'worker_type_id': worker_type('21').id,
        })
        print('  → creado %s en %s' % (empleado.name, secundaria.name))
    creados_sec.append(empleado)
check(len(creados_sec) == 2, 'Empleados de la compañía secundaria',
      ', '.join(e.name for e in creados_sec))

# --------------------------------------------------------------------- #
# Coherencia de las versiones                                            #
# --------------------------------------------------------------------- #
sin_afiliacion = [e.name for e in empleados.values()
                  if not e.version_id.membership_id]
check(not sin_afiliacion, 'Todos con afiliación previsional (AFP/ONP)',
      ', '.join(sin_afiliacion) or '10 con AFP u ONP')

por_horas = empleados['E04'].version_id
check(por_horas.wage_type == 'hourly',
      'Empleado con remuneración por horas', '%s S/ %.2f/h' % (
          por_horas.wage_type, por_horas.wage))

practicante = empleados['E09'].version_id
check(practicante.l10n_pe_labor_regime == 'practicante',
      'Practicante en modalidad formativa',
      practicante.l10n_pe_labor_regime)

check(empleados['E03'].version_id.resource_calendar_id == nocturno,
      'Vigilante en jornada nocturna',
      empleados['E03'].version_id.resource_calendar_id.name)

env.cr.commit()
print('\n  --- Resumen de perfiles ---')
for perfil in PLANTILLA:
    empleado = empleados[perfil['ref']]
    print('  %s %-32s S/ %8.2f  %-14s %s' % (
        perfil['ref'], empleado.name, perfil['wage'],
        perfil['afp'], perfil['ejercita']))

fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 3: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

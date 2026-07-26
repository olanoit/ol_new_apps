# -*- coding: utf-8 -*-
"""Fase 7 — Contabilización de la planilla y de los beneficios.

Configura las cuentas de la planilla (el Excel del cliente no las trae),
genera el asiento del lote de abril y los asientos de CTS y
gratificación, y comprueba que cuadren.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f07_contabilidad.py
"""
RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 7 — CONTABILIZACIÓN')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
env = env(context=dict(env.context, allowed_company_ids=principal.ids))
param = env['hr.main.parameter'].get_main_parameter(principal)
mg = env['hr.payroll.structure'].search([('name', '=', 'BASE MG')], limit=1)

Account = env['account.account'].with_company(principal)


def cuenta(prefijo, nombre, tipo='expense'):
    """Cuenta del plan peruano por prefijo; se crea si no existe."""
    existente = Account.search([('code', '=like', prefijo + '%')], limit=1)
    if existente:
        return existente
    return Account.create({
        'code': prefijo,
        'name': nombre,
        'account_type': tipo,
        'company_ids': [(4, principal.id)],
    })


# Plan contable peruano (PCGE) aplicado a la planilla.
GASTO_REMUNERACIONES = cuenta('6211', 'Sueldos y salarios')
GASTO_APORTES = cuenta('6271', 'Régimen de prestaciones de salud')
POR_PAGAR_REMUNERACIONES = cuenta('4111', 'Sueldos y salarios por pagar',
                                  'liability_payable')
POR_PAGAR_AFP = cuenta('4032', 'Sistema privado de pensiones',
                       'liability_current')
POR_PAGAR_ESSALUD = cuenta('4031', 'EsSalud', 'liability_current')
POR_PAGAR_TERCEROS = cuenta('4191', 'Otras cuentas por pagar',
                            'liability_current')
GASTO_CTS = cuenta('6291', 'Compensación por tiempo de servicios')
POR_PAGAR_CTS = cuenta('4151', 'CTS por pagar', 'liability_current')
GASTO_GRATI = cuenta('6214', 'Gratificaciones')
POR_PAGAR_GRATI = cuenta('4114', 'Gratificaciones por pagar',
                         'liability_payable')
GASTO_VACA = cuenta('6215', 'Vacaciones')
POR_PAGAR_VACA = cuenta('4115', 'Vacaciones por pagar', 'liability_payable')
AJUSTE = cuenta('6591', 'Ajuste por redondeo')

check(GASTO_REMUNERACIONES and POR_PAGAR_REMUNERACIONES,
      'Cuentas de planilla disponibles en el plan',
      '%s / %s' % (GASTO_REMUNERACIONES.code,
                   POR_PAGAR_REMUNERACIONES.code))

# --------------------------------------------------------------------- #
# 1. Cuentas por regla, según su categoría                              #
# --------------------------------------------------------------------- #
# El asiento carga por account_debit de cada regla y abona por
# account_credit con detalle por trabajador. El Excel del cliente no
# trae cuentas: se asignan por categoría siguiendo el PCGE.
# Esquema clásico peruano: el ingreso es gasto contra la cuenta por
# pagar al trabajador; retenciones y descuentos CARGAN esa cuenta por
# pagar (reducen el líquido) y ABONAN la cuenta del tercero; el aporte
# del empleador es gasto propio contra EsSalud.
POR_CATEGORIA = {
    # categoría: (cuenta de cargo, cuenta de abono)
    'ING': (GASTO_REMUNERACIONES, POR_PAGAR_REMUNERACIONES),
    'DES_AFE': (POR_PAGAR_REMUNERACIONES, GASTO_REMUNERACIONES),
    'DES_NET': (POR_PAGAR_REMUNERACIONES, POR_PAGAR_TERCEROS),
    'APOR_TRA': (POR_PAGAR_REMUNERACIONES, POR_PAGAR_AFP),
    'APOR_EMP': (GASTO_APORTES, POR_PAGAR_ESSALUD),
}
asignadas = 0
for codigo_categoria, (debe, haber) in POR_CATEGORIA.items():
    categoria = env['hr.salary.rule.category'].search(
        [('code', '=', codigo_categoria)], limit=1)
    reglas = env['hr.salary.rule'].with_company(principal).search([
        ('struct_id', '=', mg.id), ('category_id', '=', categoria.id)])
    for regla in reglas:
        regla.account_debit = debe.id if debe else False
        regla.account_credit = haber.id if haber else False
        # El abono se detalla por trabajador (una línea por empleado).
        if 'employee_move_line' in regla._fields:
            regla.employee_move_line = codigo_categoria in (
                'ING', 'DES_AFE', 'DES_NET')
    asignadas += len(reglas)

# Las reglas de aporte a la AFP van a la cuenta de su membresía.
for membresia in env['hr.membership'].search([('is_afp', '=', True)]):
    membresia.with_company(principal).account_id = POR_PAGAR_AFP.id
onp = env['hr.membership'].search([('name', '=', 'ONP')], limit=1)
onp.with_company(principal).account_id = cuenta(
    '4033', 'ONP', 'liability_current').id

check(asignadas > 40, 'Cuentas asignadas a las reglas por categoría',
      '%d reglas' % asignadas)

# --------------------------------------------------------------------- #
# 2. Diario, partner y cuentas de beneficios                            #
# --------------------------------------------------------------------- #
diario = env['account.journal'].search([
    ('company_id', '=', principal.id), ('type', '=', 'general')], limit=1)
partner_planilla = env['res.partner'].search(
    [('name', '=', 'Planilla de trabajadores')], limit=1)
if not partner_planilla:
    partner_planilla = env['res.partner'].create({
        'name': 'Planilla de trabajadores', 'company_id': principal.id})
param.write({
    'move_journal_id': diario.id,
    'move_partner_id': partner_planilla.id,
    'benefits_adjust_account_id': AJUSTE.id,
    'cts_debe_account_id': GASTO_CTS.id,
    'cts_haber_account_id': POR_PAGAR_CTS.id,
    'cts_payable_account_id': POR_PAGAR_CTS.id,
    'grati_debe_account_id': GASTO_GRATI.id,
    'grati_haber_account_id': POR_PAGAR_GRATI.id,
    'grati_payable_account_id': POR_PAGAR_GRATI.id,
    'vaca_debe_account_id': GASTO_VACA.id,
    'vaca_haber_account_id': POR_PAGAR_VACA.id,
    'boni_debe_account_id': GASTO_GRATI.id,
    'boni_haber_account_id': POR_PAGAR_GRATI.id,
    'liquidation_payable_account_id': POR_PAGAR_REMUNERACIONES.id,
    'liq_concept_in_account_id': GASTO_REMUNERACIONES.id,
    'liq_concept_out_account_id': POR_PAGAR_TERCEROS.id,
})
env.cr.commit()          # la configuración contable se persiste ya
try:
    param.check_batch_move_values()
    check(True, 'Configuración contable del asiento de planilla',
          'diario %s, partner %s' % (diario.code, partner_planilla.name))
except Exception as exc:                                    # noqa: BLE001
    check(False, 'Configuración contable del asiento de planilla',
          str(exc)[:160])

# --------------------------------------------------------------------- #
# 3. Asiento del lote de abril                                          #
# --------------------------------------------------------------------- #
lote = env['hr.payslip.run'].search([
    ('name', '=', 'Planilla abril 2026'),
    ('company_id', '=', principal.id)], limit=1)
if lote.move_id:
    asiento_previo = lote.move_id
    lote.move_id = False
    if asiento_previo.state == 'posted':
        asiento_previo.button_draft()
    asiento_previo.unlink()
lote._pe_generate_batch_move()
asiento = lote.move_id
check(asiento, 'Asiento del lote generado',
      '%s (%s)' % (asiento.name, asiento.state))

debe = sum(asiento.line_ids.mapped('debit'))
haber = sum(asiento.line_ids.mapped('credit'))
check(abs(debe - haber) < 0.01, 'El asiento cuadra',
      'debe S/ %.2f = haber S/ %.2f en %d líneas' % (
          debe, haber, len(asiento.line_ids)))

# El cargo por remuneraciones debe ser el total de ingresos del lote.
ingresos_lote = sum(
    linea.total for boleta in lote.slip_ids
    for linea in boleta.line_ids
    if linea.category_id.code == 'ING')
cargo_remuneraciones = sum(asiento.line_ids.filtered(
    lambda l: l.account_id == GASTO_REMUNERACIONES).mapped('debit'))
check(abs(cargo_remuneraciones - ingresos_lote) < 1.0,
      'El cargo a remuneraciones = ingresos de la planilla',
      'S/ %.2f vs S/ %.2f' % (cargo_remuneraciones, ingresos_lote))

# Detalle por trabajador en el abono de la cuenta por pagar.
lineas_por_pagar = asiento.line_ids.filtered(
    lambda l: l.account_id == POR_PAGAR_REMUNERACIONES and l.credit)
check(len(lineas_por_pagar) >= 10,
      'Abono con detalle por trabajador',
      '%d líneas de detalle' % len(lineas_por_pagar))

# Bloque AFP contra la cuenta de la membresía.
lineas_afp = asiento.line_ids.filtered(
    lambda l: l.account_id == POR_PAGAR_AFP)
env.cr.commit()
check(lineas_afp, 'Bloque de aportes a la AFP',
      'S/ %.2f en %d líneas' % (sum(lineas_afp.mapped('credit')),
                                len(lineas_afp)))

# --------------------------------------------------------------------- #
# 4. Asientos de beneficios sociales                                    #
# --------------------------------------------------------------------- #
cts = env['hr.cts'].search([('company_id', '=', principal.id),
                            ('year', '=', 2026), ('type', '=', '05')],
                           limit=1)
grati = env['hr.gratification'].search([
    ('company_id', '=', principal.id), ('year', '=', 2026),
    ('type', '=', '07')], limit=1)

for registro, etiqueta in ((cts, 'CTS'), (grati, 'Gratificación')):
    if not registro:
        check(False, 'Asiento de %s' % etiqueta, 'sin registro previo')
        continue
    # get_move_wizard precalcula las líneas y las pasa por contexto:
    # se usa su acción tal cual, como haría la pantalla.
    if not registro.account_move_id:
        accion = registro.get_move_wizard()
        Wizard = env['hr.benefits.move.wizard'].with_context(
            **accion['context'])
        valores = Wizard.default_get(['account_id', 'debit', 'credit'])
        valores.update(debit=accion['context']['default_debit'],
                       credit=accion['context']['default_credit'])
        Wizard.create(valores).generate_move()
    asiento_bbss = registro.account_move_id
    if asiento_bbss:
        total_debe = sum(asiento_bbss.line_ids.mapped('debit'))
        total_haber = sum(asiento_bbss.line_ids.mapped('credit'))
        check(abs(total_debe - total_haber) < 0.01,
              'Asiento de %s cuadrado' % etiqueta,
              '%s: S/ %.2f en %d líneas' % (
                  asiento_bbss.name, total_debe,
                  len(asiento_bbss.line_ids)))
    else:
        check(False, 'Asiento de %s' % etiqueta, 'no se generó')

env.cr.commit()
print('\n  --- Asiento de la planilla de abril 2026 ---')
for linea in asiento.line_ids.sorted(lambda l: (l.account_id.code, -l.debit))[:14]:
    print('  %-8s %-38s %10.2f %10.2f' % (
        linea.account_id.code, (linea.name or '')[:38],
        linea.debit, linea.credit))
if len(asiento.line_ids) > 14:
    print('  ... y %d líneas más' % (len(asiento.line_ids) - 14))

fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 7: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

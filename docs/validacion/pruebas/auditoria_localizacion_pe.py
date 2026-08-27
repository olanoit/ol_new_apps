# -*- coding: utf-8 -*-
"""Auditoría funcional de la localización peruana sobre una base real.

Solo LEE: no crea, no escribe y no confirma nada. Recorre módulo por
módulo comprobando que lo instalado está además *configurado y usable*
(catálogos sembrados, series por diario, parámetros de nómina, conexiones
a SUNAT…), que es lo que los tests unitarios no pueden ver porque
trabajan sobre datos de laboratorio.

    cd /home/och/odoo/ce19
    .venv/bin/python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/validacion/pruebas/auditoria_localizacion_pe.py

Cada comprobación imprime OK / AVISO / FALLA:

* **FALLA**: algo que impide operar (falta el dato, el modelo no responde).
* **AVISO**: configuración incompleta o sin uso todavía; no es un defecto
  del módulo, es una tarea de puesta en marcha.
"""
import json
import sys
import traceback

RESULTS = []          # (modulo, nivel, titulo, detalle)
CURRENT = ['general']

OK, WARN, FAIL = 'OK', 'AVISO', 'FALLA'


def module(name):
    CURRENT[0] = name
    print('\n' + '=' * 72)
    print('  %s' % name)
    print('=' * 72)


def record(level, title, detail=''):
    RESULTS.append((CURRENT[0], level, title, detail))
    icon = {OK: '  OK  ', WARN: ' AVISO', FAIL: ' FALLA'}[level]
    print('%s  %s%s' % (icon, title, ' — %s' % detail if detail else ''))


def check(condition, title, detail='', warn_only=False):
    if condition:
        record(OK, title, detail)
    else:
        record(WARN if warn_only else FAIL, title, detail)
    return bool(condition)


def guard(fn):
    """Ejecuta una comprobación aislando el fallo para no cortar la auditoría."""
    try:
        fn()
    except Exception as exc:                      # noqa: BLE001
        record(FAIL, '%s lanzó una excepción' % fn.__name__,
               '%s: %s' % (type(exc).__name__, exc))
        traceback.print_exc(limit=3)


def installed(name):
    mod = env['ir.module.module'].search([('name', '=', name)], limit=1)
    return bool(mod) and mod.state == 'installed'


def has_model(name):
    return name in env


company = env.company
# country_id no es almacenado en res.company (v19): se filtra por el partner.
companies = env['res.company'].search(
    [('partner_id.country_id.code', '=', 'PE')]) or company

print('Base de datos : %s' % env.cr.dbname)
print('Compañía      : %s (%s)' % (company.display_name, company.country_id.code))
print('Compañías PE  : %s' % ', '.join(companies.mapped('display_name')))


# ---------------------------------------------------------------------- #
# Base contable peruana
# ---------------------------------------------------------------------- #
def auditar_account_base():
    module('al_account_base — base contable PE')
    check(installed('al_account_base'), 'Módulo instalado')
    for comp in companies:
        check(comp.country_id.code == 'PE',
              'Compañía %s con país Perú' % comp.name)
        check(comp.currency_id.name == 'PEN',
              'Compañía %s en soles' % comp.name,
              'moneda: %s' % comp.currency_id.name)
        check(bool(comp.vat), 'Compañía %s con RUC' % comp.name,
              comp.vat or 'sin RUC', warn_only=True)
        if comp.vat:
            check(len(comp.vat) == 11 and comp.vat.isdigit(),
                  'RUC de %s con 11 dígitos' % comp.name, comp.vat)
    menu = env.ref('al_account_base.al_l10n_pe_root', raise_if_not_found=False)
    check(bool(menu), 'Menú raíz de la app Perú publicado',
          menu.complete_name if menu else '')
    plan = env['account.account'].search_count([])
    check(plan > 100, 'Plan contable cargado', '%s cuentas' % plan)


# ---------------------------------------------------------------------- #
# Series y numeración SUNAT
# ---------------------------------------------------------------------- #
def auditar_name_sequence():
    module('al_account_move_name_sequence — numeración y series CPE')
    check(installed('al_account_move_name_sequence'), 'Módulo instalado')
    journals = env['account.journal'].search([
        ('company_id', 'in', companies.ids), ('type', 'in', ('sale', 'purchase'))])
    check(bool(journals), 'Diarios de venta/compra existentes',
          '%s diarios' % len(journals))
    opt_in = journals.filtered('use_name_sequence')
    check(bool(opt_in), 'Diarios con numeración por secuencia (opt-in)',
          ', '.join(opt_in.mapped('code')) or 'ninguno todavía', warn_only=True)
    for journal in opt_in:
        if journal.l10n_latam_use_documents:
            # Con documentos latam numeran las Series CPE, no la secuencia simple.
            check(bool(journal.edi_series_ids),
                  'Diario %s con series CPE asignadas' % journal.code,
                  ', '.join(journal.edi_series_ids.mapped('name')) or 'sin series')
        else:
            check(bool(journal.name_sequence_id),
                  'Diario %s con secuencia creada' % journal.code,
                  journal.name_sequence_id.prefix or 'sin prefijo')

    if has_model('edi.invoice.series'):
        series = env['edi.invoice.series'].search(
            [('company_id', 'in', companies.ids)])
        check(bool(series), 'Series CPE registradas',
              ', '.join('%s(%s)' % (s.name, s.state) for s in series) or 'ninguna',
              warn_only=True)
        publicadas = series.filtered(lambda s: s.state == 'publish')
        for serie in publicadas:
            check(bool(serie.invoice_seq_id),
                  'Serie %s con secuencia de facturas' % serie.name,
                  serie.invoice_seq_id.prefix or 'sin secuencia')
            check(serie.invoice_seq_id.implementation == 'no_gap',
                  'Serie %s numera sin huecos' % serie.name,
                  serie.invoice_seq_id.implementation,
                  warn_only=True)


# ---------------------------------------------------------------------- #
# Medios de pago
# ---------------------------------------------------------------------- #
def auditar_payments():
    module('al_account_payments — medios de pago SUNAT')
    if not check(has_model('pe.catalog.payment'), 'Modelo del catálogo disponible'):
        return
    catalog = env['pe.catalog.payment'].search([])
    check(len(catalog) >= 20, 'Catálogo 1 de SUNAT sembrado',
          '%s medios' % len(catalog))
    check(bool(catalog.filtered('is_detraction')),
          'Al menos un medio marcado para detracción',
          ', '.join(catalog.filtered('is_detraction').mapped('code')))
    payments = env['account.payment'].search(
        [('company_id', 'in', companies.ids)], limit=500)
    with_method = payments.filtered('pe_payment_method_id')
    check(bool(payments), 'Hay pagos registrados en la base',
          '%s pagos (muestra)' % len(payments), warn_only=True)
    if payments:
        record(OK if with_method else WARN,
               'Pagos con medio de pago informado',
               '%s de %s' % (len(with_method), len(payments)))


# ---------------------------------------------------------------------- #
# Cuentas destino 6→9
# ---------------------------------------------------------------------- #
def auditar_destinations():
    module('al_account_destinations — asiento de destino 6→9')
    if not check(installed('al_account_destinations'), 'Módulo instalado'):
        return
    for comp in companies:
        dest_type = comp.l10n_pe_dest_type
        check(bool(dest_type), 'Tipo de destino configurado en %s' % comp.name,
              dest_type or 'sin configurar', warn_only=True)
    accounts = env['account.account'].search([('l10n_pe_destiny_ids', '!=', False)])
    check(bool(accounts), 'Cuentas con distribución de destino',
          '%s cuentas' % len(accounts), warn_only=True)
    for account in accounts:
        total = sum(account.l10n_pe_destiny_ids.mapped('percentage'))
        check(abs(total - 1.0) < 0.0001,
              'Distribución de %s suma 100 %%' % account.code,
              '%.4f' % total)


# ---------------------------------------------------------------------- #
# Geografía
# ---------------------------------------------------------------------- #
def auditar_city():
    module('al_l10n_pe_city — ubigeo y ciudades')
    peru = env.ref('base.pe')
    check(peru.enforce_cities, 'País con desplegable de ciudades activo')
    cities = env['res.city'].search([('country_id', '=', peru.id)])
    check(len(cities) >= 421, 'Ciudades del Perú cargadas', '%s ciudades' % len(cities))
    check(not cities.filtered(lambda c: not c.state_id),
          'Todas las ciudades tienen departamento')
    districts = env['l10n_pe.res.city.district'].search_count([]) \
        if has_model('l10n_pe.res.city.district') else 0
    check(districts > 1000, 'Distritos (ubigeo) del core cargados',
          '%s distritos' % districts, warn_only=True)


# ---------------------------------------------------------------------- #
# Tipo de cambio
# ---------------------------------------------------------------------- #
def auditar_currency():
    module('al_l10n_pe_currency — tipo de cambio SUNAT/SBS')
    if not check(installed('al_l10n_pe_currency'), 'Módulo instalado'):
        return
    usd = env.ref('base.USD')
    rates = env['res.currency.rate'].search(
        [('currency_id', '=', usd.id), ('company_id', 'in', companies.ids)],
        order='name desc', limit=10)
    check(bool(rates), 'Tipos de cambio del dólar cargados',
          'último: %s' % (rates[0].name if rates else 'ninguno'), warn_only=True)
    if rates:
        last = rates[0]
        check(bool(last.rate_purchase) and bool(last.rate_sale),
              'Tasas compra/venta informadas en el último día',
              'compra %s / venta %s (origen %s)'
              % (last.rate_purchase, last.rate_sale, last.ref_origin or '—'),
              warn_only=True)
    if has_model('l10n_pe.api.connection'):
        conns = env['l10n_pe.api.connection'].search([])
        check(bool(conns), 'Conexiones de API configuradas',
              ', '.join(conns.mapped('name')) or 'ninguna', warn_only=True)
        for conn in conns:
            check(bool(getattr(conn, 'token', False) or getattr(conn, 'api_key', False)),
                  'Conexión %s con credencial' % conn.name,
                  'sin token' if not getattr(conn, 'token', False) else 'token presente',
                  warn_only=True)


# ---------------------------------------------------------------------- #
# Comprobante electrónico
# ---------------------------------------------------------------------- #
def auditar_invoice():
    module('al_l10n_pe_invoice — comprobante electrónico')
    for xmlid in ('al_l10n_pe_invoice.report_cpe_invoice_a4',
                  'al_l10n_pe_invoice.report_cpe_ticket'):
        check(bool(env.ref(xmlid, raise_if_not_found=False)),
              'Reporte %s registrado' % xmlid.split('.')[-1])
    moves = env['account.move'].search([
        ('company_id', 'in', companies.ids),
        ('move_type', 'in', ('out_invoice', 'out_refund')),
        ('state', '=', 'posted')], limit=200)
    check(bool(moves), 'Facturas de venta publicadas',
          '%s documentos (muestra)' % len(moves), warn_only=True)
    descuadres = []
    for move in moves:
        desglose = (move.l10n_pe_edi_amount_base + move.l10n_pe_edi_amount_igv
                    + move.l10n_pe_edi_amount_exonerated
                    + move.l10n_pe_edi_amount_unaffected
                    + move.l10n_pe_edi_amount_isc
                    + move.l10n_pe_edi_amount_icbper
                    + move.l10n_pe_edi_amount_others)
        if move.currency_id.compare_amounts(desglose, move.amount_total) != 0:
            descuadres.append('%s (%.2f vs %.2f)' % (
                move.name, desglose, move.amount_total))
    check(not descuadres, 'Desglose tributario cuadra con el total',
          '; '.join(descuadres[:5]) or 'todas las facturas de la muestra',
          warn_only=True)
    for comp in companies:
        check(bool(comp.l10n_pe_edi_provider),
              'Proveedor EDI configurado en %s' % comp.name,
              comp.l10n_pe_edi_provider or 'sin proveedor', warn_only=True)


# ---------------------------------------------------------------------- #
# Detracciones
# ---------------------------------------------------------------------- #
def auditar_detraction():
    module('al_l10n_pe_detraction — detracciones SPOT')
    if not check(has_model('l10n_pe.detraction.type'), 'Modelo de tipos disponible'):
        return
    types = env['l10n_pe.detraction.type'].search([])
    check(len(types) >= 20, 'Catálogo 54 de SUNAT sembrado',
          '%s tipos' % len(types))
    sin_pct = types.filtered(lambda t: not t.percentage)
    check(not sin_pct, 'Todos los tipos tienen porcentaje',
          ', '.join(sin_pct.mapped('code'))[:120])
    national_bank = env.ref('l10n_pe.peruvian_national_bank', raise_if_not_found=False)
    for comp in companies:
        account = comp.partner_id.bank_ids.filtered(
            lambda b: b.bank_id == national_bank) if national_bank else False
        check(bool(account), 'Cuenta del Banco de la Nación en %s' % comp.name,
              account[0].acc_number if account else 'sin cuenta BN', warn_only=True)
    moves = env['account.move'].search([
        ('company_id', 'in', companies.ids),
        ('l10n_pe_detraction_applies', '=', True)], limit=100)
    check(True, 'Documentos con detracción aplicada', '%s documentos' % len(moves))
    malos = moves.filtered(lambda m: m.l10n_pe_detraction_amount <= 0)
    check(not malos, 'Detracciones con importe calculado',
          ', '.join(malos.mapped('name'))[:120])


# ---------------------------------------------------------------------- #
# Retenciones
# ---------------------------------------------------------------------- #
def auditar_retention():
    module('al_l10n_pe_retention — retenciones IGV')
    if not check(installed('al_l10n_pe_retention'), 'Módulo instalado'):
        return
    for comp in companies:
        check(True, 'Agente de retención en %s' % comp.name,
              'sí, tasa %s %%' % comp.l10n_pe_retention_rate
              if comp.l10n_pe_retention_agent else 'no marcado')
    taxes = env['account.tax'].search([
        ('company_id', 'in', companies.ids),
        ('is_withholding_tax_on_payment', '=', True)])
    check(bool(taxes), 'Impuesto de retención en el pago configurado',
          ', '.join(taxes.mapped('name'))[:120] or 'ninguno', warn_only=True)
    for tax in taxes:
        check(bool(tax.withholding_sequence_id),
              'Serie de constancia en %s' % tax.name,
              tax.withholding_sequence_id.prefix or 'sin secuencia',
              warn_only=True)
    # Las dos excepciones al régimen viven en l10n_pe_vat_sunat: el
    # padrón oficial es la fuente, no un marcado propio del módulo.
    agentes = env['res.partner'].search_count(
        [('is_retention_agent', '=', True)])
    check(True, 'Contactos marcados como agente de retención',
          '%s contactos' % agentes)
    buenos = env['res.partner'].search_count(
        [('is_good_taxpayer', '=', True)])
    check(True, 'Contactos marcados como buen contribuyente',
          '%s contactos' % buenos)
    if has_model('l10n_pe.retention.received'):
        received = env['l10n_pe.retention.received'].search_count([])
        check(True, 'Constancias de retención recibidas', '%s registros' % received)


# ---------------------------------------------------------------------- #
# Cierre de tipo de cambio
# ---------------------------------------------------------------------- #
def auditar_exchange_closure():
    module('al_l10n_pe_exchange_closure — ajuste por diferencia de cambio')
    if not check(has_model('l10n_pe.exchange.closure'), 'Modelo disponible'):
        return
    closures = env['l10n_pe.exchange.closure'].search(
        [('company_id', 'in', companies.ids)], order='id desc')
    check(True, 'Cierres registrados', '%s cierres' % len(closures))
    for closure in closures[:5]:
        lines = closure.line_ids
        check(bool(lines) or closure.state == 'draft',
              'Cierre %s con líneas' % closure.display_name,
              '%s líneas, estado %s' % (len(lines), closure.state),
              warn_only=True)


# ---------------------------------------------------------------------- #
# Letras de cambio
# ---------------------------------------------------------------------- #
def auditar_letters():
    module('al_l10n_pe_account_letter — letras de cambio')
    if not check(has_model('l10n_pe.letter'), 'Modelo disponible'):
        return
    config = env['l10n_pe.letter.account.config'].search(
        [('company_id', 'in', companies.ids)])
    check(bool(config), 'Configuración contable de letras',
          '%s configuraciones' % len(config), warn_only=True)
    letters = env['l10n_pe.letter'].search([('company_id', 'in', companies.ids)])
    check(True, 'Letras registradas', '%s letras' % len(letters))
    sin_lineas = letters.filtered(lambda l: not l.letter_line_ids)
    check(not sin_lineas, 'Letras con cuotas/líneas',
          ', '.join(sin_lineas.mapped('name'))[:120], warn_only=True)
    descuadres = letters.filtered(
        lambda l: l.rest_amount < 0 or l.partial_amount < 0)
    check(not descuadres, 'Letras sin importes negativos',
          ', '.join(descuadres.mapped('name'))[:120])


# ---------------------------------------------------------------------- #
# PLE
# ---------------------------------------------------------------------- #
def auditar_ple():
    module('al_l10n_pe_ple — libros electrónicos')
    if not check(has_model('l10n_pe.ple.export.wizard'), 'Asistente de exportación disponible'):
        return
    wizard_model = env['l10n_pe.ple.export.wizard']
    # Cada libro es una casilla export_<código> del asistente.
    libros = sorted(name[len('export_'):] for name in wizard_model._fields
                    if name.startswith('export_'))
    check(len(libros) >= 10, 'Libros disponibles en el asistente',
          '%s libros: %s' % (len(libros), ', '.join(libros)))
    for comp in companies:
        check(bool(comp.vat), 'RUC en %s (cabecera de los TXT)' % comp.name,
              comp.vat or 'sin RUC')
    for model_name in ('l10n_pe.ple.cost.center', 'l10n_pe.ple.equity'):
        check(has_model(model_name), 'Modelo %s disponible' % model_name)


# ---------------------------------------------------------------------- #
# SIRE
# ---------------------------------------------------------------------- #
def auditar_sire():
    module('al_l10n_pe_sire — RVIE / RCE por API')
    if not check(has_model('l10n_pe.sire.rvie'), 'Modelos SIRE disponibles'):
        return
    for comp in companies:
        creds = all([
            getattr(comp, 'l10n_pe_sire_client_id', False),
            getattr(comp, 'l10n_pe_sire_client_secret', False),
            getattr(comp, 'l10n_pe_sire_sol_user', False),
        ])
        check(creds, 'Credenciales SIRE en %s' % comp.name,
              'completas' if creds else 'incompletas (SOL/cliente API)',
              warn_only=True)
    rvie = env['l10n_pe.sire.rvie'].search_count([])
    rce = env['l10n_pe.sire.rce'].search_count([])
    check(True, 'Propuestas descargadas', 'RVIE %s / RCE %s' % (rvie, rce))


# ---------------------------------------------------------------------- #
# Padrón SUNAT / consulta RUC
# ---------------------------------------------------------------------- #
def auditar_vat_sunat():
    module('l10n_pe_vat_sunat — consulta RUC/DNI')
    if not check(has_model('l10n_pe.api.connection'), 'Modelo de conexiones disponible'):
        return
    conns = env['l10n_pe.api.connection'].search([])
    check(bool(conns), 'Conexiones sembradas',
          ', '.join(conns.mapped('name')) or 'ninguna')
    activas = conns.filtered(lambda c: getattr(c, 'active', True)
                             and (getattr(c, 'token', False) or getattr(c, 'api_key', False)))
    check(bool(activas), 'Alguna conexión con credencial cargada',
          ', '.join(activas.mapped('name')) or 'ninguna operativa', warn_only=True)
    mappings = env['l10n_pe.api.field.mapping'].search_count([]) \
        if has_model('l10n_pe.api.field.mapping') else 0
    check(mappings > 0, 'Mapeo de campos de la API definido',
          '%s mapeos' % mappings, warn_only=True)
    partners = env['res.partner'].search([
        ('l10n_latam_identification_type_id', '!=', False), ('vat', '!=', False)],
        limit=500)
    ruc_type = env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
    malos = partners.filtered(
        lambda p: ruc_type and p.l10n_latam_identification_type_id == ruc_type
        and (not p.vat.isdigit() or len(p.vat) != 11))
    check(not malos, 'RUC de contactos con formato válido',
          ', '.join('%s:%s' % (p.name, p.vat) for p in malos[:5]) or
          '%s contactos revisados' % len(partners))


# ---------------------------------------------------------------------- #
# Kardex
# ---------------------------------------------------------------------- #
def auditar_kardex():
    module('ol_stock_kardex_pe — inventario permanente 12.1 / 13.1')
    if not check(has_model('l10n_pe.kardex.report'), 'Modelo del kardex disponible'):
        return
    reports = env['l10n_pe.kardex.report'].search(
        [('company_id', 'in', companies.ids)], order='id desc', limit=5)
    check(True, 'Kardex generados', '%s reportes (últimos)' % len(reports))
    valuation = env['product.category'].search([]).mapped('property_valuation')
    check('real_time' in valuation or 'manual_periodic' in valuation,
          'Categorías de producto con valoración definida',
          ', '.join(sorted(set(valuation))), warn_only=True)


# ---------------------------------------------------------------------- #
# TPV
# ---------------------------------------------------------------------- #
def auditar_pos():
    module('al_l10n_pe_edi_pos / al_pos_vendedor — TPV')
    configs = env['pos.config'].search([('company_id', 'in', companies.ids)])
    check(bool(configs), 'Puntos de venta configurados',
          '%s TPV' % len(configs), warn_only=True)
    for config in configs:
        if 'l10n_pe_cpe_enabled' in config._fields:
            check(bool(config.l10n_pe_cpe_enabled),
                  'CPE activo en %s' % config.name,
                  'boleta/factura configuradas' if config.l10n_pe_cpe_enabled
                  else 'faltan diarios de boleta/factura', warn_only=True)
        if 'authorized_seller' in config._fields and config.authorized_seller:
            check(bool(config.seller_ids),
                  'Vendedores autorizados en %s' % config.name,
                  '%s vendedores' % len(config.seller_ids))


# ---------------------------------------------------------------------- #
# Planillas
# ---------------------------------------------------------------------- #
def auditar_planillas():
    module('al_hr_pe* — planillas Perú')
    if not check(has_model('hr.main.parameter'), 'Parámetros principales disponibles'):
        return
    for comp in companies:
        param = env['hr.main.parameter'].search(
            [('company_id', '=', comp.id)], limit=1)
        if not check(bool(param), 'Parámetros de nómina en %s' % comp.name):
            continue
        check(bool(param.move_journal_id),
              'Diario de planilla en %s' % comp.name,
              param.move_journal_id.display_name or 'sin diario', warn_only=True)
        check(bool(param.move_partner_id),
              'Partner por defecto del asiento en %s' % comp.name,
              param.move_partner_id.display_name or 'sin partner', warn_only=True)
    structs = env['hr.payroll.structure'].search(
        [('country_id', '=', env.ref('base.pe').id)])
    check(bool(structs), 'Estructuras salariales peruanas',
          ', '.join(structs.mapped('name'))[:150], warn_only=True)
    for struct in structs:
        check(bool(struct.rule_ids), 'Estructura %s con reglas' % struct.name,
              '%s reglas' % len(struct.rule_ids))
    employees = env['hr.employee'].search([('company_id', 'in', companies.ids)])
    check(True, 'Empleados registrados', '%s empleados' % len(employees))
    sin_doc = employees.filtered(lambda e: not e.identification_id)
    check(not sin_doc, 'Empleados con documento de identidad',
          ', '.join(sin_doc.mapped('name'))[:150], warn_only=True)
    if has_model('pe.public.holiday'):
        holidays = env['pe.public.holiday'].search([])
        aplicados = env['resource.calendar.leaves'].search_count(
            [('pe_public_holiday_id', '!=', False)])
        check(bool(holidays), 'Feriados nacionales cargados',
              '%s feriados' % len(holidays))
        check(aplicados > 0, 'Feriados aplicados a calendarios',
              '%s descansos' % aplicados, warn_only=True)
    slips = env['hr.payslip'].search([('company_id', 'in', companies.ids)])
    check(True, 'Boletas registradas', '%s boletas' % len(slips))


# ---------------------------------------------------------------------- #
# Integridad transversal
# ---------------------------------------------------------------------- #
def auditar_integridad():
    module('Integridad transversal')
    broken = env['ir.model.data'].search([('module', 'like', 'al_%')])
    check(bool(broken), 'Datos XML de los módulos al_* presentes',
          '%s registros' % len(broken))
    views = env['ir.ui.view'].search([('active', '=', True)])
    check(bool(views), 'Vistas activas', '%s vistas' % len(views))
    crons = env['ir.cron'].search([('active', '=', True)])
    pe_crons = crons.filtered(
        lambda c: (c.ir_actions_server_id.code or '').lower().find('pe') >= 0
        or 'pe' in (c.name or '').lower())
    check(True, 'Tareas programadas activas',
          '%s en total, %s relacionadas con PE' % (len(crons), len(pe_crons)))
    failed = env['ir.module.module'].search([('state', '=', 'to upgrade')])
    check(not failed, 'Sin módulos pendientes de actualizar',
          ', '.join(failed.mapped('name'))[:150])


for fn in (auditar_account_base, auditar_name_sequence, auditar_payments,
           auditar_destinations, auditar_city, auditar_currency,
           auditar_invoice, auditar_detraction, auditar_retention,
           auditar_exchange_closure, auditar_letters, auditar_ple,
           auditar_sire, auditar_vat_sunat, auditar_kardex, auditar_pos,
           auditar_planillas, auditar_integridad):
    guard(fn)


# ---------------------------------------------------------------------- #
# Resumen
# ---------------------------------------------------------------------- #
print('\n' + '=' * 72)
print('  RESUMEN')
print('=' * 72)
totals = {OK: 0, WARN: 0, FAIL: 0}
for _mod, level, _title, _detail in RESULTS:
    totals[level] += 1
print('OK: %s   AVISO: %s   FALLA: %s   (total %s)'
      % (totals[OK], totals[WARN], totals[FAIL], len(RESULTS)))

if totals[FAIL]:
    print('\nFallas:')
    for mod, level, title, detail in RESULTS:
        if level == FAIL:
            print('  - [%s] %s — %s' % (mod, title, detail))
if totals[WARN]:
    print('\nAvisos (configuración pendiente, no defectos):')
    for mod, level, title, detail in RESULTS:
        if level == WARN:
            print('  - [%s] %s — %s' % (mod, title, detail))

with open('/tmp/auditoria_localizacion_pe.json', 'w') as fh:
    json.dump([{'modulo': m, 'nivel': l, 'titulo': t, 'detalle': d}
               for m, l, t, d in RESULTS], fh, ensure_ascii=False, indent=1)
print('\nDetalle en /tmp/auditoria_localizacion_pe.json')

# La auditoría no escribe nada: se deshace cualquier lectura sucia.
env.cr.rollback()

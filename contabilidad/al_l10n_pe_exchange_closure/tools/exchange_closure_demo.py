# -*- coding: utf-8 -*-
"""Datos de comprobación del cierre de tipo de cambio.

Ejecutar con:
    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < al_l10n_pe_exchange_closure/tools/exchange_closure_demo.py

Monta un escenario real en dólares (factura de venta, factura de compra,
banco en M.E. y un cobro parcial conciliado), corre los cierres de junio y
julio 2026 y verifica que, tras cada cierre, el saldo contable de cada
cuenta sea exactamente ``saldo_en_dólares × T.C. de cierre``.

Es idempotente: si ya existen los registros «DEMO TC» los reutiliza.
"""
from datetime import date

company = env['res.company'].browse(1)
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
usd = env.ref('base.USD')
pen = company.currency_id
results = []


def log(name, ok, detail=''):
    results.append((name, ok))
    print('  [%s] %s %s' % ('OK' if ok else 'XX', name, detail))


def get_or_create(model, domain, vals):
    rec = env[model].with_company(company).search(domain, limit=1)
    return rec or env[model].with_company(company).create(vals)


def acc(code):
    return env['account.account'].with_company(company).search(
        [('code', '=', code)], limit=1)


# ------------------------------------------------------------------ #
print('=== 1. Configuración ===')
# ------------------------------------------------------------------ #
journal = get_or_create('account.journal', [('code', '=', 'CTC')], {
    'name': 'Cierre de tipo de cambio', 'code': 'CTC', 'type': 'general',
    'company_id': company.id})
company.l10n_pe_exchange_closing_journal_id = journal
log('Diario CTC configurado', bool(company.l10n_pe_exchange_closing_journal_id),
    journal.name)
log('Cuentas 676/776 de la compañía',
    bool(company.income_currency_exchange_account_id
         and company.expense_currency_exchange_account_id),
    '%s / %s' % (company.expense_currency_exchange_account_id.code,
                 company.income_currency_exchange_account_id.code))

acc_bank = acc('1041002')      # Cuentas corrientes operativas (M.E.)
acc_receivable = acc('1212000')  # Facturas por cobrar - terceros
acc_payable = acc('4212000')   # Facturas por pagar - terceros
acc_bank.write({'currency_id': usd.id, 'l10n_pe_exchange_closing': 'summary'})
acc_receivable.l10n_pe_exchange_closing = 'detail'
acc_payable.l10n_pe_exchange_closing = 'detail'
log('Cuentas marcadas para el cierre', True,
    '%s(sin detalle) %s(detalle) %s(detalle)' % (
        acc_bank.code, acc_receivable.code, acc_payable.code))
log('T.C. por naturaleza',
    acc_bank._l10n_pe_closing_rate_type() == 'purchase'
    and acc_payable._l10n_pe_closing_rate_type() == 'sale',
    'activo→compra, pasivo→venta')

# T.C. de fin de mes (SUNAT no publica sábados/domingos; se registran aquí
# para que la comprobación sea reproducible sin salir a internet).
for rate_date, purchase, sale in ((date(2026, 6, 30), 3.410, 3.418),
                                  (date(2026, 7, 31), 3.395, 3.404)):
    usd._l10n_pe_upsert_rate(rate_date, purchase, sale, 'manual')
log('T.C. de cierre registrados', True, '30/06 3.410-3.418 · 31/07 3.395-3.404')

partner_cli = get_or_create('res.partner', [('name', '=', 'DEMO TC Cliente')],
                            {'name': 'DEMO TC Cliente'})
partner_prov = get_or_create('res.partner', [('name', '=', 'DEMO TC Proveedor')],
                             {'name': 'DEMO TC Proveedor'})
partner_cc = get_or_create('res.partner', [('name', '=', 'DEMO TC Analítica')],
                           {'name': 'DEMO TC Analítica'})
acc_other = env['account.account'].with_company(company).search(
    [('account_type', '=', 'income')], limit=1)
acc_exp = env['account.account'].with_company(company).search(
    [('account_type', '=', 'expense')], limit=1)

# Centros de costo para comprobar la herencia de analítica.
plan = get_or_create('account.analytic.plan', [('name', '=', 'DEMO TC Centros')],
                     {'name': 'DEMO TC Centros'})
cc_north = get_or_create('account.analytic.account',
                         [('name', '=', 'DEMO TC Norte')],
                         {'name': 'DEMO TC Norte', 'plan_id': plan.id,
                          'company_id': company.id})
cc_south = get_or_create('account.analytic.account',
                         [('name', '=', 'DEMO TC Sur')],
                         {'name': 'DEMO TC Sur', 'plan_id': plan.id,
                          'company_id': company.id})
dist_north = {str(cc_north.id): 100.0}
dist_south = {str(cc_south.id): 100.0}
log('Centros de costo creados', True, '%s / %s' % (cc_north.name, cc_south.name))

# ------------------------------------------------------------------ #
print('\n=== 2. Movimientos en dólares de junio ===')
# ------------------------------------------------------------------ #


def entry(ref, move_date, lines):
    """Asiento en dólares. Cada línea es (cuenta, US$, T.C., socio[, analítica])."""
    move = env['account.move'].with_company(company).search(
        [('ref', '=', ref), ('company_id', '=', company.id)], limit=1)
    if move:
        return move
    move = env['account.move'].with_company(company).create({
        'move_type': 'entry', 'journal_id': journal.id, 'date': move_date,
        'ref': ref,
        'line_ids': [(0, 0, {
            'account_id': line[0].id,
            'partner_id': line[3].id if line[3] else False,
            'currency_id': usd.id,
            'amount_currency': line[1],
            'balance': round(line[1] * line[2], 2),
            'analytic_distribution': line[4] if len(line) > 4 else False,
            'name': ref,
        }) for line in lines],
    })
    move.action_post()
    return move


# Venta a crédito US$ 10,000 al T.C. 3.389 del 14/06.
mv_sale = entry('DEMO TC venta', date(2026, 6, 15), [
    (acc_receivable, 10000.0, 3.389, partner_cli),
    (acc_other, -10000.0, 3.389, False),
])
# Compra a crédito US$ 6,000 al T.C. 3.384 del 18/06.
mv_bill = entry('DEMO TC compra', date(2026, 6, 18), [
    (acc_exp, 6000.0, 3.384, False),
    (acc_payable, -6000.0, 3.384, partner_prov),
])
# Depósito en la cuenta corriente en dólares al T.C. 3.386 del 22/06.
mv_bank = entry('DEMO TC banco', date(2026, 6, 22), [
    (acc_bank, 5000.0, 3.386, False),
    (acc_other, -5000.0, 3.386, False),
])
# Dos ventas al mismo cliente con centros de costo distintos: la analítica
# va en la línea de ingreso, no en la cuenta por cobrar (caso real de una
# factura). 60 % Norte / 40 % Sur por importe.
mv_cc1 = entry('DEMO TC venta CC Norte', date(2026, 6, 16), [
    (acc_receivable, 6000.0, 3.389, partner_cc),
    (acc_other, -6000.0, 3.389, False, dist_north),
])
mv_cc2 = entry('DEMO TC venta CC Sur', date(2026, 6, 17), [
    (acc_receivable, 4000.0, 3.389, partner_cc),
    (acc_other, -4000.0, 3.389, False, dist_south),
])
log('Asientos de junio publicados',
    all(m.state == 'posted'
        for m in (mv_sale, mv_bill, mv_bank, mv_cc1, mv_cc2)),
    ', '.join(m.name for m in (mv_sale, mv_bill, mv_bank, mv_cc1, mv_cc2)))

# ------------------------------------------------------------------ #
print('\n=== 3. Cierre de junio 2026 ===')
# ------------------------------------------------------------------ #
Closure = env['l10n_pe.exchange.closure'].with_company(company)


def reset_closures():
    """Deja los cierres en borrador para que el script sea re-ejecutable.

    Se recorren del más reciente al más antiguo porque un cierre anterior no
    se puede recalcular mientras haya uno posterior contabilizado.
    """
    closures = Closure.search([
        ('company_id', '=', company.id), ('currency_id', '=', usd.id),
        ('state', '!=', 'cancel')], order='date desc')
    for closure in closures:
        if closure.state == 'posted':
            closure.action_cancel()
        closure.action_draft()
    return closures


reset = reset_closures()
if reset:
    print('  (se reabrieron %d cierres previos para recalcularlos)' % len(reset))


def run_closure(month, year):
    closure = Closure.search([
        ('company_id', '=', company.id), ('currency_id', '=', usd.id),
        ('month', '=', month), ('year', '=', year), ('state', '!=', 'cancel'),
    ], limit=1)
    if not closure:
        closure = Closure.create({
            'company_id': company.id, 'currency_id': usd.id,
            'month': month, 'year': year, 'journal_id': journal.id})
    if closure.state == 'draft':
        closure.action_fetch_rate()
        closure.action_compute()
    if closure.state == 'computed':
        closure.action_post()
    return closure


def show(closure):
    print('  %s · T.C. compra %.3f venta %.3f · asiento %s' % (
        closure.name, closure.rate_purchase, closure.rate_sale,
        closure.move_id.name or '-'))
    print('  %-12s %-22s %12s %6s %12s %12s %10s  %s' % (
        'CUENTA', 'SOCIO', 'SALDO US$', 'T.C.', 'SALDO S/', 'REVALUADO',
        'AJUSTE', 'ANALÍTICA'))
    for line in closure.line_ids:
        analytic = ' '.join(
            '%s %.0f%%' % (env['account.analytic.account'].browse(
                int(key.split(',')[0])).name, value)
            for key, value in (line.analytic_distribution or {}).items())
        print('  %-12s %-22s %12.2f %6.3f %12.2f %12.2f %10.2f  %s' % (
            line.account_id.code, (line.partner_id.name or '')[:22],
            line.amount_currency, line.rate, line.balance,
            line.balance_adjusted, line.adjustment, analytic))
    print('  Ganancia %.2f · Pérdida %.2f · Neto %.2f' % (
        closure.amount_gain, closure.amount_loss, closure.amount_net))


def check_revalued(closure):
    """Tras contabilizar, saldo contable == saldo M.E. × T.C. de cierre."""
    ok = True
    for line in closure.line_ids:
        domain = closure._get_aml_domain(
            line.account_id.l10n_pe_exchange_closing)
        # Ahora sí se incluye el asiento del cierre recién contabilizado.
        domain = [d for d in domain if not (
            isinstance(d, (list, tuple)) and d[0] == 'move_id')]
        domain += [('account_id', '=', line.account_id.id)]
        if line.account_id.l10n_pe_exchange_closing == 'detail':
            domain += [('partner_id', '=', line.partner_id.id or False)]
        amls = env['account.move.line'].with_company(company).search(domain)
        balance = sum(amls.mapped('balance'))
        amount_currency = sum(amls.mapped('amount_currency'))
        expected = round(amount_currency * line.rate, 2)
        if abs(balance - expected) > 0.01:
            ok = False
            print('     %s %s: saldo %.2f ≠ esperado %.2f' % (
                line.account_id.code, line.partner_id.name or '',
                balance, expected))
    return ok


june = run_closure('06', 2026)
show(june)
log('Cierre de junio contabilizado', june.state == 'posted', june.move_id.name)
log('Asiento cuadrado',
    pen.is_zero(sum(june.move_id.line_ids.mapped('balance'))))
log('El ajuste no mueve moneda extranjera',
    all(l.amount_currency == 0 for l in june.move_id.line_ids
        if l.currency_id == usd))
log('Saldos revaluados al T.C. de cierre', check_revalued(june))

# Comprobación aritmética explícita del renglón del banco.
bank_line = june.line_ids.filtered(lambda l: l.account_id == acc_bank)
log('Banco: 5.000 × 3.410 − 16.930 = 120,00',
    abs(bank_line.adjustment - 120.0) < 0.01,
    '%.2f' % bank_line.adjustment)
recv_line = june.line_ids.filtered(
    lambda l: l.account_id == acc_receivable and l.partner_id == partner_cli)
log('Por cobrar: 10.000 × 3.410 − 33.890 = 210,00',
    abs(recv_line.adjustment - 210.0) < 0.01, '%.2f' % recv_line.adjustment)
pay_line = june.line_ids.filtered(
    lambda l: l.account_id == acc_payable and l.partner_id == partner_prov)
log('Por pagar: −6.000 × 3.418 + 20.304 = −204,00',
    abs(pay_line.adjustment + 204.0) < 0.01, '%.2f' % pay_line.adjustment)

print('\n=== 3.b Distribución analítica ===')
cc_line = june.line_ids.filtered(
    lambda l: l.account_id == acc_receivable and l.partner_id == partner_cc)
log('Analítica heredada de las líneas de ingreso del documento',
    cc_line.analytic_distribution == {str(cc_north.id): 60.0,
                                      str(cc_south.id): 40.0},
    str(cc_line.analytic_distribution))

move_lines = june.move_id.line_ids
balance_lines = move_lines.filtered(
    lambda l: l.account_id in (acc_bank + acc_receivable + acc_payable))
result_lines = move_lines.filtered(
    lambda l: l.account_id in (company.income_currency_exchange_account_id
                               + company.expense_currency_exchange_account_id))
log('Las líneas de balance no llevan analítica',
    not any(balance_lines.mapped('analytic_distribution')),
    'si la llevaran, sus apuntes analíticos anularían los del resultado')
log('Las líneas de resultado sí la llevan',
    any(result_lines.mapped('analytic_distribution')))
log('Se abre una línea de resultado por distribución analítica',
    len(result_lines) > 2, '%d líneas 676/776' % len(result_lines))

analytic_lines = env['account.analytic.line'].search(
    [('move_line_id', 'in', move_lines.ids)])
column = plan._column_name()
by_cc = {}
for aline in analytic_lines:
    key = aline[column].name or '(sin centro)'
    by_cc[key] = by_cc.get(key, 0.0) + aline.amount
print('  Apuntes analíticos generados: %s' % (
    ', '.join('%s %.2f' % (name, amount) for name, amount in by_cc.items())))
# El ajuste del cliente analítico es 10.000 × 3.410 − 33.890 = 210,00,
# repartido 60/40 entre Norte y Sur.
log('Analítica Norte 126,00 (60 % de 210)',
    abs(by_cc.get(cc_north.name, 0.0) - 126.0) < 0.01)
log('Analítica Sur 84,00 (40 % de 210)',
    abs(by_cc.get(cc_south.name, 0.0) - 84.0) < 0.01)
log('El total analítico iguala al ajuste del cliente (210,00)',
    abs(sum(by_cc.values()) - 210.0) < 0.01,
    '%.2f' % sum(by_cc.values()))

# ------------------------------------------------------------------ #
print('\n=== 4. Movimiento de julio y cierre de julio 2026 ===')
# ------------------------------------------------------------------ #
# Cobro parcial de US$ 4,000 al T.C. 3.397 del 15/07.
mv_collect = entry('DEMO TC cobro', date(2026, 7, 15), [
    (acc_bank, 4000.0, 3.397, False),
    (acc_receivable, -4000.0, 3.397, partner_cli),
])
log('Cobro parcial publicado', mv_collect.state == 'posted', mv_collect.name)

july = run_closure('07', 2026)
show(july)
log('Cierre de julio contabilizado', july.state == 'posted', july.move_id.name)
log('Asiento cuadrado',
    pen.is_zero(sum(july.move_id.line_ids.mapped('balance'))))
log('Saldos revaluados al T.C. de cierre', check_revalued(july))

# El punto crítico: julio no vuelve a ajustar lo ya ajustado en junio.
july_recv = july.line_ids.filtered(
    lambda l: l.account_id == acc_receivable and l.partner_id == partner_cli)
# Saldo M.E. 6.000; saldo contable = 33.890 + 210 (junio) − 13.588 (cobro)
# = 20.512; revaluado 6.000 × 3.395 = 20.370 → ajuste −142,00.
log('Por cobrar julio: ajusta solo el delta (−142,00)',
    abs(july_recv.adjustment + 142.0) < 0.01, '%.2f' % july_recv.adjustment)
log('El saldo de partida ya incluía el ajuste de junio',
    abs(july_recv.balance - 20512.0) < 0.01, '%.2f' % july_recv.balance)

# El asiento de cierre de junio agrupa a los tres socios: si julio heredara
# analítica de sus líneas hermanas, todos los renglones acabarían con el
# 60/40 del cliente analítico.
july_cc = july.line_ids.filtered(
    lambda l: l.account_id == acc_receivable and l.partner_id == partner_cc)
log('Julio: el cliente analítico conserva su 60/40',
    july_cc.analytic_distribution == {str(cc_north.id): 60.0,
                                      str(cc_south.id): 40.0},
    str(july_cc.analytic_distribution))
log('Julio: los demás renglones no heredan analítica del cierre de junio',
    not july_recv.analytic_distribution
    and not july.line_ids.filtered(
        lambda l: l.account_id == acc_bank).analytic_distribution,
    'banco y cliente sin centro de costo quedan sin analítica')

# ------------------------------------------------------------------ #
print('\n=== 5. Validaciones ===')
# ------------------------------------------------------------------ #
# Las pruebas de rechazo van dentro de un savepoint: capturar la excepción
# no deshace el INSERT, y el commit final dejaría registros a medio crear.
try:
    with env.cr.savepoint():
        Closure.create({'company_id': company.id, 'currency_id': usd.id,
                        'month': '06', 'year': 2026, 'journal_id': journal.id})
    log('Rechaza un segundo cierre de junio', False)
except Exception as exc:  # noqa: BLE001 — se comprueba el rechazo
    log('Rechaza un segundo cierre de junio', True, type(exc).__name__)

june_again = Closure.search([('month', '=', '06'), ('year', '=', 2026),
                             ('company_id', '=', company.id),
                             ('state', '=', 'posted')], limit=1)
try:
    with env.cr.savepoint():
        june_again.unlink()
    log('Protege el cierre contabilizado del borrado', False)
except Exception as exc:  # noqa: BLE001
    log('Protege el cierre contabilizado del borrado', True,
        type(exc).__name__)

env.cr.commit()
print('\n=== RESUMEN: %d/%d comprobaciones OK ===' % (
    sum(1 for _n, ok in results if ok), len(results)))
for name, ok in results:
    if not ok:
        print('  FALLA: %s' % name)

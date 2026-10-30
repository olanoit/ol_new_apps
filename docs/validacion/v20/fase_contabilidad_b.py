# -*- coding: utf-8 -*-
# Fase contabilidad_b (OL-ACCOUNTING): cobros, pagos, bancos, financiamiento y cierre.
# Partes: P4 financiamiento/cierre (su preparación va primero), P1 pagos/tesorería, P2 cobranza/cheques/letras, P3 caja/pasarelas/flujo.

# ======================================================================= PARTE 4
# -*- coding: utf-8 -*-
# Fase contabilidad_b — parte 4: financiamiento y cierre.
# Préstamos bancarios, cartas fianza, depósitos a plazo, arrendamientos NIIF 16,
# DUA de importación, cierre de tipo de cambio y revaluación multimoneda.
import time as _p4_time
from datetime import date as _p4_date
from unittest.mock import patch as _p4_patch

import sys as _p4_sys
_p4_sys.stdout.reconfigure(line_buffering=True)
_p4_TS = _p4_time.strftime('%H%M%S')
_p4_PEN = company.currency_id


def _p4_round(v):
    return _p4_PEN.round(v)


def _p4_partner(name, **vals):
    Partner = env['res.partner']
    p = Partner.search([('name', '=', qa_name(name))], limit=1)
    return p or Partner.create(dict({'name': qa_name(name), 'is_company': True}, **vals))


def _p4_journal(name, code, jtype, **vals):
    Journal = env['account.journal']
    j = Journal.search([('name', '=', qa_name(name)), ('company_id', '=', company.id)], limit=1)
    return j or Journal.create(dict({'name': qa_name(name), 'code': code, 'type': jtype,
                                     'company_id': company.id}, **vals))


def _p4_balance(moves, account):
    lines = moves.filtered(lambda m: m.state == 'posted').line_ids.filtered(lambda l: l.account_id == account)
    return _p4_round(sum(lines.mapped('balance')))


def _p4_balanced(moves):
    return all(_p4_PEN.is_zero(sum(m.line_ids.mapped('balance'))) for m in moves)


def _p4_run(fn):
    t = _p4_time.time()
    ejecutar(fn)
    print('    (%s: %.0f s)' % (fn.__name__, _p4_time.time() - t))


def _p4_today(day):
    return _p4_patch('odoo.fields.Date.context_today', return_value=day)


def _p4_rate(currency, day, comp, **vals):
    Rate = env['res.currency.rate']
    r = Rate.search([('currency_id', '=', currency.id), ('company_id', '=', comp.id), ('name', '=', day)], limit=1)
    if r:
        r.write(vals)
        return r
    return Rate.create(dict({'currency_id': currency.id, 'company_id': comp.id, 'name': day}, **vals))


# --- Preparación temprana -------------------------------------------------
# Crear una compañía actualiza las propiedades de TODOS los contactos y la
# configuración de la DUA escribe en la compañía: con otros agentes trabajando
# en paralelo eso da SerializationFailure si se hace tarde en la transacción.
_p4_prep = {}


def _p4_prepare():
    peru = env.ref('base.pe')
    for key, vals in (('closure', {'name': qa_name('P4 Cierre TC %s S.A.C.' % _p4_TS)}),
                      ('reval', {'name': qa_name('P4 Revaluación %s S.A.C.' % _p4_TS), 'country_id': peru.id,
                                 'account_fiscal_country_id': peru.id})):
        try:
            with env.cr.savepoint():
                comp = env['res.company'].create(dict(vals, currency_id=company.currency_id.id))
                env.user.company_ids = [Command.link(comp.id)]
                _p4_prep[key] = comp
        except Exception as e:  # noqa: BLE001
            _p4_prep[key + '_error'] = '%s: %s' % (type(e).__name__, e)
    try:
        with env.cr.savepoint():
            if not company.l10n_pe_dua_partner_id or not company.l10n_pe_dua_offset_account_id:
                customs = company.l10n_pe_dua_partner_id or _p4_partner(
                    'P4 SUNAT - Aduanas', vat='20131312955', country_id=peru.id)
                offset = company.l10n_pe_dua_offset_account_id or env['account.account'].search(
                    [('code', '=', '609190')], limit=1) or env['account.account'].create({
                        'name': qa_name('P4 Valor en aduana por regularizar'), 'code': '609198',
                        'account_type': 'expense', 'company_ids': [Command.link(company.id)]})
                company.write({'l10n_pe_dua_partner_id': customs.id, 'l10n_pe_dua_offset_account_id': offset.id})
                _p4_prep['dua_seeded'] = True
    except Exception as e:  # noqa: BLE001
        _p4_prep['dua_error'] = '%s: %s' % (type(e).__name__, e)


_p4_prepare()
print('P4 preparación:', {k: (v.display_name if hasattr(v, 'display_name') else v) for k, v in _p4_prep.items()})

_p4_bank_journal = _p4_journal('P4 Banco financiamiento', 'Q4BK', 'bank')
_p4_misc_journal = _p4_journal('P4 Operaciones financieras', 'Q4MS', 'general')
_p4_bank = _p4_partner('P4 BANCO FINANCIERO SA', vat='20100047218')


# ======================================================================
#  al_l10n_pe_bank_loan
# ======================================================================
def _p4_loan_new(**vals):
    loan = env['l10n_pe.bank.loan'].create(dict({
        'partner_id': _p4_bank.id, 'journal_id': _p4_bank_journal.id, 'misc_journal_id': _p4_misc_journal.id,
        'amount': 120000.0, 'rate': 12.0, 'installment_count': 12, 'date_disbursement': _p4_date(2026, 1, 15),
    }, **vals))
    loan.action_compute_schedule()
    return loan


caso('al_l10n_pe_bank_loan', 'Préstamo francés: desembolso con comisión e ITF, devengo y pago de la 1.ª cuota',
     'Tesorería ▸ Préstamos ▸ Nuevo (S/ 120 000, TEA 12 %, 12 cuotas) ▸ Calcular cronograma ▸ Confirmar; '
     'Devengar al 31/01 y Pagar cuota desde el asistente.')


def _p4_t_loan():
    loan = registro(_p4_loan_new(disbursement_fee=500.0, itf_applies=True), 'préstamo francés')
    check(loan.name.startswith('PRE/'), 'secuencia PRE/', loan.name)
    check(loan.principal_account_id.code.startswith('4511'), 'cuenta de capital 4511', loan.principal_account_id.code)
    check(loan.interest_payable_account_id.code.startswith('45511'), 'intereses por pagar 45511',
          loan.interest_payable_account_id.code)
    igual(len(loan.line_ids), 12, 'cronograma de 12 cuotas')
    igual(sum(loan.line_ids.mapped('principal')), 120000.0, 'capital del cronograma = préstamo')
    cuotas = {round(l.principal + l.interest, 2) for l in loan.line_ids.sorted('date_due')[:-1]}
    igual(len(cuotas), 1, 'cuota fija (método francés)')
    first = loan.line_ids.sorted('date_due')[0]
    igual(first.interest, round(120000 * (1.12 ** (31 / 360) - 1), 2), 'interés 1.ª cuota (TEA, 31 días, base 360)')
    loan.action_confirm()
    igual(loan.state, 'running', 'préstamo en curso')
    out_in = _p4_bank_journal._l10n_pe_treasury_outstanding_account('inbound')
    out_out = _p4_bank_journal._l10n_pe_treasury_outstanding_account('outbound')
    from odoo.addons.al_l10n_pe_itf.models.res_company import itf_amount
    itf = itf_amount(120000.0, company.root_id.l10n_pe_itf_rate)
    igual(_p4_balance(loan.move_ids, loan.principal_account_id), -120000.0, 'desembolso: capital al haber 4511')
    igual(_p4_balance(loan.move_ids, loan.fee_account_id), 500.0, 'comisión de desembolso al gasto')
    itf_net = itf_amount(119500.0, company.root_id.l10n_pe_itf_rate)
    igual(_p4_balance(loan.move_ids, out_in), 119500.0 - itf_net,
          'banco recibe el neto de comisión menos ITF (%s)' % itf_net)
    check(itf > 0, 'ITF calculado sobre el desembolso', 'ITF %s (tasa %s %%)' % (itf, company.root_id.l10n_pe_itf_rate))
    check(loan.tcea > 12.0, 'TCEA > TEA por la comisión', 'TCEA %.4f' % loan.tcea)
    loan._l10n_pe_accrue(_p4_date(2026, 1, 31))
    loan._l10n_pe_accrue(_p4_date(2026, 1, 31))
    devengado = round(first.interest * 16 / 31, 2)
    igual(first.interest_accrued, devengado, 'devengo de 16/31 días (idempotente)')
    igual(_p4_balance(loan.move_ids, loan.interest_payable_account_id), -devengado, 'interés por pagar devengado')
    wiz = env['l10n_pe.bank.loan.payment'].create({'loan_id': loan.id, 'operation': 'installment',
                                                   'line_id': first.id, 'date': first.date_due})
    igual(wiz.total, first.amount_total, 'asistente propone el total de la cuota')
    wiz.action_confirm()
    igual(first.state, 'paid', 'cuota 1 pagada')
    igual(_p4_balance(loan.move_ids, loan.interest_payable_account_id), 0.0, 'devengo cancelado al pagar')
    igual(_p4_balance(loan.move_ids, loan.interest_expense_account_id), first.interest, 'gasto financiero = interés')
    igual(loan.principal_balance, 120000.0 - first.principal, 'saldo de capital tras la cuota')
    check(_p4_balanced(loan.move_ids), 'todos los asientos cuadran', '%s asientos' % len(loan.move_ids))
    registro(loan.move_ids, 'asientos del préstamo')
    second = loan.line_ids.sorted('date_due')[1]
    try:
        with env.cr.savepoint():
            loan._l10n_pe_pay_line(loan.line_ids.sorted('date_due')[2], second.date_due)
        check(False, 'impide pagar cuotas fuera de orden')
    except Exception as e:  # noqa: BLE001
        check('UserError' in type(e).__name__, 'impide pagar cuotas fuera de orden', str(e)[:90])


_p4_run(_p4_t_loan)

caso('al_l10n_pe_bank_loan', 'Prepago con reducción de cuota y línea de crédito',
     'Tesorería ▸ Líneas de crédito ▸ Nueva (S/ 150 000); préstamo ligado ▸ Confirmar ▸ Prepagar capital S/ 30 000.')


def _p4_t_loan_prepay():
    cline = registro(env['l10n_pe.treasury.credit.line'].create({
        'name': qa_name('P4 Línea préstamos'), 'partner_id': _p4_bank.id, 'line_type': 'loan',
        'amount_limit': 150000.0}), 'línea de crédito')
    loan = registro(_p4_loan_new(credit_line_id=cline.id), 'préstamo con línea')
    loan.action_confirm()
    igual(cline.amount_used, 120000.0, 'línea: usado')
    igual(cline.amount_available, 30000.0, 'línea: disponible')
    other = _p4_loan_new(credit_line_id=cline.id, amount=50000.0)
    try:
        with env.cr.savepoint():
            other.action_confirm()
        check(False, 'bloquea exceder la línea de crédito')
    except Exception as e:  # noqa: BLE001
        check('UserError' in type(e).__name__, 'bloquea exceder la línea de crédito', str(e)[:90])
    other.invalidate_recordset()
    other.unlink()
    first = loan.line_ids.sorted('date_due')[0]
    loan._l10n_pe_pay_line(first, first.date_due)
    old = loan.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')[0].amount_total
    balance = loan.principal_balance
    loan._l10n_pe_prepay(_p4_date(2026, 3, 1), 30000.0, mode='installment')
    pending = loan.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')
    igual(len(pending), 11, 'mantiene 11 cuotas pendientes')
    igual(sum(pending.mapped('principal')), balance - 30000.0, 'capital pendiente = saldo − prepago')
    check(pending[1].amount_total < old, 'la cuota baja tras el prepago', '%s → %s' % (old, pending[1].amount_total))
    check(_p4_balanced(loan.move_ids), 'asientos cuadrados')
    registro(loan.move_ids, 'asientos del préstamo prepagado')


_p4_run(_p4_t_loan_prepay)


# ======================================================================
#  al_l10n_pe_bank_guarantee
# ======================================================================
_p4_entity = _p4_partner('P4 MUNICIPALIDAD DE PRUEBA')
_p4_supplier = _p4_partner('P4 CONTRATISTA SAC')


def _p4_guarantee(**vals):
    return env['l10n_pe.bank.guarantee'].create(dict({
        'number': 'QA20-CF-%s' % _p4_TS, 'bank_id': _p4_bank.id, 'partner_id': _p4_entity.id, 'amount': 50000.0,
        'date_issue': _p4_date(2026, 1, 10), 'date_end': _p4_date(2026, 7, 10), 'journal_id': _p4_bank_journal.id,
        'commission_rate': 0.5, 'commission_min': 100.0,
    }, **vals))


caso('al_l10n_pe_bank_guarantee', 'Carta fianza emitida: comisión por trimestre, activación, renovación y ejecución',
     'Tesorería ▸ Cartas fianza ▸ Nueva (S/ 50 000, 0,5 % trimestral) ▸ Activar ▸ Renovar ▸ Ejecutar.')


def _p4_t_guarantee():
    g = registro(_p4_guarantee(), 'carta fianza emitida')
    igual(g.commission_amount, 750.0, 'comisión 3 trimestres × 0,5 % × 50 000')
    small = _p4_guarantee(amount=5000.0, date_end=_p4_date(2026, 2, 10), number='QA20-CF-%s-B' % _p4_TS)
    igual(small.commission_amount, 100.0, 'comisión mínima')
    small.unlink()
    g.action_activate()
    igual(g.state, 'active', 'fianza activa')
    out = _p4_bank_journal._l10n_pe_treasury_outstanding_account('outbound')
    igual(_p4_balance(g.move_ids, g.commission_account_id), 750.0, 'gasto de comisión', )
    igual(_p4_balance(g.move_ids, out), -750.0, 'salida de banco por la comisión')
    new = registro(g._l10n_pe_renew(_p4_date(2027, 1, 10)), 'renovación')
    igual(g.state, 'renewed', 'original queda renovada')
    igual(new.state, 'active', 'renovación activa')
    igual(new.date_issue, _p4_date(2026, 7, 10), 'renovación desde el vencimiento anterior')
    igual(_p4_balance(new.move_ids, new.commission_account_id), new.commission_amount, 'comisión de la renovación')
    expense = env['account.account'].search([('code', '=like', '659%'), ('account_type', '=', 'expense'),
                                             ('company_ids', 'in', company.id)], limit=1)
    new._l10n_pe_execute(_p4_date(2026, 9, 1), 20000.0, _p4_bank_journal, expense)
    igual(new.state, 'executed', 'fianza ejecutada')
    igual(_p4_balance(new.move_ids, expense), 20000.0, 'ejecución al gasto (%s)' % expense.code)
    registro((g | new).move_ids, 'asientos de la fianza')


_p4_run(_p4_t_guarantee)

caso('al_l10n_pe_bank_guarantee', 'Carta fianza recibida: sin comisión, plazo de reclamo y aviso por cron',
     'Tesorería ▸ Cartas fianza ▸ Nueva (recibida del contratista) ▸ Activar; el cron avisa antes del vencimiento.')


def _p4_t_guarantee_received():
    g = registro(_p4_guarantee(direction='received', partner_id=_p4_supplier.id, journal_id=False,
                               number='QA20-CFR-%s' % _p4_TS), 'fianza recibida')
    igual(g.commission_amount, 0.0, 'sin comisión')
    igual(g.claim_deadline, _p4_date(2026, 7, 25), 'plazo de reclamo (art. 1898 CC: +15 días)')
    g.action_activate()
    check(not g.move_ids, 'no genera asientos')
    with _p4_today(_p4_date(2026, 7, 1)):
        env['l10n_pe.bank.guarantee']._cron_l10n_pe_bank_guarantees()
    act = g.activity_ids
    check(bool(act), 'cron crea actividad de aviso')
    if act:
        igual(act[:1].date_deadline, _p4_date(2026, 7, 25), 'actividad vence con el plazo de reclamo')


_p4_run(_p4_t_guarantee_received)


# ======================================================================
#  al_l10n_pe_term_deposit
# ======================================================================
def _p4_deposit(**vals):
    return env['l10n_pe.term.deposit'].create(dict({
        'partner_id': _p4_bank.id, 'journal_id': _p4_bank_journal.id, 'misc_journal_id': _p4_misc_journal.id,
        'amount': 100000.0, 'rate': 6.0, 'day_basis': '360', 'date_start': _p4_date(2026, 1, 1), 'term_days': 180,
    }, **vals))


caso('al_l10n_pe_term_deposit', 'Depósito a plazo: apertura, devengo mensual y cancelación al vencimiento',
     'Tesorería ▸ Depósitos a plazo ▸ Nuevo (S/ 100 000, TEA 6 %, 180 días) ▸ Abrir ▸ Devengar ▸ Cancelar.')


def _p4_t_deposit():
    d = registro(_p4_deposit(), 'depósito a plazo')
    check(d.name.startswith('DEP/'), 'secuencia DEP/', d.name)
    igual(d.date_end, _p4_date(2026, 6, 30), 'vencimiento a 180 días')
    check(d.deposit_account_id.code.startswith('1062'), 'cuenta 1062', d.deposit_account_id.code)
    igual(d.expected_interest, 2956.30, 'interés esperado 100 000 × (1,06^(180/360) − 1)')
    d.action_open()
    igual(d.state, 'open', 'depósito abierto')
    igual(_p4_balance(d.move_ids, d.deposit_account_id), 100000.0, 'cargo a 1062')
    igual(_p4_balance(d.move_ids, _p4_bank_journal.default_account_id), -100000.0, 'abono al banco')
    for me in (_p4_date(2026, 1, 31), _p4_date(2026, 2, 28), _p4_date(2026, 3, 31)):
        d._l10n_pe_accrue(me)
        d._l10n_pe_accrue(me)
    exp = d._l10n_pe_interest_until(_p4_date(2026, 3, 31))
    igual(d.interest_accrued, exp, 'devengo a marzo (idempotente)')
    igual(len(d.move_ids), 4, 'apertura + 3 devengos')
    igual(_p4_balance(d.move_ids, d.income_account_id), -exp, 'ingreso financiero devengado')
    d._l10n_pe_close(_p4_date(2026, 6, 30))
    igual(d.state, 'closed', 'depósito cancelado')
    igual(_p4_balance(d.move_ids, d.deposit_account_id), 0.0, 'saldo 1062 en cero')
    igual(_p4_balance(d.move_ids, d.interest_account_id), 0.0, 'intereses por cobrar en cero')
    igual(_p4_balance(d.move_ids, _p4_bank_journal.default_account_id), d.expected_interest,
          'el banco recibe capital + intereses')
    check(_p4_balanced(d.move_ids), 'asientos cuadrados')
    registro(d.move_ids, 'asientos del depósito')


_p4_run(_p4_t_deposit)

caso('al_l10n_pe_term_deposit', 'Renovación con capitalización y garantía de alquiler con liberación parcial',
     'Depósito ▸ Renovar (capitaliza intereses); Depósito de garantía ▸ Abrir ▸ Liberar S/ 2 000 y luego el saldo.')


def _p4_t_deposit_renew():
    d = registro(_p4_deposit(capitalize_interest=True), 'depósito capitalizable')
    d.action_open()
    new = registro(d._l10n_pe_renew(_p4_date(2026, 6, 30)), 'renovación')
    igual(d.state, 'renewed', 'original renovado')
    igual(new.state, 'open', 'renovación abierta')
    igual(new.amount, 100000.0 + d.expected_interest, 'capital nuevo = capital + intereses')
    igual(_p4_balance(d.move_ids | new.move_ids, d.interest_account_id), 0.0,
          'intereses capitalizados (sin saldo por cobrar)')
    landlord = _p4_partner('P4 ARRENDADOR ALMACÉN SAC', vat='20100070970')
    g = registro(_p4_deposit(deposit_type='guarantee_given', partner_id=landlord.id, amount=6000.0, rate=0.0,
                             term_days=0, date_end=False), 'garantía de alquiler')
    check(g.deposit_account_id.code.startswith('1643'), 'garantía en 1643', g.deposit_account_id.code)
    g.action_open()
    g._l10n_pe_release(_p4_date(2026, 3, 1), 2000.0)
    igual(g.remaining_amount, 4000.0, 'saldo tras liberación parcial')
    try:
        with env.cr.savepoint():
            g._l10n_pe_release(_p4_date(2026, 3, 2), 5000.0)
        check(False, 'no libera más del saldo')
    except Exception as e:  # noqa: BLE001
        check('UserError' in type(e).__name__, 'no libera más del saldo', str(e)[:80])
    g._l10n_pe_release(_p4_date(2026, 4, 1), 4000.0)
    igual(g.state, 'closed', 'garantía cerrada')
    igual(_p4_balance(g.move_ids, g.deposit_account_id), 0.0, 'saldo 1643 en cero')


_p4_run(_p4_t_deposit_renew)


# ======================================================================
#  al_l10n_pe_lease (NIIF 16)
# ======================================================================
_p4_lease_journal = _p4_journal('P4 Arrendamientos', 'Q4AR', 'general')
_p4_lease_purchase = _p4_journal('P4 Compras arrendamientos', 'Q4AP', 'purchase', l10n_latam_use_documents=False)
_p4_lessor = _p4_partner('P4 ARRENDADORA ALMACENES SAC', vat='20100070970')


def _p4_lease(**vals):
    lease = env['l10n_pe.lease'].create(dict({
        'partner_id': _p4_lessor.id, 'property_description': qa_name('P4 Almacén Callao'),
        'date_start': _p4_date(2026, 1, 1), 'term_months': 36, 'payment_amount': 1000.0,
        'payment_timing': 'advance', 'annual_rate': 12.0, 'journal_id': _p4_lease_journal.id,
    }, **vals))
    lease.action_create_liability_accounts()
    return lease


caso('al_l10n_pe_lease', 'Reconocimiento NIIF 16: derecho de uso, pasivo, activo, préstamo y cuotas',
     'Contabilidad ▸ Arrendamientos ▸ Nuevo (36 meses, S/ 1 000 adelantado, TEA 12 %) ▸ Crear subcuentas ▸ '
     'Confirmar ▸ Registrar cuota (factura del arrendador).')

_p4_lease_ctx = {}


def _p4_t_lease():
    lease = registro(_p4_lease(initial_direct_costs=500.0), 'arrendamiento')
    rate = 1.12 ** (1 / 12) - 1
    exp = round(sum(1000.0 / (1 + rate) ** k for k in range(1, 36)), 2)
    igual(lease.liability_amount, exp, 'pasivo = VP de 35 cuotas (la 1.ª es adelantada)')
    igual(lease.rou_amount, round(exp + 1000.0 + 500.0, 2), 'derecho de uso = pasivo + cuota adelantada + costos')
    check(lease.liability_long_account_id.code.startswith('4521'), 'subcuenta pasivo LP 4521',
          lease.liability_long_account_id.code)
    check(lease.liability_short_account_id.code.startswith('4522'), 'subcuenta pasivo CP 4522',
          lease.liability_short_account_id.code)
    lease.action_confirm()
    igual(lease.state, 'running', 'contrato en curso')
    move = lease.initial_move_id
    igual(move.state, 'posted', 'asiento inicial publicado')
    clearing = move.line_ids.filtered(lambda l: l.account_id == lease.clearing_account_id)
    igual(sum(clearing.mapped('credit')), 1500.0, 'transitoria: cuota adelantada + costos')
    variant = lease.asset_id.main_variant_id
    igual((variant.method, variant.method_number), ('linear', 36), 'activo lineal a 36 meses')
    igual(lease.asset_id.original_value, lease.rou_amount, 'valor del activo = derecho de uso')
    loan = lease.loan_id
    igual(loan.duration, 35, 'préstamo (account_loans) de 35 cuotas')
    igual(loan.amount_borrowed, lease.liability_amount, 'préstamo = pasivo')
    check(lease.asset_id in loan.linked_assets_ids, 'activo y pasivo enlazados por grupo')
    first = env['account.move'].browse(lease.action_register_installment()['res_id'])
    igual(first.invoice_line_ids.account_id, lease.clearing_account_id, 'cuota 1 salda la transitoria')
    second = env['account.move'].browse(lease.action_register_installment()['res_id'])
    igual(second.invoice_line_ids.account_id, lease.liability_short_account_id, 'cuota 2 al pasivo CP')
    igual(second.invoice_date, _p4_date(2026, 2, 1), 'cuota 2 fechada 01/02')
    for b in first | second:
        b.journal_id = _p4_lease_purchase
        b.action_post()
    registro(first | second, 'facturas del arrendador')
    registro(move, 'asiento inicial')
    _p4_lease_ctx['lease'] = lease


_p4_run(_p4_t_lease)

caso('al_l10n_pe_lease', 'Remedición (aumento de renta) tras publicar la depreciación del mes',
     'Arrendamiento ▸ Contabilizar depreciación de octubre ▸ Remedir desde 01/11/2026 (renta S/ 1 100, 26 meses).')


def _p4_t_lease_remeasure():
    lease = _p4_lease(property_description=qa_name('P4 Oficina remedición'))
    registro(lease, 'arrendamiento a remedir')
    lease.action_confirm()
    variant = lease.asset_id.main_variant_id
    posted_dep = variant.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
    last_dep = max(posted_dep.mapped('date')) if posted_dep else None
    loan_posted = lease.loan_id.line_ids.generated_move_ids.filtered(lambda m: m.state == 'posted')
    print('    depreciación publicada hasta', last_dep, '; asientos préstamo publicados', len(loan_posted))
    # Hoy 30/10: la cuota de octubre (01/10) está contabilizada; la depreciación de octubre (31/10) no.
    try:
        with env.cr.savepoint():
            env['l10n_pe.lease.remeasure'].with_context(default_lease_id=lease.id).create({
                'date': _p4_date(2026, 10, 1), 'payment_amount': 1100.0, 'remaining_months': 27,
                'annual_rate': 12.0, 'reason': 'x'}).action_apply()
        check(False, 'rechaza remedir un mes ya contabilizado (01/10)')
    except Exception as e:  # noqa: BLE001
        check('UserError' in type(e).__name__, 'rechaza remedir un mes ya contabilizado (01/10)', str(e)[:110])
    # Hoy es 30/10: la depreciación de octubre (31/10) aún no puede publicarse
    # (Odoo rechaza depreciaciones publicadas en el futuro al modificar el activo).
    # Se simula el 02/11: se publica la depreciación de octubre y se remide desde el 01/11.
    from freezegun import freeze_time
    _p4_freeze = freeze_time('2026-11-02 10:00:00')
    _p4_freeze.start()
    try:
        _p4_t_lease_remeasure_nov(lease, variant)
    finally:
        _p4_freeze.stop()


def _p4_t_lease_remeasure_nov(lease, variant):
    oct_dep = variant.depreciation_move_ids.filtered(
        lambda m: m.state == 'draft' and m.date <= _p4_date(2026, 10, 31))
    oct_dep.action_post()
    check(bool(oct_dep), 'depreciación de octubre publicada', ', '.join(oct_dep.mapped('name')))
    rou_before = lease.asset_id.book_value
    old_loan = lease.loan_id
    wizard = env['l10n_pe.lease.remeasure'].with_context(default_lease_id=lease.id).create({
        'date': _p4_date(2026, 11, 1), 'payment_amount': 1100.0, 'remaining_months': 26,
        'annual_rate': 12.0, 'reason': 'Reajuste de la renta'})
    rate = 1.12 ** (1 / 12) - 1
    expected = round(1100.0 + sum(1100.0 / (1 + rate) ** k for k in range(1, 26)), 2)
    igual(wizard.new_liability, expected, 'nuevo pasivo (incluye la cuota adelantada de noviembre)')
    difference = wizard.difference
    check(difference > 0, 'diferencia positiva (aumento)', difference)
    wizard.action_apply()
    igual(old_loan.state, 'closed', 'préstamo anterior cerrado')
    igual(lease.loan_id.amount_borrowed, expected, 'nuevo préstamo = nuevo pasivo')
    increase = lease.asset_id.main_variant_id.children_ids
    igual(sum(increase.mapped('original_value')), difference, 'aumento bruto del derecho de uso')
    igual(lease.asset_id.book_value, rou_before + difference, 'valor en libros + diferencia')
    igual(lease.event_ids.mapped('kind'), ['remeasurement'], 'evento de remedición')
    igual(lease.liability_difference, 0.0, 'libro cuadra con la tabla')
    registro(lease.event_ids.move_ids, 'asientos de remedición')


_p4_run(_p4_t_lease_remeasure)


# ======================================================================
#  al_l10n_pe_import_dua
# ======================================================================
caso('al_l10n_pe_import_dua', 'DUA: número de la DAM, liquidación (derechos + IGV) y publicación',
     'Compras ▸ Facturas ▸ Nueva con tipo 50 (DUA), Aduana 118, régimen 10 ▸ Generar líneas de la liquidación ▸ '
     'Confirmar.')


def _p4_t_dua():
    if _p4_prep.get('dua_error'):
        raise RuntimeError('no se pudo configurar la DUA en la compañía: %s' % _p4_prep['dua_error'])
    if _p4_prep.get('dua_seeded'):
        aviso('compañía sin socio Aduanas / cuenta puente de DUA', 'se configuraron al inicio de la fase')
    customs = company.l10n_pe_dua_partner_id
    journal = env['account.journal'].search([
        *env['account.journal']._check_company_domain(company),
        ('type', '=', 'purchase'), ('l10n_latam_use_documents', '=', True)], limit=1)
    seq = _p4_TS[-5:]
    dua = registro(env['account.move'].create({
        'move_type': 'in_invoice', 'partner_id': customs.id, 'journal_id': journal.id,
        'l10n_latam_document_type_id': env.ref('l10n_pe.document_type50').id,
        'invoice_date': _p4_date(2026, 10, 5), 'ref': qa_name('P4 DUA'),
        'l10n_pe_dua_customs_code': '118', 'l10n_pe_dua_year': '2026', 'l10n_pe_dua_regime': '10',
        'l10n_pe_dua_sequence': seq, 'l10n_pe_dua_customs_value': 10000.0,
        'l10n_pe_dua_ad_valorem': 600.0, 'l10n_pe_dua_other_duties': 100.0,
    }), 'DUA')
    check(dua.l10n_pe_dua_is_dua, 'reconocida como DUA')
    igual(dua.l10n_latam_document_number, '118-2026-10-%06d' % int(seq), 'número DAM aduana-año-régimen-correlativo')
    dua.action_l10n_pe_dua_generate_lines()
    igual(dua.l10n_pe_dua_tax_base, 10700.0, 'base del IGV = valor + derechos')
    igual(dua.amount_tax, 1926.0, 'IGV 18 % de 10 700')
    igual(dua.amount_total, 2626.0, 'total a pagar a Aduanas: derechos 700 + IGV 1 926')
    dua.action_l10n_pe_dua_generate_lines()
    igual(len(dua.invoice_line_ids.filtered('l10n_pe_dua_line_kind')), 4, 'regenerar no duplica líneas')
    dua.action_post()
    igual(dua.state, 'posted', 'DUA publicada')
    try:
        with env.cr.savepoint():
            dua.action_l10n_pe_dua_create_landed_costs()
        check(False, 'costos en destino exigen recepciones')
    except Exception as e:  # noqa: BLE001
        check('UserError' in type(e).__name__, 'costos en destino exigen recepciones', str(e)[:90])


_p4_run(_p4_t_dua)


# ======================================================================
#  al_l10n_pe_exchange_closure  (compañía propia: el cierre toma todos los saldos de la compañía)
# ======================================================================
_p4_usd = env.ref('base.USD')

caso('al_l10n_pe_exchange_closure', 'Cierre mensual de T.C.: activo a compra, pasivo a venta, detalle por socio',
     'Contabilidad ▸ Cierre ▸ Cierre de tipo de cambio ▸ Nuevo (setiembre 2026, compra 3,80 / venta 3,82) ▸ '
     'Calcular ▸ Contabilizar.')


def _p4_t_closure():
    comp = _p4_prep.get('closure')
    if not comp:
        raise RuntimeError('compañía aislada no creada: %s' % _p4_prep.get('closure_error'))
    cenv = env(context=dict(env.context, allowed_company_ids=comp.ids))
    registro(comp, 'compañía aislada del cierre')
    Account = cenv['account.account'].with_company(comp)
    acc = lambda code, name, t, **kw: Account.create(dict(  # noqa: E731
        {'code': code, 'name': name, 'account_type': t, 'company_ids': [Command.set(comp.ids)]}, **kw))
    bank = acc('Q4B104', 'Bancos ME', 'asset_current', currency_id=_p4_usd.id, l10n_pe_exchange_closing='summary')
    rec = acc('Q4B121', 'Por cobrar ME', 'asset_receivable', reconcile=True, currency_id=_p4_usd.id,
              l10n_pe_exchange_closing='detail')
    loanacc = acc('Q4B451', 'Préstamos ME', 'liability_non_current', currency_id=_p4_usd.id,
                  l10n_pe_exchange_closing='summary')
    other = acc('Q4B999', 'Contrapartida', 'equity', currency_id=_p4_usd.id)
    gain = acc('Q4B776', 'Ganancia dif. cambio', 'income_other')
    loss = acc('Q4B676', 'Pérdida dif. cambio', 'expense')
    comp.write({'income_currency_exchange_account_id': gain.id, 'expense_currency_exchange_account_id': loss.id})
    journal = cenv['account.journal'].create({'name': qa_name('P4 Cierre T.C.'), 'code': 'Q4TC', 'type': 'general',
                                              'company_id': comp.id})
    comp.l10n_pe_exchange_closing_journal_id = journal
    pa = _p4_partner('P4 Cliente A TC')
    pb = _p4_partner('P4 Cliente B TC')

    def entry(day, lines):
        m = cenv['account.move'].with_company(comp).create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': day,
            'line_ids': [Command.create({'account_id': a.id, 'partner_id': p.id if p else False,
                                         'currency_id': _p4_usd.id, 'amount_currency': u, 'balance': s})
                         for a, u, s, p in lines]})
        m.action_post()
        return m
    entry('2026-09-10', [(bank, 1000.0, 3700.0, None), (loanacc, -1000.0, -3700.0, None)])
    entry('2026-09-12', [(rec, 1000.0, 3700.0, pa), (other, -1000.0, -3700.0, None)])
    entry('2026-09-14', [(rec, 500.0, 1855.0, pb), (other, -500.0, -1855.0, None)])
    _p4_rate(_p4_usd, '2026-10-01', comp, rate_purchase=3.80, rate_sale=3.82)
    closure = cenv['l10n_pe.exchange.closure'].with_company(comp).create({
        'company_id': comp.id, 'currency_id': _p4_usd.id, 'month': '09', 'year': 2026,
        'rate_purchase': 0.0, 'rate_sale': 0.0, 'journal_id': journal.id})
    registro(closure, 'cierre de T.C.')
    igual(closure.date, _p4_date(2026, 9, 30), 'fecha de asiento fin de mes')
    igual(closure.rate_date, _p4_date(2026, 10, 1), 'T.C. de cierre SBS publicado al día siguiente')
    with _p4_patch.object(type(cenv['res.currency']), 'l10n_pe_update_range_bcrp', autospec=True, return_value=0), \
            _p4_patch.object(type(cenv['res.currency']), 'l10n_pe_update_date_apis', autospec=True, return_value=0):
        closure.action_fetch_rate()
    igual((closure.rate_purchase, closure.rate_sale), (3.80, 3.82), 'T.C. tomado del registro (sin red)')
    closure.action_compute()
    lb = closure.line_ids.filtered(lambda l: l.account_id == bank)
    igual(lb.rate_type, 'purchase', 'activo usa T.C. compra')
    igual(lb.adjustment, 100.0, 'ajuste banco 1 000 × (3,80 − 3,70)')
    ll = closure.line_ids.filtered(lambda l: l.account_id == loanacc)
    igual(ll.rate_type, 'sale', 'pasivo usa T.C. venta')
    igual(ll.adjustment, -120.0, 'ajuste préstamo −1 000 × (3,82 − 3,70)')
    igual(closure.line_ids.filtered(lambda l: l.account_id == rec and l.partner_id == pa).adjustment, 100.0,
          'detalle socio A')
    igual(closure.line_ids.filtered(lambda l: l.account_id == rec and l.partner_id == pb).adjustment, 45.0,
          'detalle socio B (1 900 − 1 855)')
    igual(closure.amount_gain, 245.0, 'ganancia total')
    igual(closure.amount_loss, 120.0, 'pérdida total (no se netea)')
    closure.action_post()
    igual(closure.state, 'posted', 'cierre contabilizado')
    mv = closure.move_id
    igual(_p4_round(sum(mv.line_ids.filtered(lambda l: l.account_id == gain).mapped('credit'))), 245.0,
          'abono a ganancia por diferencia de cambio')
    igual(_p4_round(sum(mv.line_ids.filtered(lambda l: l.account_id == loss).mapped('debit'))), 120.0,
          'cargo a pérdida por diferencia de cambio')
    usd_lines = mv.line_ids.filtered(lambda l: l.currency_id == _p4_usd)
    check(usd_lines and all(not l.amount_currency for l in usd_lines), 'el ajuste no mueve moneda extranjera',
          '%s líneas en USD' % len(usd_lines))
    igual(mv.line_ids.filtered(lambda l: l.account_id == bank).l10n_pe_closing_rate, 3.80, 'T.C. citado en la línea', 3)
    registro(mv, 'asiento de cierre')


_p4_run(_p4_t_closure)


# ======================================================================
#  al_l10n_pe_multicurrency_revaluation (compañía propia: el informe lee todos los apuntes)
# ======================================================================
caso('al_l10n_pe_multicurrency_revaluation', 'Informe de G/P no realizadas con T.C. compra/venta por cuenta y asiento',
     'Contabilidad ▸ Informes ▸ Ganancias/pérdidas no realizadas al 30/09/2026 ▸ ver columna T.C. ▸ '
     'Ajuste ▸ asiento de provisión.')


def _p4_t_revaluation():
    comp = _p4_prep.get('reval')
    if not comp:
        raise RuntimeError('compañía aislada no creada: %s' % _p4_prep.get('reval_error'))
    cenv = env(context=dict(env.context, allowed_company_ids=comp.ids))
    registro(comp, 'compañía aislada de la revaluación')
    day = '2026-09-30'
    _p4_rate(_p4_usd, day, comp, rate_sale=3.700, rate_purchase=3.720)
    journal = cenv['account.journal'].create({'name': qa_name('P4 Varios'), 'code': 'Q4VR', 'type': 'general',
                                              'company_id': comp.id})
    Account = cenv['account.account'].with_company(comp)
    acc = lambda code, name, t, **kw: Account.create(dict(  # noqa: E731
        {'code': code, 'name': name, 'account_type': t, 'company_ids': [Command.set(comp.ids)]}, **kw))
    expense = acc('659001', 'Gasto', 'expense')
    income = acc('759001', 'Ingreso', 'income')
    payable = acc('421201', 'Por pagar ME', 'liability_payable', reconcile=True)
    receivable = acc('121201', 'Por cobrar ME', 'asset_receivable', reconcile=True)
    check(payable.l10n_pe_revaluation_rate_visible and not expense.l10n_pe_revaluation_rate_visible,
          'campo T.C. visible solo en cuentas de balance')
    payable.l10n_pe_revaluation_rate_type = 'purchase'
    receivable.l10n_pe_revaluation_rate_type = 'sale'
    partner = _p4_partner('P4 Socio ME')
    for account, cur, bal in ((payable, -100.0, -370.0), (receivable, 250.0, 925.0)):
        cp = expense if bal > 0 else income
        m = cenv['account.move'].with_company(comp).create({
            'move_type': 'entry', 'date': day, 'journal_id': journal.id, 'line_ids': [
                Command.create({'name': 'ME', 'partner_id': partner.id, 'account_id': account.id,
                                'currency_id': _p4_usd.id, 'amount_currency': cur, 'balance': bal}),
                Command.create({'name': 'Contrapartida', 'account_id': cp.id, 'currency_id': _p4_usd.id,
                                'amount_currency': -cur, 'balance': -bal})]})
        m.action_post()
    report = cenv.ref('account_reports.multicurrency_revaluation_report').with_company(comp)
    options = report.get_options({'selected_variant_id': report.id, 'unfold_all': True,
                                  'date': {'date_from': day, 'date_to': day, 'mode': 'range', 'filter': 'custom'}})
    check('rate_used' in [c['expression_label'] for c in options['columns']], 'columna T.C. presente')
    lines = report._get_lines(options)

    def val(line, label):
        for col, cd in zip(line['columns'], options['columns']):
            if cd['expression_label'] == label:
                return col['no_format']

    def acc_line(account):
        return next((l for l in lines if l['id'].endswith('{"groupby": "account_code"}~~%s' % account.code)
                     or l['id'].endswith('{"groupby": "account_id"}~account.account~%s' % account.id)), None)
    lp, lr = acc_line(payable), acc_line(receivable)
    check(lp and lr, 'líneas de las cuentas en el informe')
    if lp and lr:
        igual(val(lp, 'rate_used'), 'S/ 3.720', 'por pagar revaluada a T.C. compra')
        igual(val(lp, 'adjustment'), -2.0, 'ajuste por pagar −100 × (3,72 − 3,70)')
        igual(val(lr, 'rate_used'), 'S/ 3.700', 'por cobrar revaluada a T.C. venta')
        igual(val(lr, 'adjustment'), 0.0, 'por cobrar sin ajuste')
    total = next((l for l in lines if report._get_model_info_from_id(l['id']) == ('res.currency', _p4_usd.id)), None)
    if check(bool(total), 'línea total de la moneda'):
        igual(total['name'], 'USD (1 USD = S/ 3.700)', 'cabecera con el T.C.')
        igual(val(total, 'rate_used'), '', 'T.C. en blanco al mezclar tasas')
        igual(val(total, 'adjustment'), -2.0, 'ajuste total')
    wizard = cenv['account.multicurrency.revaluation.wizard'].with_company(comp).with_context(
        multicurrency_revaluation_report_options=options).create({
            'journal_id': journal.id, 'date': day,
            'expense_provision_account_id': expense.id, 'income_provision_account_id': income.id})
    mvals = [c[2] for c in wizard._get_move_vals()['line_ids']]
    pl = [v for v in mvals if v['account_id'] == payable.id]
    check(pl and pl[0]['name'] == 'Provisión de USD (T.C. S/ 3.720)', 'línea del asiento cita el T.C. aplicado',
          pl and pl[0]['name'])
    if pl:
        igual(pl[0]['credit'], 2.0, 'abono de 2,00 a por pagar')
    res = wizard.create_entries()
    move = cenv['account.move'].browse(res.get('res_id')) if isinstance(res, dict) and res.get('res_id') else \
        cenv['account.move'].search([('company_id', '=', comp.id), ('journal_id', '=', journal.id)],
                                    order='id desc', limit=1)
    check(move and move.state == 'posted', 'asiento de ajuste publicado', move.name if move else '')
    registro(move, 'asiento de revaluación')


_p4_run(_p4_t_revaluation)

# ======================================================================= PARTE 1
# -*- coding: utf-8 -*-
# Fase contabilidad_b — parte 1: pagos, comprobantes, extractos, lotes y tesorería.
# Autocontenido: todo lo de nivel de módulo lleva prefijo _p1_.
from datetime import date as _p1_date

_p1_PEN = company.currency_id
_p1_USD = env.ref('base.USD')
_p1_PE = env.ref('base.pe')
# OdooBot (superusuario del shell) no puede marcar cuentas bancarias como de confianza:
# se crean como el administrador, como en pantalla.
_p1_BANKACC = env['res.partner.bank'].with_user(env.ref('base.user_admin'))


def _p1_rate(day, value):
    """Busca o crea el T.C. USD del día; devuelve el inverse_company_rate vigente ese día."""
    Rate = env['res.currency.rate']
    rate = Rate.search([('currency_id', '=', _p1_USD.id), ('company_id', '=', company.id),
                        ('name', '=', day)], limit=1)
    if not rate:
        rate = Rate.create({'currency_id': _p1_USD.id, 'company_id': company.id, 'name': day,
                            'inverse_company_rate': value})
    return rate.inverse_company_rate


def _p1_account(code, name, account_type='asset_current', reconcile=True):
    Account = env['account.account']
    acc = Account.search([*Account._check_company_domain(company), ('code', '=', code)], limit=1)
    return acc or Account.create({'code': code, 'name': qa_name(name), 'account_type': account_type,
                                  'reconcile': reconcile})


def _p1_journal(code, name, jtype, outstanding=None, **vals):
    Journal = env['account.journal']
    journal = Journal.search([('company_id', '=', company.id), ('code', '=', code)], limit=1)
    if not journal:
        journal = Journal.create(dict({'name': qa_name(name), 'code': code, 'type': jtype,
                                       'company_id': company.id}, **vals))
    if outstanding:
        (journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids) \
            .payment_account_id = outstanding
    return journal


def _p1_partner(name, **vals):
    return env['res.partner'].create(dict({'name': qa_name(name)}, **vals))


def _p1_open_line(move):
    return move.line_ids.filtered(lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))


_p1_OUT = _p1_account('1049P11', 'P1 Pendientes de pago/cobro')
_p1_SALE = _p1_journal('Q1VT', 'P1 Ventas sin EDI', 'sale', l10n_latam_use_documents=False)
_p1_PURCH = _p1_journal('Q1CP', 'P1 Compras sin documentos', 'purchase', l10n_latam_use_documents=False)


def _p1_doc(move_type, partner, amount, currency=None, day=_p1_date(2026, 10, 5), **vals):
    move = env['account.move'].create(dict({
        'move_type': move_type, 'partner_id': partner.id,
        'journal_id': (_p1_SALE if move_type.startswith('out') else _p1_PURCH).id,
        'invoice_date': day, 'date': day, 'currency_id': (currency or _p1_PEN).id,
        'invoice_line_ids': [Command.create({'name': 'Servicio QA20', 'price_unit': amount,
                                             'tax_ids': [Command.clear()]})],
    }, **vals))
    move.action_post()
    return move


# ======================================================================
#  al_account_payments
# ======================================================================
caso('al_account_payments', 'N.º de operación = payment_reference nativo y medio de pago SUNAT',
     'Contabilidad → Clientes → Pagos → Nuevo: medio «003 Transferencia», N.º de operación; Confirmar.')


def _p1_ap_related():
    bank = registro(_p1_journal('Q1BOP', 'P1 Banco exige operación', 'bank', _p1_OUT,
                                l10n_pe_require_operation_number=True), 'diario que exige n.º de operación')
    partner = registro(_p1_partner('P1 Cliente pagos SAC', vat='20557912879', country_id=_p1_PE.id))
    transf = env.ref('al_account_payments.pe_catalog_payment_003')
    pay = env['account.payment'].create({
        'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': partner.id,
        'amount': 250.0, 'journal_id': bank.id, 'date': _p1_date(2026, 10, 20),
        'pe_payment_method_id': transf.id})
    fld = pay._fields['bank_operation_number']
    check(fld.related == 'payment_reference' or getattr(fld, 'related', None) == ('payment_reference',),
          'bank_operation_number es related a payment_reference', str(fld.related))
    try:
        with env.cr.savepoint():
            pay.action_post()
        check(False, 'Diario con «Exigir número de operación» bloquea sin n.º', 'se publicó sin número')
    except Exception as exc:  # noqa: BLE001
        check('operación' in str(exc), 'Diario con «Exigir número de operación» bloquea sin n.º', str(exc)[:90])
    pay.bank_operation_number = 'OP-QA20-0001'
    igual(pay.payment_reference, 'OP-QA20-0001', 'escribir bank_operation_number llena payment_reference')
    pay.payment_reference = 'OP-QA20-0002'
    igual(pay.bank_operation_number, 'OP-QA20-0002', 'escribir payment_reference se refleja en bank_operation_number')
    pay.action_post()
    registro(pay, 'pago con n.º de operación')
    check(pay.state != 'draft', 'pago publicado con n.º de operación', pay.state)
    env.cr.execute('SELECT payment_reference FROM account_payment WHERE id=%s', [pay.id])
    igual(env.cr.fetchone()[0], 'OP-QA20-0002', 'el n.º se guarda en la columna nativa payment_reference')
    check('bank_operation_number' not in [c for c in env['account.payment']._fields if env['account.payment']._fields[c].store and c == 'bank_operation_number'],
          'bank_operation_number no es columna propia (no store)')
    igual(pay.pe_payment_method_id.code, '003', 'medio de pago SUNAT en el pago')
    found = env['account.payment'].search([('bank_operation_number', '=', 'OP-QA20-0002')])
    check(pay in found, 'búsqueda por n.º de operación funciona sobre el related')


ejecutar(_p1_ap_related)

caso('al_account_payments', 'Asistente de registro traslada medio y n.º de operación (agrupado)',
     'Factura de cliente → Registrar pago (2 facturas, agrupar): medio 001, n.º LOTE; Crear pago.')


def _p1_ap_wizard():
    bank = _p1_journal('Q1BK', 'P1 Banco soles', 'bank', _p1_OUT)
    partner = registro(_p1_partner('P1 Cliente registro SAC'))
    invs = _p1_doc('out_invoice', partner, 300.0) | _p1_doc('out_invoice', partner, 700.0)
    registro(invs, 'facturas de venta')
    dep = env.ref('al_account_payments.pe_catalog_payment_001')
    wiz = env['account.payment.register'].with_context(active_model='account.move', active_ids=invs.ids).create({
        'journal_id': bank.id, 'pe_payment_method_id': dep.id, 'bank_operation_number': 'LOTE-QA20-01',
        'payment_date': _p1_date(2026, 10, 21), 'group_payment': True})
    pays = registro(wiz._create_payments(), 'pago agrupado')
    igual(len(pays), 1, 'un solo pago agrupado')
    igual(pays.amount, 1000.0, 'importe del pago')
    igual(pays.bank_operation_number, 'LOTE-QA20-01', 'n.º de operación trasladado')
    igual(pays.payment_reference, 'LOTE-QA20-01', 'payment_reference nativo poblado por el asistente')
    igual(pays.pe_payment_method_id, dep, 'medio de pago trasladado')
    check(all(i.payment_state in ('paid', 'in_payment') for i in invs), 'facturas pagadas',
          str(invs.mapped('payment_state')))


ejecutar(_p1_ap_wizard)

caso('al_account_payments', 'Compra de dólares al T.C. del banco (asistente de cambio)',
     'Contabilidad → Bancos → Compra/venta de moneda: de Banco soles a Banco dólares, S/ 3 800 a 3,80; Confirmar.')


def _p1_ap_exchange():
    day = _p1_date(2026, 10, 22)
    sys_rate = _p1_rate(day, 3.75)
    bank_pen = _p1_journal('Q1BK', 'P1 Banco soles', 'bank', _p1_OUT)
    bank_usd = registro(_p1_journal('Q1BKU', 'P1 Banco dólares', 'bank', _p1_OUT, currency_id=_p1_USD.id))
    wiz = env['l10n_pe.currency.exchange.wizard'].create({
        'journal_from_id': bank_pen.id, 'journal_to_id': bank_usd.id, 'date': day,
        'amount_from': 3800.0, 'bank_rate': 3.80, 'bank_operation_number': 'CAMB-QA20-1'})
    igual(wiz.amount_to, 1000.0, 'US$ recibidos = 3 800 / 3,80')
    igual(wiz.system_rate, sys_rate, 'T.C. del sistema', 4)
    expected_diff = round(1000.0 * sys_rate - 3800.0, 2)
    igual(wiz.difference, expected_diff, 'diferencia frente al T.C. del sistema')
    action = wiz.action_confirm()
    pays = registro(env['account.payment'].browse(action['domain'][0][2]), 'pagos de la compra de moneda')
    igual(sorted(pays.mapped('payment_type')), ['inbound', 'outbound'], 'salida en soles y entrada en dólares')
    igual(set(pays.mapped('bank_operation_number')), {'CAMB-QA20-1'}, 'n.º de operación en ambos pagos')
    transfer = company.transfer_account_id
    lines = env['account.move.line'].search([('account_id', '=', transfer.id),
                                             ('move_id', 'in', pays.move_id.ids)])
    check(lines and all(lines.mapped('reconciled')), 'cuenta de transferencias conciliada', transfer.code)
    if expected_diff:
        acc = company.expense_currency_exchange_account_id if expected_diff < 0 else company.income_currency_exchange_account_id
        diff = env['account.move.line'].search([('account_id', '=', acc.id), ('date', '=', day),
                                                ('balance', '=', -expected_diff), ('company_id', '=', company.id)])
        check(diff, 'asiento de diferencia de cambio en %s por %s' % (acc.code, abs(expected_diff)))
        registro(diff.move_id, 'asiento de diferencia de cambio')


ejecutar(_p1_ap_exchange)

# ======================================================================
#  al_l10n_pe_payment_multi
# ======================================================================
caso('al_l10n_pe_payment_multi', 'Un pago para facturas de dos proveedores + anticipo + comisión',
     'Contabilidad → Proveedores → Pago múltiple → Nuevo: cargar facturas de 2 proveedores, '
     'línea de anticipo y de comisión; Validar.')


def _p1_multi():
    bank = _p1_journal('Q1PM', 'P1 Banco pago múltiple', 'bank', _p1_OUT, l10n_pe_receipt_enabled=True)
    sa, sb = _p1_partner('P1 Proveedor Uno SAC'), _p1_partner('P1 Proveedor Dos SAC')
    registro(sa | sb)
    bill_a = _p1_doc('in_invoice', sa, 1000.0)
    bill_b = _p1_doc('in_invoice', sb, 500.0)
    registro(bill_a | bill_b, 'facturas de proveedor')
    expense = _p1_account('6391P1', 'P1 Gastos bancarios', 'expense', False)
    acc_422 = company.root_id.l10n_pe_advance_supplier_account_id
    multi = env['l10n_pe.payment.multi'].create({
        'payment_type': 'outbound', 'journal_id': bank.id, 'date': _p1_date(2026, 10, 20),
        'partner_ids': [Command.set((sa | sb).ids)]})
    multi.action_load_documents()
    igual(multi.line_ids.move_id, bill_a | bill_b, 'carga las facturas abiertas de ambos proveedores')
    multi.line_ids = [
        Command.create({'line_type': 'advance', 'partner_id': sb.id, 'amount': 250.0}),
        Command.create({'line_type': 'other', 'name': 'Comisión bancaria QA20', 'account_id': expense.id,
                        'amount': 15.0})]
    igual(multi.amount_total, 1765.0, 'total = 1000 + 500 + 250 + 15')
    igual(multi.partner_count, 2, 'dos socios')
    multi.action_post()
    registro(multi, 'pago múltiple')
    pay = registro(multi.payment_id, 'pago generado')
    igual(multi.state, 'posted', 'pago múltiple validado')
    igual(pay.amount, 1765.0, 'importe del pago')
    check(not pay.partner_id, 'varios socios: el pago no lleva socio')
    check(bill_a.payment_state in ('paid', 'in_payment') and bill_b.payment_state in ('paid', 'in_payment'),
          'facturas pagadas', str((bill_a.payment_state, bill_b.payment_state)))
    lines = multi.move_id.line_ids
    adv = lines.filtered(lambda l: l.account_id == acc_422)
    igual(adv.balance, 250.0, 'anticipo al debe en 422 (%s)' % acc_422.code)
    igual(adv.partner_id, sb, 'anticipo con el socio')
    igual(lines.filtered(lambda l: l.account_id == expense).balance, 15.0, 'comisión al gasto')
    check((multi.receipt_number or '').startswith('RE-Q1PM-'), 'comprobante de egreso numerado', multi.receipt_number)
    html, _t = env['ir.actions.report']._render_qweb_html(
        'al_l10n_pe_payment_receipt.report_payment_receipt_pe', pay.ids)
    html = html.decode()
    check('Varios (ver detalle)' in html and sb.name in html, 'comprobante PDF lista a cada socio')
    multi.action_cancel()
    check(pay.state == 'canceled' and bill_a.amount_residual == 1000.0, 'anular reabre las facturas',
          str((pay.state, bill_a.amount_residual)))
    multi.action_draft()
    multi.action_post()
    check(multi.payment_id != pay and multi.state == 'posted', 'revalidar crea un pago nuevo')
    registro(multi.payment_id, 'pago tras revalidar')


ejecutar(_p1_multi)

caso('al_l10n_pe_payment_multi', 'Factura en US$ pagada desde banco en soles: diferencia de cambio',
     'Pago múltiple desde banco en soles con factura en dólares; Validar.')


def _p1_multi_usd():
    d1, d2 = _p1_date(2026, 10, 6), _p1_date(2026, 10, 19)
    r1, r2 = _p1_rate(d1, 3.70), _p1_rate(d2, 3.80)
    bank = _p1_journal('Q1PM', 'P1 Banco pago múltiple', 'bank', _p1_OUT, l10n_pe_receipt_enabled=True)
    sup = registro(_p1_partner('P1 Proveedor dólares SAC'))
    bill = registro(_p1_doc('in_invoice', sup, 100.0, currency=_p1_USD, day=d1), 'factura US$')
    multi = env['l10n_pe.payment.multi'].create({
        'payment_type': 'outbound', 'journal_id': bank.id, 'date': d2,
        'line_ids': [Command.create({'line_type': 'document', 'move_line_id': _p1_open_line(bill).id})]})
    igual(multi.line_ids.amount, 100.0, 'US$ 100 a pagar')
    igual(multi.amount_total, round(100 * r2, 2), 'en soles al T.C. del pago')
    multi.action_post()
    registro(multi, 'pago múltiple en soles')
    exch = bill.line_ids.matched_debit_ids.exchange_move_id | bill.line_ids.matched_credit_ids.exchange_move_id
    igual(round(sum(abs(l.balance) for l in exch.line_ids) / 2, 2), round(abs(100 * (r2 - r1)), 2),
          'diferencia de cambio registrada')
    registro(exch, 'asiento de diferencia de cambio')


ejecutar(_p1_multi_usd)

# ======================================================================
#  al_l10n_pe_payment_application
# ======================================================================
caso('al_l10n_pe_payment_application', 'Anticipo de proveedor (422) aplicado a factura y reversión',
     'Pago a proveedor marcado «Anticipo»; desde la factura → Aplicar anticipos → Distribuir → Validar; luego Anular.')


def _p1_application():
    bank = _p1_journal('Q1AN', 'P1 Banco anticipos', 'bank', _p1_OUT)
    partner = registro(_p1_partner('P1 Socio anticipos SAC', vat='20557912879', country_id=_p1_PE.id))
    acc_422 = company.root_id.l10n_pe_advance_supplier_account_id
    adv = env['account.payment'].create({
        'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id, 'amount': 1000.0,
        'journal_id': bank.id, 'date': _p1_date(2026, 10, 1), 'l10n_pe_is_advance': True})
    adv.action_post()
    registro(adv, 'anticipo a proveedor')
    igual(adv.destination_account_id, acc_422, 'el anticipo va a la 422 (%s)' % acc_422.code)
    bill = registro(_p1_doc('in_invoice', partner, 600.0), 'factura de proveedor')
    igual(bill.l10n_pe_advance_count, 1, 'la factura ve 1 anticipo pendiente')
    action = bill.action_l10n_pe_apply_advances()
    app = env['l10n_pe.payment.application'].browse(action['res_id'])
    app.date = _p1_date(2026, 10, 20)
    app.action_distribute()
    app.action_post()
    registro(app, 'aplicación de anticipo')
    igual(app.state, 'posted', 'aplicación validada')
    igual(app.move_id.journal_id, company.root_id.l10n_pe_application_journal_id, 'asiento en el diario de aplicaciones')
    check(bill.payment_state in ('paid', 'in_payment'), 'factura cancelada con el anticipo', bill.payment_state)
    adv_line = adv.move_id.line_ids.filtered(lambda l: l.account_id == acc_422)
    igual(abs(adv_line.amount_residual), 400.0, 'saldo del anticipo por aplicar')
    app.action_cancel()
    igual(app.state, 'cancel', 'aplicación anulada')
    check(app.reversal_move_id, 'asiento de reversión creado')
    igual(bill.amount_residual, 600.0, 'la factura vuelve a quedar pendiente')
    # Compensación cuenta por cobrar / por pagar
    inv = registro(_p1_doc('out_invoice', partner, 500.0), 'factura de venta a compensar')
    net = env['l10n_pe.payment.application'].create({
        'partner_id': partner.id, 'application_type': 'netting', 'date': _p1_date(2026, 10, 21)})
    net.action_load_documents()
    check({inv, bill} <= set(net.line_ids.move_id), 'compensación carga cobrar y pagar del socio')
    net.line_ids.filtered(lambda l: l.move_id not in (inv | bill)).unlink()
    net.action_distribute()
    net.action_post()
    registro(net, 'compensación')
    igual(bill.amount_residual, 100.0, 'factura de compra compensada por 500')
    check(inv.payment_state in ('paid', 'in_payment'), 'factura de venta cancelada por compensación', inv.payment_state)


ejecutar(_p1_application)

# ======================================================================
#  al_l10n_pe_payment_receipt
# ======================================================================
caso('al_l10n_pe_payment_receipt', 'Comprobante de ingreso/egreso numerado por diario y PDF',
     'Caja con «Comprobante de pago» → Registrar pago parcial de una factura → Imprimir comprobante.')


def _p1_receipt():
    # No se toca res.company (bloquearía a las otras fases): el PDF se renderiza directo.
    cash = registro(_p1_journal('Q1CJ', 'P1 Caja recibos', 'cash', l10n_pe_receipt_enabled=True), 'caja con comprobante')
    igual(cash.l10n_pe_receipt_in_sequence_id.prefix, 'RI-Q1CJ-', 'secuencia de ingresos por diario')
    igual(cash.l10n_pe_receipt_out_sequence_id.prefix, 'RE-Q1CJ-', 'secuencia de egresos por diario')
    partner = registro(_p1_partner('P1 Cliente recibo SAC', vat='20557912879', country_id=_p1_PE.id))
    inv = registro(_p1_doc('out_invoice', partner, 300.0), 'factura de venta')
    wiz = env['account.payment.register'].with_context(active_model='account.move', active_ids=inv.ids).create({
        'journal_id': cash.id, 'amount': 118.5, 'payment_date': _p1_date(2026, 10, 23)})
    pay = registro(wiz._create_payments(), 'cobro parcial')
    check((pay.l10n_pe_receipt_number or '').startswith('RI-Q1CJ-'), 'n.º de recibo de ingreso', pay.l10n_pe_receipt_number)
    docs = pay._l10n_pe_receipt_documents()
    check(len(docs) == 1 and docs[0]['move'] == inv, 'el comprobante detalla la factura aplicada')
    igual(docs[0]['applied'], 118.5, 'aplicado')
    igual(docs[0]['residual'], 181.5, 'saldo de la factura')
    igual(pay._l10n_pe_receipt_amount_words(), 'CIENTO DIECIOCHO Y 50/100 SOLES', 'importe en letras')
    html, _t = env['ir.actions.report']._render_qweb_html(
        'al_l10n_pe_payment_receipt.report_payment_receipt_pe', pay.ids)
    html = html.decode()
    check(pay.l10n_pe_receipt_number in html and 'CIENTO DIECIOCHO' in html and inv.name in html,
          'PDF con número, importe en letras y factura')
    number = pay.l10n_pe_receipt_number
    pay.action_draft()
    pay.action_post()
    igual(pay.l10n_pe_receipt_number, number, 'el número se conserva al volver a borrador')
    out = env['account.payment'].create({'payment_type': 'outbound', 'partner_type': 'supplier',
                                         'partner_id': partner.id, 'amount': 40.0, 'journal_id': cash.id,
                                         'date': _p1_date(2026, 10, 23)})
    out.action_post()
    registro(out, 'egreso de caja')
    check((out.l10n_pe_receipt_number or '').startswith('RE-Q1CJ-'), 'n.º de recibo de egreso', out.l10n_pe_receipt_number)
    act = out.action_l10n_pe_receipt_print()
    check(act.get('type') in ('ir.actions.report', 'ir.actions.act_window'), 'acción Imprimir comprobante',
          '%s%s' % (act.get('type'), '' if company.external_report_layout_id else ' (sin diseño: Odoo abre antes el asistente de diseño)'))


ejecutar(_p1_receipt)

# ======================================================================
#  al_l10n_pe_payment_term_currency
# ======================================================================
caso('al_l10n_pe_payment_term_currency', 'Cuota fija en soles en factura en dólares',
     'Configuración → Términos de pago: cuota fija S/ 750 «Importe en soles» + saldo a 30 días; '
     'factura en US$ 1 000 con ese término; Confirmar.')


def _p1_term():
    day = _p1_date(2026, 10, 7)
    r = _p1_rate(day, 3.75)
    term = env['account.payment.term'].create({
        'name': qa_name('P1 S/ 750 a la firma y saldo 30 días'),
        'line_ids': [Command.create({'value': 'fixed', 'value_amount': 750.0, 'nb_days': 0,
                                     'l10n_pe_company_currency': True}),
                     Command.create({'value': 'percent', 'value_amount': 100, 'nb_days': 30})]})
    registro(term, 'término de pago')
    partner = registro(_p1_partner('P1 Cliente cuotas SAC'))
    inv = registro(_p1_doc('out_invoice', partner, 1000.0, currency=_p1_USD, day=day,
                           invoice_payment_term_id=term.id), 'factura US$ 1 000')
    inst = [(l.amount_currency, l.balance) for l in
            inv.line_ids.filtered(lambda l: l.display_type == 'payment_term').sorted('date_maturity')]
    usd1 = round(750.0 / r, 2)
    igual(inst[0][1], 750.0, 'primera cuota = S/ 750 exactos')
    igual(inst[0][0], usd1, 'primera cuota en US$ al T.C. de la factura (%s)' % r)
    igual(inst[0][0] + inst[1][0], 1000.0, 'cuotas en US$ suman el total')
    igual(inst[0][1] + inst[1][1], round(1000.0 * r, 2), 'cuotas en S/ suman el total')
    inv_pen = registro(_p1_doc('out_invoice', partner, 1000.0, day=day, invoice_payment_term_id=term.id),
                       'factura en soles (sin cambio)')
    inst = [l.balance for l in inv_pen.line_ids.filtered(lambda l: l.display_type == 'payment_term').sorted('date_maturity')]
    igual(inst, [750.0, 250.0], 'en soles el término funciona como el nativo')


ejecutar(_p1_term)

# ======================================================================
#  al_l10n_pe_bank_statement_import
# ======================================================================
caso('al_l10n_pe_bank_statement_import', 'Importar extracto XLSX y CSV de banca por internet (archivos de sus tests)',
     'Contabilidad → Tablero → Banco → Importar archivo: movimientos.xlsx y estado.csv; reimportar no duplica.')


def _p1_stmt():
    from odoo.addons.al_l10n_pe_bank_statement_import.tests.test_statement_parser import (
        DEBIT_CREDIT_CSV, SIGNED_ROWS, xlsx_bytes)
    suspense = _p1_account('1091P1', 'P1 Transitoria extractos', 'asset_current', False)
    journal = registro(_p1_journal('Q1EX', 'P1 Banco extractos', 'bank', suspense_account_id=suspense.id),
                       'diario de extractos')

    def lines():
        return env['account.bank.statement.line'].search([('journal_id', '=', journal.id)], order='date, id')

    att = env['ir.attachment'].create({'name': 'QA20_movimientos.xlsx', 'raw': xlsx_bytes(SIGNED_ROWS)})
    action = journal._import_bank_statement(att)
    check(action.get('tag') != 'import_bank_stmt', 'XLSX reconocido sin mapeo manual de columnas')
    ls = lines()
    igual(ls.mapped('amount'), [-10.5, 2350.5, -1500.0], 'importes en orden cronológico')
    igual(ls[:1].payment_ref, 'COMISION MANTENIMIENTO', 'descripción')
    st = ls.statement_id
    igual(len(st), 1, 'un extracto')
    igual((st.balance_start, st.balance_end_real), (7510.0, 8350.0), 'saldos inicial y final del banco')
    check(st.is_complete, 'extracto completo (saldos cuadran)')
    registro(st, 'extracto XLSX')
    att2 = env['ir.attachment'].create({'name': 'QA20_estado.csv', 'raw': DEBIT_CREDIT_CSV})
    journal._import_bank_statement(att2)
    igual(len(lines()), 6, 'CSV cargo/abono añade 3 movimientos')
    csv_lines = lines().filtered(lambda l: l.date.month == 10 and l.date.day <= 2)
    igual(sorted(csv_lines.mapped('amount')), [-800.0, -0.05, 1250.0], 'importes del CSV (coma decimal)')
    registro(csv_lines.statement_id, 'extracto CSV')
    try:
        with env.cr.savepoint():
            journal._import_bank_statement(env['ir.attachment'].create(
                {'name': 'QA20_estado (1).csv', 'raw': DEBIT_CREDIT_CSV}))
    except Exception:  # noqa: BLE001 - el nativo avisa que no hay movimientos nuevos
        pass
    igual(len(lines()), 6, 'reimportar el mismo archivo no duplica')
    action = journal._import_bank_statement(env['ir.attachment'].create({'name': 'QA20_otro.csv',
                                                                       'raw': b'col1;col2\na;b\n'}))
    igual(action.get('tag'), 'import_bank_stmt', 'CSV no reconocido pasa al importador nativo')


ejecutar(_p1_stmt)

# ======================================================================
#  al_l10n_pe_batch_payment
# ======================================================================
_p1_TXT = {}


def _p1_bank_setup():
    if _p1_TXT and _p1_TXT['bcp'].exists():
        return _p1_TXT
    Bank = env['l10n_pe.bank']
    bcp = Bank.create({'name': qa_name('P1 BCP'), 'l10n_pe_batch_format': 'bcp'})
    bbva = Bank.create({'name': qa_name('P1 BBVA'), 'l10n_pe_batch_format': 'bbva'})
    ibk = Bank.create({'name': qa_name('P1 Interbank'), 'l10n_pe_batch_format': 'interbank'})
    acc = env['res.partner.bank'].create({
        'partner_id': company.partner_id.id, 'l10n_pe_bank_id': bcp.id,
        'account_number': '191-9912345-0-71', 'currency_id': _p1_PEN.id})
    journal = _p1_journal('Q1BCP', 'P1 BCP soles masivo', 'bank', _p1_OUT, currency_id=_p1_PEN.id,
                          bank_account_id=acc.id)
    sups = []
    for name, vat, bank, number, cci in (
            ('P1 Proveedor TXT Uno', '20100070970', bcp, '193-7654321-0-22', '00219300765432102211'),
            ('P1 Proveedor TXT Dos', '20131312955', bbva, '0011-0456-0200098765', '01145600020009876512'),
            ('P1 Proveedor TXT Tres', '20100047218', ibk, '200-3001234567', '00320000300123456713')):
        partner = _p1_partner(name, is_company=True, vat=vat, country_id=_p1_PE.id)
        pbank = _p1_BANKACC.create({'partner_id': partner.id, 'l10n_pe_bank_id': bank.id,
                                                'account_number': number, 'l10n_pe_cci': cci,
                                                'allow_out_payment': True})
        sups.append((partner, pbank))
    _p1_TXT.update(bcp=bcp, journal=journal, sups=sups)
    return _p1_TXT


caso('al_l10n_pe_batch_payment', 'Lote de pagos a 3 proveedores → TXT del BCP',
     'Proveedores → Pagos: 3 pagos con método «TXT banco» → Crear lote → Validar → Descargar archivo.')


def _p1_batch():
    s = _p1_bank_setup()
    journal = s['journal']
    registro(journal, 'diario BCP con formato')
    line = journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'pe_bank_txt')
    check(line, 'el diario ofrece el método de pago masivo pe_bank_txt')
    pays = env['account.payment']
    for (partner, pbank), amount in zip(s['sups'], (1000.0, 250.5, 80.0)):
        pays |= env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id,
            'partner_bank_id': pbank.id, 'amount': amount, 'journal_id': journal.id,
            'payment_method_line_id': line.id, 'date': _p1_date(2026, 10, 26)})
    pays.action_post()
    registro(pays, 'pagos a proveedores')
    batch = env['account.batch.payment'].create({
        'journal_id': journal.id, 'batch_type': 'outbound',
        'payment_method_id': env.ref('al_l10n_pe_batch_payment.account_payment_method_pe_bank_txt').id,
        'payment_ids': [Command.set(pays.ids)]})
    batch.validate_batch()
    registro(batch, 'lote de pagos')
    check(batch.export_file, 'archivo TXT generado', batch.export_filename)
    rows = batch.export_file.content.decode('latin-1').split('\r\n')[:-1]
    igual(len(rows), 4, 'cabecera + 3 abonos')
    igual(rows[0][:7], '1000003', 'cabecera: tipo 1 y 3 abonos')
    check('00000000001330.50' in rows[0], 'total 1 330,50 en la cabecera', rows[0][:60])
    igual(len(rows[0]), 113, 'longitud de cabecera BCP proveedores')
    check(rows[1].startswith('2C1937654321022'), 'mismo banco: abono a cuenta BCP', rows[1][:20])
    check(rows[2].startswith('2B01145600020009876512'), 'otro banco: abono por CCI', rows[2][:25])
    igual(len(rows[1]), 196, 'longitud de detalle BCP')
    igual((batch.l10n_pe_export_count, batch.l10n_pe_export_total), (3, 1330.5), 'conteo y total del lote')
    check(batch.export_filename.startswith('BCP_PEN_Q1BCP_'), 'nombre del archivo', batch.export_filename)
    # proveedor sin CCI en otro banco → rechazo (se deshace con savepoint)
    partner, pbank = s['sups'][2]

    class _P1Undo(Exception):
        pass
    msg = []
    try:
        with env.cr.savepoint():
            pbank.l10n_pe_cci = False
            p = env['account.payment'].create({
                'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id,
                'partner_bank_id': pbank.id, 'amount': 10.0, 'journal_id': journal.id,
                'payment_method_line_id': line.id, 'date': _p1_date(2026, 10, 26)})
            p.action_post()
            b2 = env['account.batch.payment'].create({
                'journal_id': journal.id, 'batch_type': 'outbound', 'payment_method_id': line.payment_method_id.id,
                'payment_ids': [Command.set(p.ids)]})
            try:
                b2.validate_batch()
                msg.append(None)
            except Exception as exc:  # noqa: BLE001
                msg.append('%s: %s' % (type(exc).__name__, exc))
            raise _P1Undo()
    except _P1Undo:
        pass
    check(msg and msg[0], 'proveedor de otro banco sin CCI se rechaza', (msg[0] or 'se generó el archivo')[:100])


def _p1_batch_wrap():
    _p1_batch()


ejecutar(_p1_batch_wrap)

# ======================================================================
#  al_l10n_pe_treasury
# ======================================================================
_p1_TR = {}


def _p1_tr_setup():
    if _p1_TR and _p1_TR['pen'].exists():
        return _p1_TR
    out_in = _p1_account('1049P12', 'P1 Cobros pendientes tesorería')
    out_out = _p1_account('1049P13', 'P1 Pagos pendientes tesorería')
    js = {}
    for key, code, name, cur in (('pen', 'Q1TP', 'P1 Tesorería soles', False),
                                 ('pen2', 'Q1TB', 'P1 Tesorería soles 2', False),
                                 ('usd', 'Q1TU', 'P1 Tesorería dólares', _p1_USD.id)):
        j = _p1_journal(code, name, 'bank', currency_id=cur)
        j.inbound_payment_method_line_ids.payment_account_id = out_in
        j.outbound_payment_method_line_ids.payment_account_id = out_out
        js[key] = j
    _p1_TR.update(js)
    return _p1_TR


def _p1_opening(account, amount, day, currency=None, amount_currency=None):
    Account = env['account.account']
    equity = Account.search([*Account._check_company_domain(company), ('account_type', '=', 'equity')], limit=1)
    misc = env['account.journal'].search([('company_id', '=', company.id), ('code', '=', 'MISC')], limit=1)
    currency = currency or _p1_PEN
    amount_currency = amount if amount_currency is None else amount_currency
    move = env['account.move'].create({
        'move_type': 'entry', 'journal_id': misc.id, 'date': day, 'ref': qa_name('P1 saldo inicial'),
        'line_ids': [
            Command.create({'name': 'Saldo inicial QA20', 'account_id': account.id, 'balance': amount,
                            'currency_id': currency.id, 'amount_currency': amount_currency}),
            Command.create({'name': 'Saldo inicial QA20', 'account_id': equity.id, 'balance': -amount,
                            'currency_id': currency.id, 'amount_currency': -amount_currency})]})
    move.action_post()
    return move


caso('al_l10n_pe_treasury', 'Posición diaria: saldo contable, en tránsito y disponible',
     'Tesorería → Posición diaria → Nuevo (fecha, banco); revisar saldo, tránsito y disponible.')


def _p1_position():
    t = _p1_tr_setup()
    bank = t['pen']
    registro(_p1_opening(bank.default_account_id, 10000.0, _p1_date(2026, 10, 1)), 'saldo inicial del banco')
    bank.write({'l10n_pe_treasury_min_balance': 500.0, 'l10n_pe_treasury_overdraft': 2000.0})
    vendor = registro(_p1_partner('P1 Proveedor tesorería SAC', vat='20100070970'))
    pay = env['account.payment'].create({
        'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': vendor.id,
        'journal_id': bank.id, 'amount': 1500.0, 'date': _p1_date(2026, 10, 10)})
    pay.action_post()
    registro(pay, 'pago en tránsito')
    pos = env['l10n_pe.treasury.position'].create({'date': _p1_date(2026, 10, 16),
                                                   'journal_ids': [Command.set(bank.ids)]})
    registro(pos, 'posición de tesorería')
    line = pos.line_ids
    igual(line.balance, 10000.0, 'saldo contable')
    igual(line.payments_transit, -1500.0, 'pago confirmado sin conciliar en tránsito')
    igual(line.projected, 8500.0, 'saldo proyectado')
    igual(line.available, 8500.0 - 500.0 + 2000.0, 'disponible = proyectado − mínimo + sobregiro')


ejecutar(_p1_position)

caso('al_l10n_pe_treasury', 'Transferencia entre bancos y compra de US$ a T.C. oficial (pérdida)',
     'Tesorería → Transferencias → Nuevo: de soles a soles S/ 5 000; otra de soles a dólares a 3,75 valorizada oficial; Confirmar.')


def _p1_transfer():
    t = _p1_tr_setup()
    day = _p1_date(2026, 10, 16)
    r = _p1_rate(day, 3.70)
    T = env['l10n_pe.treasury.transfer']
    tr = T.create({'journal_from_id': t['pen'].id, 'journal_to_id': t['pen2'].id, 'amount': 5000.0, 'date': day})
    check(not tr.is_exchange, 'misma moneda: no es cambio')
    tr.action_confirm()
    registro(tr, 'transferencia soles→soles')
    igual(tr.state, 'done', 'transferencia realizada (sin umbral de aprobación)')
    igual(tr.payment_from_id.destination_account_id, company.transfer_account_id, 'por la cuenta de transferencias')
    check(all(tr._l10n_pe_transfer_lines().mapped('reconciled')), 'cuenta de transferencias conciliada')
    fx = T.create({'journal_from_id': t['pen'].id, 'journal_to_id': t['usd'].id, 'amount': 3750.0,
                   'agreed_rate': 3.75, 'valuation': 'official', 'date': day})
    igual(fx.exchange_type, 'buy', 'compra de dólares')
    igual(fx.amount_to, 1000.0, 'US$ recibidos')
    fx.action_confirm()
    registro(fx, 'compra de US$')
    expected = round(1000.0 * r - 3750.0, 2)
    igual(fx.exchange_difference, expected, 'diferencia de cambio (T.C. oficial %s)' % r)
    if expected:
        check(fx.exchange_move_id, 'asiento de diferencia de cambio')
        registro(fx.exchange_move_id, 'asiento diferencia de cambio')
    igual(company.currency_id.round(sum(fx._l10n_pe_transfer_lines().mapped('balance'))), 0.0,
          'cuenta de transferencias saldada')


ejecutar(_p1_transfer)

caso('al_l10n_pe_treasury', 'Programación de pagos: proponer, aprobar y pagar',
     'Tesorería → Programación de pagos → Nuevo → Proponer (vence al 31/10, proveedores) → Enviar → Aprobar → Pagar.')


def _p1_plan():
    t = _p1_tr_setup()
    v1 = _p1_partner('P1 Proveedor plan Uno', vat='20100070970')
    v2 = _p1_partner('P1 Proveedor plan Dos', vat='20100047218')
    registro(v1 | v2)
    b1 = _p1_doc('in_invoice', v1, 1000.0, day=_p1_date(2026, 10, 1), invoice_date_due=_p1_date(2026, 10, 10))
    b2 = _p1_doc('in_invoice', v1, 400.0, day=_p1_date(2026, 10, 1), invoice_date_due=_p1_date(2026, 10, 20))
    b3 = _p1_doc('in_invoice', v2, 700.0, day=_p1_date(2026, 10, 1), invoice_date_due=_p1_date(2026, 10, 12))
    blater = _p1_doc('in_invoice', v2, 900.0, day=_p1_date(2026, 10, 1), invoice_date_due=_p1_date(2026, 12, 30))
    registro(b1 | b2 | b3 | blater, 'facturas de proveedor')
    admin = env.ref('base.user_admin')
    plan = env['l10n_pe.treasury.payment.plan'].with_user(admin).create(
        {'journal_id': t['pen'].id, 'date': _p1_date(2026, 10, 16)})
    env['l10n_pe.treasury.payment.plan.propose'].with_user(admin).create({
        'plan_id': plan.id, 'date_due': _p1_date(2026, 10, 31),
        'partner_ids': [Command.set((v1 | v2).ids)]}).action_propose()
    plan = plan.with_env(env)
    registro(plan, 'programación de pagos')
    igual(plan.line_ids.move_id, b1 | b2 | b3, 'propone lo vencido al 31/10, no la de diciembre')
    igual(plan.amount_total, 2100.0, 'total programado')
    igual(plan.partner_count, 2, 'dos proveedores')
    igual(plan.line_ids.filtered(lambda l: l.move_id == b1).days_overdue, 6, 'días de atraso al 16/10')
    plan.action_submit()
    igual(plan.state, 'to_approve', 'sin umbral configurado requiere aprobación')
    try:
        with env.cr.savepoint():
            plan.with_user(admin).action_approve()
        check(False, 'quien prepara no puede aprobar', 'se aprobó')
    except Exception as exc:  # noqa: BLE001
        check('prepara' in str(exc), 'quien prepara no puede aprobar', str(exc)[:80])
    plan.action_approve()  # superusuario (aprobador)
    igual(plan.state, 'approved', 'aprobada')
    pos = env['l10n_pe.treasury.position'].create({'date': _p1_date(2026, 10, 16),
                                                   'journal_ids': [Command.set(t['pen'].ids)]})
    igual(pos.line_ids.scheduled, 2100.0, 'la posición refleja lo programado aprobado')
    plan.action_pay()
    igual(plan.state, 'paid', 'programación pagada')
    igual(len(plan.payment_ids), 2, 'un pago por proveedor')
    registro(plan.payment_ids, 'pagos de la programación')
    check(all(b.payment_state in ('paid', 'in_payment') for b in b1 | b2 | b3), 'facturas pagadas')


ejecutar(_p1_plan)

# ======================================================================
#  al_l10n_pe_treasury_batch_payment
# ======================================================================
caso('al_l10n_pe_treasury_batch_payment', 'Programación pagada con método TXT genera lote y archivo del banco',
     'Programación de pagos en banco BCP con método «TXT banco» → Pagar → Abrir lote → Validar → Descargar TXT.')


def _p1_plan_batch():
    s = _p1_bank_setup()
    journal = s['journal']
    line = journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'pe_bank_txt')
    partners = env['res.partner']
    bills = env['account.move']
    for name, vat, number, amount in (('P1 Proveedor lote Uno', '20100070970', '193-1111111-0-11', 800.0),
                                      ('P1 Proveedor lote Dos', '20131312955', '193-2222222-0-22', 450.0)):
        partner = _p1_partner(name, is_company=True, vat=vat, country_id=_p1_PE.id)
        _p1_BANKACC.create({'partner_id': partner.id, 'l10n_pe_bank_id': s['bcp'].id,
                                        'account_number': number, 'allow_out_payment': True})
        partners |= partner
        bills |= _p1_doc('in_invoice', partner, amount, day=_p1_date(2026, 10, 1),
                         invoice_date_due=_p1_date(2026, 10, 15))
    registro(partners)
    registro(bills, 'facturas de proveedor')
    plan = env['l10n_pe.treasury.payment.plan'].create({
        'journal_id': journal.id, 'date': _p1_date(2026, 10, 27), 'payment_method_line_id': line.id})
    env['l10n_pe.treasury.payment.plan.propose'].create({
        'plan_id': plan.id, 'date_due': _p1_date(2026, 10, 31),
        'partner_ids': [Command.set(partners.ids)]}).action_propose()
    igual(plan.line_ids.move_id, bills, 'propone las dos facturas')
    plan.action_submit()
    if plan.state == 'to_approve':
        plan.action_approve()
    plan.action_pay()
    registro(plan, 'programación con método TXT')
    batch = plan.batch_payment_id
    check(batch, 'se creó el lote bancario')
    igual(batch.payment_ids, plan.payment_ids, 'el lote contiene los pagos de la programación')
    igual(plan.payment_ids.payment_method_line_id, line, 'pagos con el método TXT')
    batch.validate_batch()
    registro(batch, 'lote bancario')
    rows = batch.export_file.content.decode('latin-1').split('\r\n')[:-1] if batch.export_file else []
    check(rows and rows[0][:7] == '1000002', 'TXT BCP con cabecera de 2 abonos', str(rows[:1]))
    check(rows and '00000000001250.00' in rows[0], 'total S/ 1 250,00 en el TXT')


ejecutar(_p1_plan_batch)

# ======================================================================= PARTE 2
# -*- coding: utf-8 -*-
# Fase contabilidad_b — parte 2: cobranza bancaria, cobranza, bloqueo de venta,
# cheques, impresión de cheques, letras de cambio y factoring.
from datetime import date as _p2_date, timedelta as _p2_td
from unittest.mock import patch as _p2_patch
import json as _p2_json

from odoo.tools import BinaryBytes as _p2_BinaryBytes

_p2_env = env(context=dict(env.context, tz='America/Lima'))
_p2_today = fields.Date.context_today(_p2_env['res.partner'])
_p2_pen = company.currency_id
_p2_admin = _p2_env.ref('base.user_admin')


def _p2_ruc(base10):
    """RUC válido a partir de 10 dígitos (dígito verificador SUNAT)."""
    weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    total = sum(int(d) * w for d, w in zip(base10, weights))
    dv = 11 - total % 11
    return base10 + str({10: 0, 11: 1}.get(dv, dv))


def _p2_partner(name, base10=None, **vals):
    vals = dict({'name': qa_name('P2 %s' % name), 'country_id': _p2_env.ref('base.pe').id,
                 'email': 'qa20.p2@example.com'}, **vals)
    if base10:
        vals['vat'] = _p2_ruc(base10)
    return _p2_env['res.partner'].create(vals)


def _p2_journal(code, name, jtype, **vals):
    Journal = _p2_env['account.journal']
    journal = Journal.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
    if not journal:
        journal = Journal.create(dict({'name': qa_name('P2 %s' % name), 'code': code, 'type': jtype,
                                       'company_id': company.id}, **vals))
    return journal


def _p2_account(code, name, account_type, reconcile=False):
    Account = _p2_env['account.account'].with_company(company)
    acc = Account.search([('code', '=', code)], limit=1)
    if not acc:
        acc = Account.create({'code': code, 'name': qa_name('P2 %s' % name), 'account_type': account_type,
                              'reconcile': reconcile})
    return acc


_p2_income = _p2_env['account.account'].with_company(company).search([('account_type', '=', 'income')], limit=1)
_p2_sale_journal = _p2_journal('Q2VT', 'Ventas', 'sale', l10n_latam_use_documents=False)
_p2_outstanding = _p2_account('104197', 'Pendientes de banco', 'asset_current', reconcile=True)
_p2_bank = _p2_journal('Q2BK', 'Banco', 'bank')
(_p2_bank.inbound_payment_method_line_ids
 | _p2_bank.outbound_payment_method_line_ids.filtered(lambda l: l.code != 'own_checks')
 ).filtered(lambda l: not l.payment_account_id).payment_account_id = _p2_outstanding


def _p2_invoice(partner, amount, due_in=30, invoice_date=None, journal=None, currency=None):
    due = _p2_today + _p2_td(days=due_in)
    inv_date = invoice_date or min(due, _p2_today) - _p2_td(days=1)
    move = _p2_env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': partner.id,
        'journal_id': (journal or _p2_sale_journal).id,
        'invoice_date': inv_date, 'invoice_date_due': due, 'date': inv_date,
        'currency_id': (currency or _p2_pen).id,
        'invoice_line_ids': [Command.create({'name': qa_name('P2 Venta'), 'quantity': 1, 'price_unit': amount,
                                             'account_id': _p2_income.id, 'tax_ids': [Command.clear()]})],
    })
    move.action_post()
    return move


def _p2_receivable(move):
    return move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')


def _p2_pay(invoice, amount=None, day=None):
    vals = {'journal_id': _p2_bank.id, 'payment_date': day or _p2_today}
    if amount is not None:
        vals['amount'] = amount
    return _p2_env['account.payment.register'].with_context(
        active_model='account.move', active_ids=invoice.ids).create(vals)._create_payments()


def _p2_balance(moves, account, partner=None):
    lines = moves.filtered(lambda m: m.state == 'posted').line_ids.filtered(
        lambda l: l.account_id == account and (not partner or l.partner_id == partner))
    return _p2_pen.round(sum(lines.mapped('balance')))


# ======================================================================
#  al_l10n_pe_check — cheques de terceros y propios
# ======================================================================
_p2_CT = _p2_env['account.chart.template'].with_company(company)
company._l10n_pe_check_setup()  # idempotente: añade «Cheques propios» al banco QA
_p2_portfolio = _p2_CT.ref('l10n_pe_third_party_check')
_p2_rejected = _p2_CT.ref('l10n_pe_rejected_check')


def _p2_receive_check(partner, number, amount, payment_date, date_received=None):
    line = _p2_portfolio.inbound_payment_method_line_ids.filtered(lambda l: l.code == 'new_third_party_checks')
    payment = _p2_env['account.payment'].create({
        'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': partner.id,
        'journal_id': _p2_portfolio.id, 'payment_method_line_id': line.id,
        'date': date_received or payment_date,
        'l10n_latam_new_check_ids': [Command.create({'name': number, 'payment_date': payment_date,
                                                     'amount': amount})],
    })
    payment.action_post()
    return payment


def _p2_own_check(partner, number, amount, payment_date, journal=None):
    journal = journal or _p2_bank
    line = journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')[:1]
    payment = _p2_env['account.payment'].create({
        'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id,
        'journal_id': journal.id, 'payment_method_line_id': line.id, 'date': _p2_date(2026, 10, 21),
        'amount': amount,
        'l10n_latam_new_check_ids': [Command.create({'name': number, 'payment_date': payment_date,
                                                     'amount': amount})],
    })
    payment.action_post()
    return payment


caso('al_l10n_pe_check', 'Cheque de terceros: recepción en cartera, aviso de plazo y depósito',
     'Contabilidad → Clientes → Pagos: nuevo cobro en «Cheques de terceros» con método «Nuevos cheques '
     'de terceros»; luego Cheques → seleccionar → Transferir al banco.')


def _p2_check_third_party():
    customer = registro(_p2_partner('Cliente cheques', '2061209031'), 'girador del cheque')
    payment = registro(_p2_receive_check(customer, '00912345', 1180.0, _p2_date(2026, 10, 20)), 'cobro con cheque')
    chk = registro(payment.l10n_latam_new_check_ids, 'cheque en cartera')
    igual(chk.current_journal_id.code, _p2_portfolio.code, 'el cheque queda en el diario de cartera')
    igual(chk.issuer_vat, customer.vat, 'RUC del girador tomado del cliente')
    line = payment.move_id.line_ids.filtered(lambda l: l.account_id.code == '1033001')
    igual(sum(line.mapped('debit')), 1180.0, 'débito en 1033001 Cheques de terceros en cartera')
    igual(chk.l10n_pe_presentation_deadline, _p2_date(2026, 11, 19), 'plazo de presentación = 30 días')
    # Cheque vencido (más de 30 días): el asistente de depósito avisa.
    old = _p2_receive_check(customer, '00912346', 500.0, _p2_date(2026, 9, 10)).l10n_latam_new_check_ids
    registro(old, 'cheque vencido')
    wizard = _p2_env['l10n_latam.payment.mass.transfer'].with_context(
        active_model='l10n_latam.check', active_ids=(chk | old).ids).create(
        {'to_journal_id': _p2_bank.id, 'payment_date': _p2_today})
    check(wizard.l10n_pe_warning and old.name in wizard.l10n_pe_warning and 'venció' in wizard.l10n_pe_warning
          and chk.name not in wizard.l10n_pe_warning, 'aviso de plazo vencido solo para el cheque viejo',
          wizard.l10n_pe_warning)
    _p2_env['l10n_latam.payment.mass.transfer'].with_context(
        active_model='l10n_latam.check', active_ids=chk.ids).create(
        {'to_journal_id': _p2_bank.id, 'payment_date': _p2_today})._create_payments()
    igual(chk.current_journal_id, _p2_bank, 'depositado: el cheque pasa al banco')
    igual(len(chk.operation_ids), 2, 'operaciones del cheque: recepción + depósito')
    try:
        with env.cr.savepoint():
            chk.issuer_vat = '20100070971'
        check(False, 'RUC de girador inválido debe rechazarse')
    except Exception as exc:  # noqa: BLE001
        check('Validation' in type(exc).__name__, 'RUC de girador inválido rechazado', str(exc)[:120])


ejecutar(_p2_check_third_party)

caso('al_l10n_pe_check', 'Cheque propio girado a proveedor',
     'Contabilidad → Proveedores → Pagos: nuevo pago desde el banco con método «Cheques propios».')


def _p2_check_own():
    supplier = registro(_p2_partner('Proveedor cheques', '2061209032'), 'proveedor')
    own_line = _p2_bank.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')
    check(own_line, 'el banco QA tiene el método «Cheques propios»', own_line.mapped('name'))
    igual(own_line[:1].payment_account_id.code, '1049001', 'cuenta de cheques girados 1049001')
    payment = registro(_p2_own_check(supplier, '00001021', 2360.0, _p2_date(2026, 10, 25)), 'pago con cheque propio')
    chk = registro(payment.l10n_latam_new_check_ids, 'cheque propio')
    igual(chk.issue_state, 'handed', 'cheque entregado')
    igual(chk.outstanding_line_id.account_id.code, '1049001', 'pendiente en 1049001 hasta el cobro')


ejecutar(_p2_check_own)

# ======================================================================
#  al_l10n_pe_check_printing
# ======================================================================
caso('al_l10n_pe_check_printing', 'Formato de chequera e impresión del cheque propio',
     'Contabilidad → Configuración → Formatos de cheque: crear formato, asignarlo al banco; '
     'en el pago con cheque propio → Imprimir cheque.')


def _p2_check_printing():
    from odoo.addons.al_l10n_pe_check_printing.models.check_layout import amount_in_words
    layout = registro(_p2_env['l10n_pe.check.layout'].create({
        'name': qa_name('P2 Chequera'), 'paper_width': 170, 'paper_height': 75, 'city': 'Lima'}), 'formato')
    _p2_bank.l10n_pe_check_layout_id = layout
    pf = layout.paperformat_id
    igual((pf.format, pf.page_width, pf.page_height), ('custom', 170, 75), 'formato de papel = tamaño de la chequera')
    igual(amount_in_words(1250.0, _p2_pen), 'MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES', 'importe en letras')
    igual(layout._l10n_pe_format_amount(1250.0, _p2_pen), 'S/ ******1,250.00', 'importe con relleno')
    supplier = registro(_p2_partner('PROVEEDOR IMPRESION', '2061209033'), 'beneficiario')
    supplier.name = 'QA20 P2 PROVEEDOR IMPRESION SAC'
    payment = registro(_p2_own_check(supplier, '00004521', 1250.0, _p2_date(2026, 11, 20)), 'cheque diferido')
    action = payment.action_l10n_pe_print_checks()
    igual(action.get('report_name'), 'al_l10n_pe_check_printing.report_check', 'acción de impresión')
    html, _t = _p2_env['ir.actions.report']._render_qweb_html(
        'al_l10n_pe_check_printing.report_check', payment.l10n_latam_new_check_ids.ids)
    html = html.decode()
    for text in ('QA20 P2 PROVEEDOR IMPRESION SAC', 'S/ ******1,250.00',
                 'MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES', 'Lima, 21 de octubre de 2026',
                 'Pagar desde: 20 de noviembre de 2026'):
        check(text in html, 'el cheque impreso contiene «%s»' % text)
    test = layout.action_print_test()
    html_test = _p2_env['ir.actions.report']._render_qweb_html(
        'al_l10n_pe_check_printing.report_check', [], data=test['data'])[0].decode()
    check('BENEFICIARIO DE PRUEBA' in html_test, 'hoja de prueba de alineación')
    omitido('PDF del cheque (wkhtmltopdf)', 'el shell corre con --no-http; se valida el HTML del reporte')


ejecutar(_p2_check_printing)

# ======================================================================
#  al_l10n_pe_collection — cartera, gestión, compromiso, intereses, calificación
# ======================================================================
_p2_result_promise = _p2_env.ref('al_l10n_pe_collection.result_promise')

caso('al_l10n_pe_collection', 'Cartera vencida, gestión con compromiso de pago y cumplimiento',
     'Cobranza → Cartera: ver la factura vencida; Registrar gestión (llamada, «Promete pagar»); '
     'registrar el cobro y evaluar el compromiso.')


def _p2_collection_promise():
    customer = registro(_p2_partner('Cliente cobranza', '2061209034'), 'deudor')
    invoice = registro(_p2_invoice(customer, 1000.0, due_in=-40), 'factura vencida 40 días')
    Portfolio = _p2_env['l10n_pe.collection.portfolio']
    Portfolio.flush_model()
    row = Portfolio.search([('move_id', '=', invoice.id)])
    igual(row.days_overdue, 40, 'días de atraso en la cartera')
    igual(row.bucket_id.name, '31 a 60 días', 'tramo de antigüedad')
    igual(row.amount_residual, 1000.0, 'saldo en cartera')
    action = registro(_p2_env['l10n_pe.collection.action'].create({
        'partner_id': customer.id, 'user_id': _p2_admin.id, 'channel': 'call',
        'result_id': _p2_result_promise.id, 'promise_date': _p2_today + _p2_td(days=5),
        'promise_amount': 600, 'line_ids': [Command.set(_p2_receivable(invoice).ids)],
        'next_action_date': _p2_today + _p2_td(days=6), 'next_action_summary': qa_name('P2 Confirmar pago'),
    }), 'gestión')
    promise = registro(action.promise_id, 'compromiso')
    igual((promise.amount, promise.state), (600.0, 'pending'), 'compromiso pendiente por 600')
    check(customer.activity_ids.filtered(lambda a: a.summary == qa_name('P2 Confirmar pago')),
          'actividad de seguimiento programada')
    registro(_p2_pay(invoice, 600), 'cobro parcial')
    promise._l10n_pe_evaluate()
    igual(promise.state, 'kept', 'compromiso cumplido antes de su fecha')
    igual(promise.collected_amount, 600.0, 'importe cobrado del compromiso')


ejecutar(_p2_collection_promise)

caso('al_l10n_pe_collection', 'Interés moratorio y nota de débito',
     'Cobranza → Intereses: asistente de intereses para el cliente → crear nota de débito.')


def _p2_collection_interest():
    old_rate = company.l10n_pe_collection_interest_rate
    try:
        company.l10n_pe_collection_interest_rate = 12.0
        customer = registro(_p2_partner('Cliente intereses', '2061209035'), 'deudor')
        invoice = registro(_p2_invoice(customer, 1000.0, due_in=-36), 'factura vencida 36 días')
        line = _p2_receivable(invoice)
        amount, _ac, days = customer._l10n_pe_collection_interest(line, _p2_today, company)
        igual(days, 36, 'días de mora')
        igual(amount, 11.40, 'interés 1000 × (1.12^(36/360) − 1)')
        wizard = _p2_env['l10n_pe.collection.interest.wizard'].create({
            'partner_ids': [Command.set(customer.ids)], 'date': _p2_today})
        igual(len(wizard.line_ids), 1, 'una línea de interés')
        note = _p2_env['account.move'].browse(wizard.action_create()['res_id'])
        registro(note, 'nota de débito por intereses (borrador)')
        igual(note.state, 'draft', 'nota de débito en borrador')
        igual(note.debit_origin_id, invoice, 'nota de débito referida a la factura')
        igual(note.amount_untaxed, 11.40, 'base de la nota de débito')
        line.invalidate_recordset(['l10n_pe_collection_interest_date'])
        igual(customer._l10n_pe_collection_interest(line, _p2_today, company)[0], 0.0,
              'facturado el interés, no se vuelve a calcular')
    finally:
        company.l10n_pe_collection_interest_rate = old_rate


ejecutar(_p2_collection_interest)

caso('al_l10n_pe_collection', 'Calificación del deudor y bloqueo automático por mora',
     'Cobranza → Clientes: recalcular calificación; el cliente moroso queda bloqueado; el jefe lo libera.')


def _p2_collection_rating():
    old_days = company.l10n_pe_collection_hold_days
    try:
        company.l10n_pe_collection_hold_days = 60
        customer = registro(_p2_partner('Cliente moroso', '2061209036'), 'deudor')
        registro(_p2_invoice(customer, 1000.0, due_in=-130), 'factura vencida 130 días')
        for days in (40, 30, 20):
            promise = _p2_env['l10n_pe.collection.promise'].create({
                'partner_id': customer.id, 'user_id': _p2_admin.id,
                'date': _p2_today - _p2_td(days=days), 'amount': 100})
            promise._l10n_pe_evaluate()
            registro(promise, 'compromiso incumplido')
        igual(promise.state, 'broken', 'compromiso incumplido')
        customer._l10n_pe_collection_rate(company, _p2_today)
        partner = customer.with_company(company)
        check(partner.l10n_pe_collection_rating in ('C', 'D'), 'calificación C/D', partner.l10n_pe_collection_rating)
        igual(partner.l10n_pe_collection_max_days, 130, 'máximo atraso')
        igual(partner.l10n_pe_collection_hold, 'auto', 'bloqueo automático')
        check(partner._l10n_pe_collection_is_on_hold(company), 'cliente bloqueado')
        partner.action_l10n_pe_collection_release()
        igual(partner.l10n_pe_collection_hold, 'released', 'liberado por el jefe de cobranza')
    finally:
        company.l10n_pe_collection_hold_days = old_days


ejecutar(_p2_collection_rating)

# ======================================================================
#  al_l10n_pe_collection_sale — bloqueo de venta por mora
# ======================================================================
caso('al_l10n_pe_collection_sale', 'Pedido de venta bloqueado por crédito y liberado',
     'Cobranza → Clientes → Bloquear crédito; Ventas → pedido → Confirmar (rechazado); liberar y confirmar.')


def _p2_sale_hold():
    from odoo.exceptions import UserError
    customer = registro(_p2_partner('Cliente bloqueado venta', '2061209037'), 'cliente')
    product = registro(_p2_env['product.product'].create({'name': qa_name('P2 Producto venta'),
                                                          'list_price': 100}), 'producto')
    order = registro(_p2_env['sale.order'].create({
        'partner_id': customer.id,
        'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 1})]}), 'pedido')
    customer.action_l10n_pe_collection_hold()
    order.invalidate_recordset(['l10n_pe_collection_hold_warning'])
    check(order.l10n_pe_collection_hold_warning, 'aviso de bloqueo en el pedido', order.l10n_pe_collection_hold_warning)
    try:
        with env.cr.savepoint():
            order.action_confirm()
        check(False, 'la confirmación debía rechazarse con el cliente bloqueado')
    except UserError as exc:
        check('bloqueado' in str(exc), 'confirmación rechazada por bloqueo', str(exc)[:120])
    customer.action_l10n_pe_collection_release()
    order.invalidate_recordset(['l10n_pe_collection_hold_warning'])
    check(not order.l10n_pe_collection_hold_warning, 'sin aviso tras liberar')
    order.action_confirm()
    igual(order.state, 'sale', 'pedido confirmado tras liberar')


ejecutar(_p2_sale_hold)

# ======================================================================
#  al_l10n_pe_bank_collection — archivo de deudores BCP y respuesta
# ======================================================================
_p2_agreement = []


def _p2_get_agreement():
    found = _p2_env['l10n_pe.bank.collection.agreement'].search([('name', '=', qa_name('P2 BCP soles'))], limit=1)
    if found:
        return found
    if not _p2_agreement:
        _p2_agreement.append(_p2_env['l10n_pe.bank.collection.agreement'].create({
            'name': qa_name('P2 BCP soles'), 'journal_id': _p2_bank.id, 'account_branch': '191',
            'account_number': '1234567', 'company_name': 'OLANO IT SAC',
            'debtors_layout_id': _p2_env.ref('al_l10n_pe_bank_collection.layout_bcp_crep_debtors').id,
            'response_layout_id': _p2_env.ref('al_l10n_pe_bank_collection.layout_bcp_crep_response').id,
            'days_ahead': 10}))
    return _p2_agreement[0]


caso('al_l10n_pe_bank_collection', 'Archivo de deudores BCP (CREP)',
     'Tesorería → Recaudación → Lotes de deudores: nuevo lote, Cargar documentos → Generar archivo.')


def _p2_bank_collection_debtors():
    _p2_agreement.clear()
    agreement = registro(_p2_get_agreement(), 'convenio')
    c1 = registro(_p2_partner('CLIENTE ÑANDÚ', '2061209038'), 'deudor 1')
    c1.name = 'QA20 P2 COMPAÑÍA ÑANDÚ SAC'
    c2 = registro(_p2_partner('Cliente recaudo 2', '2061209039'), 'deudor 2')
    overdue = registro(_p2_invoice(c1, 1234.56, due_in=-10), 'vencida')
    registro(_p2_invoice(c2, 100.0, due_in=5), 'vence dentro de 10 días')
    registro(_p2_invoice(c2, 100.0, due_in=40), 'vence después (no va)')
    batch = registro(_p2_env['l10n_pe.bank.collection.batch'].create({
        'agreement_id': agreement.id, 'partner_ids': [Command.set((c1 | c2).ids)]}), 'lote')
    batch.action_load()
    igual(batch.line_count, 2, 'documentos en el lote (excluye el que vence después)')
    igual(batch.amount_total, 1334.56, 'total del lote')
    batch.action_generate()
    igual(batch.state, 'generated', 'lote generado')
    check(batch.filename and batch.filename.startswith('CREP_'), 'nombre del archivo CREP', batch.filename)
    lines = batch.file.content.decode('ascii').split('\r\n')
    igual(len(lines), 3, 'cabecera + 2 detalles')
    check(all(len(x) == 250 for x in lines), 'registros de 250 posiciones')
    header, first = lines[0], lines[1]
    igual(header[0:13], 'CC1910' + '1234567', 'cabecera: sucursal/moneda/cuenta')
    igual(header[62:71], '000000002', 'cabecera: cantidad de registros')
    igual(header[71:86], '000000000133456', 'cabecera: importe total')
    igual(first[13:27].rstrip(), c1.vat, 'detalle: código de depositante = RUC')
    igual(first[27:67].rstrip(), 'QA20 P2 COMPANIA NANDU SAC', 'detalle: nombre en ASCII')
    igual(first[67:97].rstrip(), overdue.name, 'detalle: número de documento')
    igual(first[113:128], '000000000123456', 'detalle: importe')


ejecutar(_p2_bank_collection_debtors)

caso('al_l10n_pe_bank_collection', 'Importar respuesta del banco y aplicar cobros',
     'Tesorería → Recaudación → Respuestas: subir el archivo de abonos → Importar → Procesar.')


def _p2_bank_collection_response():
    _p2_agreement.clear()
    agreement = registro(_p2_get_agreement(), 'convenio')
    layout = agreement.response_layout_id
    c1 = registro(_p2_partner('Cliente abono 1', '2061209040'), 'deudor')
    c2 = registro(_p2_partner('Cliente abono 2', '2061209041'), 'deudor sin doc')
    invoice = registro(_p2_invoice(c1, 500.0, due_in=-3), 'factura a cobrar')
    old = registro(_p2_invoice(c2, 300.0, due_in=-20), 'antigua')
    newer = registro(_p2_invoice(c2, 400.0, due_in=-5), 'reciente')
    rows = [(c1.vat, invoice.name, 500.0, '552001'), ('00' + c2.vat, '', 500.0, '552002')]
    details = [{
        'account_branch': '191', 'account_number': '1234567', 'currency': agreement.currency_id,
        'depositor_code': code, 'return_info': info, 'payment_date': _p2_today, 'due_date': _p2_today,
        'paid_amount': amount, 'late_amount': 0.0, 'paid_total': amount, 'branch': '000191',
        'operation_number': op, 'channel': 'AGENTE'} for code, info, amount, op in rows]
    header = {'account_branch': '191', 'account_number': '1234567', 'currency': agreement.currency_id,
              'file_date': _p2_today, 'record_count': len(rows), 'total_amount': 1000.0}
    content = layout._build_file(header, details)
    response = registro(_p2_env['l10n_pe.bank.collection.response'].create({
        'agreement_id': agreement.id, 'file': _p2_BinaryBytes(content), 'filename': 'abonos_qa20.txt'}), 'respuesta')
    response.action_import()
    l1, l2 = response.line_ids.sorted('id')
    igual((l1.state, l1.partner_id), ('matched', c1), 'abono 1 casado con el documento')
    igual(l2.state, 'partner', 'abono 2 casado por cliente (ceros a la izquierda)')
    response.action_process()
    igual(response.state, 'done', 'respuesta procesada')
    registro(response.line_ids.payment_id, 'cobros generados')
    check(invoice.payment_state in ('paid', 'in_payment'), 'factura con documento cobrada', invoice.payment_state)
    check('552001' in (l1.payment_id.memo or ''), 'memo del cobro lleva la operación', l1.payment_id.memo)
    check(old.payment_state in ('paid', 'in_payment'), 'abono sin documento paga primero la más antigua')
    igual(newer.amount_residual, 200.0, 'saldo de la reciente')
    again = _p2_env['l10n_pe.bank.collection.response'].create({
        'agreement_id': agreement.id, 'file': _p2_BinaryBytes(content), 'filename': 'abonos_qa20_bis.txt'})
    again.action_import()
    igual(set(again.line_ids.mapped('state')), {'duplicate'}, 'reimportar el mismo archivo: duplicados')
    again.unlink()


ejecutar(_p2_bank_collection_response)

# ======================================================================
#  al_l10n_pe_account_letter — canje de letras y operaciones con el banco
# ======================================================================
_p2_doc01 = _p2_env.ref('l10n_pe.document_type01')
_p2_pe_bank = _p2_env['l10n_pe.bank'].search([], limit=1)


def _p2_letter_journal():
    return _p2_journal('Q2LT', 'Letras por cobrar', 'general', currency_id=_p2_pen.id,
                       l10n_pe_letter_type='receivable')


def _p2_redeemed_letter(partner, amount, letters=2):
    invoice = registro(_p2_invoice(partner, amount, due_in=0, invoice_date=_p2_date(2026, 10, 1)), 'factura canjeada')
    term = invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
    letter = _p2_env['l10n_pe.letter'].create({
        'partner_id': partner.id, 'type': 'out_invoice', 'journal_id': _p2_letter_journal().id,
        'invoice_line_ids': [Command.create({'document_type_id': _p2_doc01.id, 'move_line_id': term.id,
                                             'account_id': term.account_id.id,
                                             'imp_div': abs(term.amount_residual_currency)})]})
    letter.invoice_date = _p2_date(2026, 10, 5)
    letter.action_checked()
    letter.write({'number_letter': letters, 'letter_end_date': _p2_date(2026, 12, 5), 'range_date': 30})
    letter.action_create_letters()
    for index, line in enumerate(letter.letter_line_ids, start=1):
        line.nro_letter = 'QA20-P2-%d-%03d' % (letter.id, index)
    letter.action_redeemed()
    return registro(letter, 'canje')


def _p2_send_letter(letter, letter_type, when):
    _p2_env['l10n_pe.letter.canje.wizard'].create({
        'letter_id': letter.id, 'date_canje': when, 'letter_type': letter_type, 'canje_type': 'all',
        'bank_id': _p2_pe_bank.id, 'code': 'QA20-%s' % letter.name}).action_canje()


def _p2_letter_apply(letter, operation, bank_journal, when, **values):
    wizard = _p2_env['l10n_pe.letter.bank.wizard'].with_context(
        **letter._action_bank_operation(operation)['context']).create(dict({
            'letter_line_ids': [Command.set(letter.letter_line_ids.ids)],
            'date': when, 'bank_journal_id': bank_journal.id}, **values))
    wizard.action_apply()
    return wizard


caso('al_l10n_pe_account_letter', 'Canje de factura en 2 letras y descuento bancario',
     'Contabilidad → Letras → Canjes: nuevo canje, Verificar, Crear letras, Canjear; Enviar al banco '
     '(descuento); Liquidar descuento; Cobro del banco.')


def _p2_letter_discount():
    company_ = company
    loan, interest, fee = (company_.l10n_pe_letter_loan_account_id, company_.l10n_pe_letter_interest_account_id,
                           company_.l10n_pe_letter_fee_account_id)
    check(loan and interest and fee, 'cuentas de letras de la compañía', '%s / %s / %s' % (loan.code, interest.code, fee.code))
    partner = registro(_p2_partner('Cliente letras', '2061209042'), 'aceptante')
    letter = _p2_redeemed_letter(partner, 1000.0, letters=2)
    igual(letter.state, 'redeemed', 'canje en estado Canjeado')
    igual(len(letter.letter_line_ids), 2, 'dos letras')
    igual(sum(letter.letter_line_ids.mapped('imp_div')), 1000.0, 'las letras suman la factura')
    registro(letter.letter_line_ids, 'letras')
    portfolio_acc = _p2_env['l10n_pe.letter.account.config'].search([
        ('account_type', '=', 'asset_receivable'), ('letter_type', '=', 'portfolio'),
        ('currency_id', '=', _p2_pen.id)], limit=1).account_id
    opens = letter.letter_line_ids.mapped(lambda l: l._l10n_pe_open_line())
    check(opens and all(o.account_id == portfolio_acc and o.debit for o in opens),
          'el canje carga las letras en cartera', '%s → %s' % (portfolio_acc.code, opens.mapped('account_id.code')))
    bank_journal = _p2_bank
    _p2_send_letter(letter, 'discount', _p2_date(2026, 10, 10))
    igual(letter.state, 'banked', 'canje Bancarizado al enviar todas las letras')
    igual(letter.canje_move_id.date, _p2_date(2026, 10, 10), 'asiento del envío con la fecha del envío')
    wizard = _p2_letter_apply(letter, 'settle_discount', bank_journal, _p2_date(2026, 10, 11),
                              interest_amount=30.0, fee_amount=5.0)
    igual(wizard.net_amount, 965.0, 'neto abonado por el banco')
    move = letter.bank_move_ids
    registro(move, 'liquidación del descuento')
    igual(_p2_balance(move, bank_journal.default_account_id), 965.0, 'banco neto')
    igual(_p2_balance(move, interest), 30.0, 'interés 6734')
    igual(_p2_balance(move, fee), 5.0, 'comisión 6391')
    igual(_p2_balance(move, loan), -1000.0, 'préstamo 4511')
    igual(set(letter.letter_line_ids.mapped('payment_state')), {'pending'}, 'descontada sigue pendiente')
    _p2_letter_apply(letter, 'collected', bank_journal, _p2_today)
    registro(letter.bank_move_ids - move, 'cobro del banco')
    igual(set(letter.letter_line_ids.mapped('payment_state')), {'paid'}, 'letras cobradas')
    igual(_p2_balance(letter.bank_move_ids, loan), 0.0, 'préstamo cancelado')


ejecutar(_p2_letter_discount)

caso('al_l10n_pe_account_letter', 'Letra en cobranza libre cobrada por el banco',
     'Canje → Enviar al banco (cobranza libre) → Operación bancaria «Cobrada» con comisión.')


def _p2_letter_billing():
    from odoo.exceptions import UserError
    partner = registro(_p2_partner('Cliente letras cobranza', '2061209043'), 'aceptante')
    letter = _p2_redeemed_letter(partner, 1000.0, letters=1)
    _p2_send_letter(letter, 'billing', _p2_date(2026, 10, 10))
    igual(set(letter.letter_line_ids.mapped('letter_type')), {'billing'}, 'letra en cobranza libre')
    line = letter.letter_line_ids
    bank_line = line._l10n_pe_open_line()
    check('Cobro del banco' in (bank_line._l10n_pe_payment_block_reason() or ''),
          'letra en el banco: el pago directo se bloquea')
    wizard = _p2_letter_apply(letter, 'collected', _p2_bank, _p2_today, fee_amount=7.0)
    igual(wizard.net_amount, 993.0, 'neto cobrado')
    registro(letter.bank_move_ids, 'cobro de la letra')
    igual(_p2_balance(letter.bank_move_ids, _p2_bank.default_account_id), 993.0, 'banco')
    igual(line.payment_state, 'paid', 'letra cobrada')
    try:
        with env.cr.savepoint():
            letter.action_draft()
        check(False, 'no debe restablecerse un canje con operaciones bancarias')
    except UserError:
        check(True, 'restablecer a borrador bloqueado con operaciones')


ejecutar(_p2_letter_billing)

# ======================================================================
#  al_l10n_pe_factoring
# ======================================================================
_p2_misc = _p2_journal('Q2FG', 'Factoring', 'general')


def _p2_fact_operation(factor, invoices, modality='without_recourse', percent=90.0):
    return _p2_env['l10n_pe.factoring'].create({
        'factor_id': factor.id, 'modality': modality, 'journal_id': _p2_misc.id,
        'currency_id': _p2_pen.id, 'default_advance_percent': percent,
        'line_ids': [Command.create({'move_id': inv.id, 'advance_percent': percent}) for inv in invoices]})


def _p2_fact_wizard(operation, kind, **vals):
    wizard = _p2_env['l10n_pe.factoring.wizard'].create(dict({
        'factoring_id': operation.id, 'operation': kind, 'date': _p2_today,
        'bank_journal_id': _p2_bank.id}, **vals))
    if kind in ('settle', 'repurchase', 'write_off') and 'line_ids' not in vals:
        wizard.line_ids = operation.line_ids.filtered(lambda l: l.state == 'assigned')
    wizard.action_apply()
    return wizard


caso('al_l10n_pe_factoring', 'Factoring sin recurso: cesión, desembolso y liquidación',
     'Contabilidad → Factoring → Operaciones: nueva operación con la factura, Ceder → Desembolsar → Liquidar.')


def _p2_factoring_without():
    customer = registro(_p2_partner('Cliente factoring', '2061209044'), 'adquirente')
    factor = registro(_p2_partner('Factor capital', '2061209045'), 'factor')
    invoice = registro(_p2_invoice(customer, 1000.0, due_in=60, invoice_date=_p2_today), 'factura cedida')
    op = registro(_p2_fact_operation(factor, invoice), 'operación sin recurso')
    cfg = op._config()
    igual((op.advance_amount, op.retained_amount), (900.0, 100.0), 'adelanto 90 % y retenido 10 %')
    op.action_assign()
    igual(op.state, 'assigned', 'cedida')
    check(invoice.payment_state in ('paid', 'in_payment'), 'sin recurso la factura se da de baja', invoice.payment_state)
    igual(_p2_balance(op.move_ids, cfg.assigned_account_id, factor), 1000.0, 'deuda pasa al factor')
    _p2_fact_wizard(op, 'disburse', interest_amount=20.0, fee_amount=10.0, expense_amount=5.0)
    igual(op.net_amount, 865.0, 'neto desembolsado')
    igual(_p2_balance(op.move_ids, _p2_bank.default_account_id), 865.0, 'banco recibe el neto')
    igual(_p2_balance(op.move_ids, cfg.interest_account_id), 20.0, 'interés')
    _p2_fact_wizard(op, 'settle')
    igual(op.state, 'done', 'operación liquidada')
    igual(_p2_balance(op.move_ids, cfg.assigned_account_id), 0.0, 'cuenta del factor saldada')
    igual(_p2_balance(op.move_ids, _p2_bank.default_account_id), 965.0, 'banco total (neto + retenido)')
    registro(op.move_ids, 'asientos de factoring')
    for move in op.move_ids:
        check(not _p2_pen.round(sum(move.line_ids.mapped('balance'))), 'asiento %s cuadra' % move.ref)


ejecutar(_p2_factoring_without)

caso('al_l10n_pe_factoring', 'Factoring con recurso y anotación en CAVALI (servicio simulado)',
     'Factura → Registrar en CAVALI; Factoring con recurso: Ceder (transferencia CAVALI) → Desembolsar → Liquidar.')


class _P2FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status
        self.text = _p2_json.dumps(data)

    def json(self):
        return self._data


def _p2_factoring_with_cavali():
    fields_ = ('l10n_pe_cavali_mode', 'l10n_pe_cavali_environment', 'l10n_pe_cavali_url_test',
               'l10n_pe_cavali_user', 'l10n_pe_cavali_password', 'l10n_pe_cavali_rut')
    saved = {f: company[f] for f in fields_}
    saved_street = company.partner_id.street
    post = 'odoo.addons.al_l10n_pe_factoring.models.cavali.requests.post'
    try:
        company.write({'l10n_pe_cavali_mode': 'webservice', 'l10n_pe_cavali_environment': 'test',
                       'l10n_pe_cavali_url_test': 'https://cavali.test/api/', 'l10n_pe_cavali_user': 'usuario',
                       'l10n_pe_cavali_password': 'clave', 'l10n_pe_cavali_rut': 'RUT1'})
        if not company.partner_id.street:
            company.partner_id.street = 'Av. Arequipa 456'
        customer = registro(_p2_partner('Cliente factoring recurso', '2061209046',
                                        street='Av. Javier Prado 123'), 'adquirente')
        factor = registro(_p2_partner('Factor recurso', '2061209047'), 'factor')
        invoice = registro(_p2_invoice(customer, 2000.0, due_in=60, invoice_date=_p2_today), 'factura negociable')
        ok = _P2FakeResponse({'codigo': '0', 'mensaje': 'Correcto', 'codigoAnotacion': 'AN-QA20', 'estado': 'ANOTADA'})
        with _p2_patch(post, return_value=ok) as mock:
            invoice.action_l10n_pe_cavali_register()
        payload = mock.call_args.kwargs['json']
        igual(mock.call_args.args[0], 'https://cavali.test/api/facturas/registro', 'URL de registro CAVALI')
        igual(payload['montoNetoPendiente'], 2000.0, 'payload: monto neto pendiente')
        igual(payload['rucAdquirente'], customer.vat, 'payload: RUC del adquirente')
        igual((invoice.l10n_pe_negotiable_state, invoice.l10n_pe_cavali_number), ('registered', 'AN-QA20'),
              'factura negociable anotada')
        check('clave' not in (invoice.l10n_pe_cavali_log_ids[:1].request_body or ''), 'credenciales fuera del log')
        registro(invoice.l10n_pe_cavali_log_ids, 'log CAVALI')
        invoice._l10n_pe_add_negotiable_event('accepted')
        op = registro(_p2_fact_operation(factor, invoice, modality='with_recourse', percent=80.0), 'operación con recurso')
        cfg = op._config()
        with _p2_patch(post, return_value=_P2FakeResponse({'codigo': '0'})) as mock:
            op.action_assign()
        igual(mock.call_args.args[0], 'https://cavali.test/api/facturas/transferencia', 'transferencia CAVALI')
        igual(invoice.l10n_pe_negotiable_state, 'transferred', 'factura transferida')
        igual(invoice.payment_state, 'not_paid', 'con recurso no se da de baja (NIIF 9)')
        _p2_fact_wizard(op, 'disburse', interest_amount=30.0)
        igual(_p2_balance(op.move_ids, cfg.obligation_account_id, factor), -1600.0, 'obligación con el factor')
        with _p2_patch(post, return_value=_P2FakeResponse({'codigo': '0'})) as mock:
            _p2_fact_wizard(op, 'settle')
        igual(mock.call_args.kwargs['json'].get('montoPagado'), 2000.0, 'pago informado a CAVALI')
        igual(op.state, 'done', 'operación liquidada')
        check(invoice.payment_state in ('paid', 'in_payment'), 'el cobro del factor cancela la factura')
        igual(_p2_balance(op.move_ids, _p2_bank.default_account_id), 1970.0, 'banco: adelanto 1570 + retenido 400')
        registro(op.move_ids, 'asientos con recurso')
        omitido('CAVALI real', 'sin credenciales de prueba: servicio simulado con mock')
    finally:
        company.write(saved)
        company.partner_id.street = saved_street


ejecutar(_p2_factoring_with_cavali)

# ======================================================================= PARTE 3
# -*- coding: utf-8 -*-
# Fase contabilidad_b — parte 3: fondos de caja, gastos con caja chica, cierre
# de caja, pasarelas de pago (Culqi, Izipay, Niubiz, PagoEfectivo) y flujo de
# caja proyectado.
import hashlib as _p3_hashlib
import hmac as _p3_hmac
import json as _p3_json
from datetime import date as _p3_date, timedelta as _p3_td
from unittest.mock import MagicMock as _p3_MagicMock, Mock as _p3_Mock, patch as _p3_patch

_p3_API = 'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'
_p3_seq = [0]


def _p3_rate(currency, day, rate):
    """Tipo de cambio search-or-create (rate = unidades de moneda por 1 PEN)."""
    Rate = env['res.currency.rate']
    found = Rate.search([('name', '=', day), ('currency_id', '=', currency.id),
                         ('company_id', '=', company.id)], limit=1)
    return found or Rate.create({'name': day, 'currency_id': currency.id,
                                 'company_id': company.id, 'rate': rate})


def _p3_acc_domain():
    return env['account.account']._check_company_domain(company)


_p3_expense = env['account.account'].search([*_p3_acc_domain(), ('account_type', '=', 'expense')], limit=1)
_p3_bank = env['account.journal'].search([('company_id', '=', company.id), ('type', '=', 'bank')], limit=1)


def _p3_partner(name, **vals):
    return env['res.partner'].create(dict({'name': qa_name('P3 %s' % name)}, **vals))


def _p3_bill(supplier, amount, day=_p3_date(2026, 10, 5)):
    _p3_seq[0] += 1
    bill = env['account.move'].create({
        'move_type': 'in_invoice', 'partner_id': supplier.id,
        'l10n_latam_document_number': 'F001-%06d' % (930000 + _p3_seq[0]),
        'invoice_date': day, 'currency_id': company.currency_id.id,
        'invoice_line_ids': [Command.create({
            'name': 'Combustible', 'quantity': 1, 'price_unit': amount,
            'account_id': _p3_expense.id, 'tax_ids': [Command.clear()]})],
    })
    bill.action_post()
    return bill


def _p3_fund(worker, amount, fund_type='advance', purpose='Visita a obra'):
    fund = env['l10n_pe.cash.fund'].create({
        'fund_type': fund_type, 'partner_id': worker.id, 'purpose': purpose,
        'amount': amount, 'journal_id': _p3_bank.id, 'date': _p3_date(2026, 10, 1)})
    fund.action_approve()
    action = fund.action_deliver()
    env['account.payment'].browse(action['res_id']).action_post()
    return fund


# ============================================================ cash_fund
caso('al_l10n_pe_cash_fund', 'Entrega a rendir: rendición con movilidad, devolución y cierre',
     'Contabilidad → Entregas a rendir → Nuevo: aprobar, entregar, registrar rendición con factura '
     'y planilla de movilidad, registrar la devolución del saldo y cerrar.')


def _p3_cash_fund_advance():
    worker = registro(_p3_partner('Trabajador ER', additional_identifiers={'PE_DNI': '40506071'}))
    supplier = registro(_p3_partner('Grifo ER'))
    fund = registro(_p3_fund(worker, 500.0), 'entrega a rendir')
    check(fund.name.startswith('ER/'), 'Número con prefijo ER/', fund.name)
    igual((fund.state, fund.amount_delivered, fund.amount_balance), ('open', 500.0, 500.0),
          'Fondo abierto y entregado')
    bill = registro(_p3_bill(supplier, 300.0), 'factura rendida')
    settlement = registro(env['l10n_pe.cash.settlement'].create({
        'fund_id': fund.id, 'date': _p3_date(2026, 10, 6),
        'document_line_ids': [Command.create({'move_id': bill.id})],
        'mobility_line_ids': [
            Command.create({'date': _p3_date(2026, 10, 2), 'reason': 'Visita a obra',
                            'destination': 'Santa Anita - Ate', 'amount': 30.0}),
            Command.create({'date': _p3_date(2026, 10, 2), 'reason': 'Retorno',
                            'destination': 'Ate - Santa Anita', 'amount': 25.0}),
        ]}), 'rendición')
    igual(settlement.amount_mobility_excess, 9.8, 'Exceso de movilidad sobre el tope 4 % RMV (45,20/día)')
    settlement.action_post()
    igual(bill.payment_state, 'paid', 'La factura queda pagada con la rendición')
    check(settlement.mobility_number, 'Planilla de movilidad numerada', settlement.mobility_number)
    igual(settlement.move_id.state, 'posted', 'Asiento de rendición publicado')
    registro(settlement.move_id, 'asiento de rendición')
    igual(fund.amount_balance, 145.0, 'Saldo por devolver 500 − 300 − 55')
    try:
        with env.cr.savepoint():
            fund.action_close()
        check(False, 'No permite cerrar con saldo pendiente')
    except Exception as exc:  # noqa: BLE001
        check('UserError' in type(exc).__name__, 'No permite cerrar con saldo pendiente', str(exc)[:90])
    ret = env['account.payment'].browse(fund.action_register_return()['res_id'])
    ret.action_post()
    registro(ret, 'devolución del saldo')
    igual(fund.amount_balance, 0.0, 'Saldo cero tras la devolución')
    fund.action_close()
    igual(fund.state, 'closed', 'Fondo cerrado')
    check(all(fund._fund_move_lines().mapped('reconciled')), 'Cuenta del fondo conciliada al cerrar')
    try:
        html = env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_cash_fund.action_report_mobility_sheet', settlement.ids)[0]
        check(b'Planilla de gastos de movilidad' in html, 'PDF de planilla de movilidad generado')
    except Exception as exc:  # noqa: BLE001
        aviso('No se pudo renderizar la planilla de movilidad', '%s: %s' % (type(exc).__name__, exc))


ejecutar(_p3_cash_fund_advance)

caso('al_l10n_pe_cash_fund', 'Caja chica: gasto y reposición; reembolso de entrega excedida',
     'Contabilidad → Caja chica → Nuevo: rendir una factura y reponer el fondo; en una entrega a '
     'rendir con gasto mayor, registrar el reembolso al trabajador.')


def _p3_cash_fund_petty():
    worker = registro(_p3_partner('Cajera CCH', additional_identifiers={'PE_DNI': '40506072'}))
    supplier = registro(_p3_partner('Librería CCH'))
    fund = registro(_p3_fund(worker, 1000.0, 'petty_cash', 'Caja chica oficina'), 'caja chica')
    check(fund.name.startswith('CCH/'), 'Número con prefijo CCH/', fund.name)
    st = env['l10n_pe.cash.settlement'].create({
        'fund_id': fund.id, 'document_line_ids': [Command.create({'move_id': _p3_bill(supplier, 400.0).id})]})
    st.action_post()
    registro(st, 'rendición caja chica')
    igual(fund.amount_balance, 600.0, 'Saldo de caja chica tras el gasto')
    pay = env['account.payment'].browse(fund.action_replenish()['res_id'])
    pay.action_post()
    registro(pay, 'reposición')
    igual((pay.amount, pay.l10n_pe_cash_fund_kind), (400.0, 'replenishment'), 'Reposición por lo gastado')
    igual(fund.amount_balance, 1000.0, 'Caja chica repuesta al monto fijo')
    # Reembolso: gasto mayor a lo entregado.
    adv = registro(_p3_fund(worker, 100.0), 'entrega excedida')
    st2 = env['l10n_pe.cash.settlement'].create({
        'fund_id': adv.id, 'document_line_ids': [Command.create({'move_id': _p3_bill(supplier, 150.0).id})]})
    st2.action_post()
    igual(adv.amount_balance, -50.0, 'Saldo a favor del trabajador')
    reimb = env['account.payment'].browse(adv.action_register_reimbursement()['res_id'])
    reimb.action_post()
    registro(reimb, 'reembolso al trabajador')
    igual((reimb.payment_type, reimb.amount), ('outbound', 50.0), 'Reembolso de salida por 50')
    adv.action_close()
    igual(adv.state, 'closed', 'Entrega con reembolso cerrada')


ejecutar(_p3_cash_fund_petty)

# ============================================================ cash_fund_expense
caso('al_l10n_pe_cash_fund_expense', 'Gasto de empleado pagado con caja chica → factura de proveedor',
     'Gastos → Nuevo gasto con comprobante (boleta) y caja chica; enviar, aprobar y contabilizar: '
     'se genera la factura del proveedor pagada con la rendición del fondo.')


def _p3_cash_fund_expense():
    worker = registro(_p3_partner('Empleado gastos', additional_identifiers={'PE_DNI': '40506073'}))
    supplier = registro(_p3_partner('Restaurante gastos'))
    employee = registro(env['hr.employee'].create({'name': qa_name('P3 Empleado gastos'),
                                                   'work_contact_id': worker.id}))
    meal = registro(env['product.product'].create({
        'name': qa_name('P3 Almuerzo del personal'), 'type': 'service', 'can_be_expensed': True,
        'standard_price': 0.0, 'supplier_taxes_id': [Command.clear()],
        'property_account_expense_id': _p3_expense.id}))
    receipt_type = env.ref('l10n_pe.document_type03')
    journal = company._l10n_pe_expense_journal()
    check(journal, 'Diario de compras con documentos para gastos', journal.name)
    fund = registro(_p3_fund(worker, 500.0, 'petty_cash', 'Caja chica gastos'), 'caja chica')

    def _exp(**vals):
        return env['hr.expense'].create(dict({
            'name': 'Almuerzo del personal', 'employee_id': employee.id,
            'product_id': meal.id, 'total_amount_currency': 32.0,
            'date': _p3_date(2026, 10, 7), 'payment_mode': 'own_account',
            'l10n_pe_cash_fund_id': fund.id, 'vendor_id': supplier.id,
            'l10n_latam_document_type_id': receipt_type.id,
            'l10n_pe_document_number': 'B010-00095725'}, **vals))
    e1 = _exp()
    e2 = _exp(total_amount_currency=24.65, l10n_pe_document_number='B010-00095726')
    exps = registro(e1 | e2, 'gasto')
    exps.action_submit()
    exps.action_approve()
    exps.action_post()
    bill = e1.account_move_id
    registro(bill | e2.account_move_id, 'factura de proveedor del gasto')
    igual(bill.move_type, 'in_invoice', 'El gasto se contabiliza como factura de proveedor')
    igual(bill.partner_id, supplier, 'Proveedor del comprobante')
    igual(bill.l10n_latam_document_type_id, receipt_type, 'Tipo de documento boleta (03)')
    check('B010-00095725' in bill.name, 'Número del comprobante en la factura', bill.name)
    igual(bill.amount_total, 32.0, 'Importe de la factura')
    igual(bill.payment_state, 'paid', 'Factura pagada por la caja chica')
    igual(e1.state, 'paid', 'Gasto pagado')
    igual(fund.amount_balance, 500.0 - 32.0 - 24.65, 'Saldo de caja chica descontado')
    st = fund.settlement_ids
    registro(st, 'rendición automática')
    igual((len(st), st.state), (1, 'posted'), 'Una rendición publicada para ambos gastos')
    # Sin número de comprobante no se contabiliza.
    e3 = _exp(l10n_pe_document_number=False, total_amount_currency=10.0)
    e3.action_submit()
    e3.action_approve()
    try:
        with env.cr.savepoint():
            e3.action_post()
        check(False, 'Exige número de comprobante')
    except Exception as exc:  # noqa: BLE001
        check('número de comprobante' in str(exc), 'Exige número de comprobante', str(exc)[:90])


ejecutar(_p3_cash_fund_expense)

# ============================================================ cash_closing
_p3_cc = {}


def _p3_cc_setup():
    if _p3_cc:
        return _p3_cc
    partner = _p3_partner('Cliente caja')
    cash = env['account.journal'].create({'name': qa_name('P3 Caja tienda'), 'code': 'Q3CJ',
                                          'type': 'cash', 'company_id': company.id})
    (cash.inbound_payment_method_line_ids | cash.outbound_payment_method_line_ids) \
        .payment_account_id = cash.default_account_id
    sale = env['account.journal'].create({'name': qa_name('P3 Ventas caja'), 'code': 'Q3VC', 'type': 'sale',
                                          'l10n_latam_use_documents': False, 'company_id': company.id})
    _p3_cc.update(partner=partner, cash=cash, sale=sale,
                  method=env['pe.catalog.payment'].search([], limit=1))
    return _p3_cc


def _p3_cc_invoice(amount, day):
    c = _p3_cc
    move = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': c['partner'].id, 'journal_id': c['sale'].id,
        'invoice_date': day, 'date': day,
        'invoice_line_ids': [Command.create({'name': 'Venta', 'price_unit': amount, 'tax_ids': [Command.clear()]})]})
    move.action_post()
    return move


def _p3_cc_collect(invoice, day):
    wiz = env['account.payment.register'].with_context(
        active_model='account.move', active_ids=invoice.ids).create(
        {'journal_id': _p3_cc['cash'].id, 'payment_date': day})
    return wiz._create_payments()


def _p3_cc_payment(ptype, amount, day):
    c = _p3_cc
    p = env['account.payment'].create({
        'payment_type': ptype, 'partner_type': 'customer' if ptype == 'inbound' else 'supplier',
        'partner_id': c['partner'].id, 'amount': amount, 'date': day,
        'journal_id': c['cash'].id, 'pe_payment_method_id': c['method'].id})
    p.action_post()
    return p


def _p3_cc_count(closing, amount):
    counts = {c.value: c for c in closing.count_ids}
    hundreds, rest = divmod(round(amount * 100), 10000)
    counts[100.0].quantity = hundreds
    units, tenths = divmod(rest, 100)
    counts[1.0].quantity = units
    counts[0.1].quantity = tenths // 10


caso('al_l10n_pe_cash_closing', 'Cierre de caja con faltante: saldo según libros, arqueo y asiento de diferencia',
     'Contabilidad → Cierres de caja → Nuevo (caja, día): revisar ingresos/egresos del día, '
     'registrar el arqueo por denominaciones y cerrar; imprimir el PDF.')

_p3_D0, _p3_D1, _p3_D2 = _p3_date(2026, 10, 19), _p3_date(2026, 10, 20), _p3_date(2026, 10, 21)


def _p3_cash_closing():
    c = _p3_cc_setup()
    registro(c['cash'] | c['sale'], 'diario')
    registro(c['partner'])
    p0 = _p3_cc_payment('inbound', 1000, _p3_D0)
    inv1 = _p3_cc_invoice(500, _p3_D1)
    inv2 = _p3_cc_invoice(200, _p3_D0)
    _p3_cc_collect(inv1, _p3_D1)
    _p3_cc_collect(inv2, _p3_D1)
    p_out = _p3_cc_payment('outbound', 100, _p3_D1)
    registro(p0 | p_out, 'movimiento de caja')
    registro(inv1 | inv2, 'venta')
    closing = registro(env['l10n_pe.cash.closing'].create({'journal_id': c['cash'].id, 'date': _p3_D1}),
                       'cierre del día')
    igual(closing.balance_start, 1000.0, 'Saldo inicial según libros')
    igual(closing.amount_in, 700.0, 'Ingresos del día (contado 500 + cobranza 200)')
    igual(closing.amount_out, 100.0, 'Egresos del día')
    igual(closing.balance_book, 1600.0, 'Saldo final según libros')
    kinds = {line.amount: (line.category, line.sale_kind) for line in closing.line_ids}
    igual(kinds.get(500.0), ('collection', 'cash'), 'Venta al contado clasificada')
    igual(kinds.get(200.0), ('collection', 'credit'), 'Cobranza de venta al crédito clasificada')
    values = set(closing.count_ids.mapped('value'))
    check({200.0, 100.0, 0.1} <= values and 0.05 not in values, 'Denominaciones vigentes precargadas',
          sorted(values))
    try:
        with env.cr.savepoint():
            closing.action_close()
        check(False, 'Exige arqueo antes de cerrar')
    except Exception as exc:  # noqa: BLE001
        check('arqueo' in str(exc), 'Exige arqueo antes de cerrar', str(exc)[:80])
    _p3_cc_count(closing, 1590.0)
    igual(closing.difference, -10.0, 'Faltante de 10 en el arqueo')
    closing.action_close()
    igual(closing.state, 'closed', 'Caja cerrada')
    move = closing.move_id
    registro(move, 'asiento de faltante')
    igual(move.state, 'posted', 'Asiento de diferencia publicado')
    loss = move.line_ids.filtered(lambda l: l.account_id == c['cash'].loss_account_id)
    igual(sum(loss.mapped('balance')), 10.0, 'Faltante a la cuenta de pérdida de la caja')
    try:
        with env.cr.savepoint():
            _p3_cc_payment('inbound', 10, _p3_D1)
        check(False, 'Día cerrado bloquea nuevos pagos')
    except Exception as exc:  # noqa: BLE001
        check('cerrada' in str(exc), 'Día cerrado bloquea nuevos pagos', str(exc)[:80])
    nxt = registro(env['l10n_pe.cash.closing'].create({'journal_id': c['cash'].id, 'date': _p3_D2}),
                   'cierre día siguiente (abierto)')
    igual(nxt.balance_start, 1590.0, 'El día siguiente parte de lo arqueado')
    try:
        html = env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_cash_closing.report_cash_closing', closing.ids)[0].decode()
        check(closing.name in html and 'Faltante' in html and 'Cobro (venta al contado)' in html,
              'PDF de cierre con faltante y resumen por categoría')
    except Exception as exc:  # noqa: BLE001
        aviso('No se pudo renderizar el PDF de cierre', '%s: %s' % (type(exc).__name__, exc))


ejecutar(_p3_cash_closing)

caso('al_l10n_pe_cash_closing', 'Reapertura del cierre: anula la diferencia y desbloquea el día',
     'Cierres de caja → abrir el cierre posterior → Reabrir: el asiento de diferencia se anula y '
     'se puede volver a registrar movimientos.')


def _p3_cash_closing_reopen():
    c = _p3_cc_setup()
    if not env['l10n_pe.cash.closing'].search([('journal_id', '=', c['cash'].id), ('date', '=', _p3_D2)]):
        aviso('Sin cierre previo del caso anterior', 'se omite la reapertura')
        return
    closing = env['l10n_pe.cash.closing'].search([('journal_id', '=', c['cash'].id), ('date', '=', _p3_D2)])
    p = _p3_cc_payment('inbound', 50, _p3_D2)
    closing.action_refresh()
    _p3_cc_count(closing, closing.balance_book - 5.0)
    closing.action_close()
    diff = closing.move_id
    check(diff and diff.state == 'posted', 'Faltante del día 2 contabilizado')
    closing.action_reopen()
    igual(closing.state, 'open', 'Cierre reabierto')
    igual(diff.state, 'cancel', 'Asiento de diferencia anulado al reabrir')
    p2 = _p3_cc_payment('inbound', 10, _p3_D2)
    registro(p | p2, 'cobro tras reapertura')
    closing.action_refresh()
    igual(closing.balance_book, 1590.0 + 60.0, 'Libros recalculados tras la reapertura')
    registro(closing, 'cierre reabierto')
    registro(diff, 'diferencia anulada')


ejecutar(_p3_cash_closing_reopen)


# ============================================================ pasarelas
def _p3_provider(code, vals):
    """Copia de prueba (modo test, sin publicar) del proveedor instalado: no toca el original."""
    src = env['payment.provider'].sudo().search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
    prov = src.copy({'name': qa_name('P3 %s' % src.name), 'is_published': False})
    prov.write(dict({'is_live': False}, **vals))
    return prov


def _p3_pay_partner(**vals):
    return _p3_partner('Cliente pasarela', **dict({
        'email': 'rosa.qa20@example.com', 'phone': '987654321', 'street': 'Av. Arequipa 123',
        'city': 'Lima', 'country_id': env.ref('base.pe').id}, **vals))


def _p3_tx(prov, partner, method_code, amount, ref, **vals):
    pm = prov.payment_method_ids.filtered(lambda m: m.code == method_code)[:1]
    return env['payment.transaction'].sudo().create(dict({
        'payment_method_id': pm.id, 'amount': amount, 'currency_id': env.ref('base.PEN').id,
        'provider_id': prov.id, 'reference': ref, 'operation': 'online_direct',
        'partner_id': partner.id}, **vals))


def _p3_ref(tag):
    return 'QA20-P3-%s-%s' % (tag, fields.Datetime.now().strftime('%H%M%S%f'))


caso('al_payment_culqi', 'Proveedor Culqi en prueba: valores del checkout, payload del cargo y cargo simulado',
     'Contabilidad → Configuración → Proveedores de pago → Culqi: llaves de prueba; el cliente paga '
     'con tarjeta en el portal (cargo simulado con mock).')


def _p3_culqi():
    prov = registro(_p3_provider('culqi', {'culqi_public_key': 'pk_test_qa2000000000',
                                           'culqi_secret_key': 'sk_test_qa2000000000'}), 'proveedor (test)')
    igual(sorted(prov._get_supported_currencies().mapped('name')), ['PEN', 'USD'], 'Monedas PEN/USD')
    igual(prov.support_refund, 'partial', 'Soporta devolución parcial')
    igual(prov._build_request_headers('POST', 'charges', {})['Authorization'], 'Bearer sk_test_qa2000000000',
          'Cabecera con la llave secreta')
    try:
        with env.cr.savepoint():
            prov.write({'is_live': True})
        check(False, 'Llaves de prueba no sirven en producción')
    except Exception as exc:  # noqa: BLE001
        check('pk_live_' in str(exc), 'Llaves de prueba no sirven en producción', str(exc)[:80])
    partner = registro(_p3_pay_partner())
    tx = registro(_p3_tx(prov, partner, 'card', 120.50, _p3_ref('CULQI')), 'transacción')
    values = tx._get_processing_values()
    igual((values['culqi_amount'], values['culqi_currency'], values['culqi_payment_method']),
          (12050, 'PEN', 'tarjeta'), 'Valores del checkout en céntimos')
    check('sk_test_qa2000000000' not in str(values), 'La llave secreta no llega al navegador')
    token = 'tkn_test_QA20P3'
    payload = tx._culqi_prepare_charge_payload(token, 'device-qa', {'eci': '05', 'xid': 'X', 'ignored': 'x'})
    igual((payload['amount'], payload['currency_code'], payload['source_id'],
           payload['antifraud_details']['country_code']), (12050, 'PEN', token, 'PE'), 'Payload del cargo')
    check(set(payload['authentication_3DS']) == {'eci', 'xid'}, 'Solo campos 3DS permitidos', payload['authentication_3DS'])
    charge = {'object': 'charge', 'id': 'chr_test_QA20P3', 'amount': 12050, 'currency_code': 'PEN',
              'email': partner.email, 'capture': True, 'reference_code': 'QA20',
              'outcome': {'type': 'venta_exitosa', 'code': 'AUT0000', 'user_message': 'ok'},
              'source': {'object': 'token', 'id': token, 'type': 'card', 'last_four': '1111'}}
    with _p3_patch(_p3_API, return_value=charge) as api:
        tx.with_context(payment_safe_write=True)._process(tx._culqi_create_charge(token))
    igual(api.call_args.args[:2], ('POST', 'charges'), 'Llamada al endpoint charges (mock)')
    igual((tx.state, tx.provider_reference), ('done', 'chr_test_QA20P3'), 'Transacción confirmada')
    tx2 = registro(_p3_tx(prov, partner, 'card', 120.50, _p3_ref('CULQI2')), 'transacción importe alterado')
    with _p3_patch(_p3_API, return_value=dict(charge, amount=100)):
        tx2.with_context(payment_safe_write=True)._process(tx2._culqi_create_charge(token))
    igual(tx2.state, 'error', 'Cargo con importe distinto se rechaza')
    omitido('Cargo real contra api.culqi.com', 'sin credenciales de prueba')


ejecutar(_p3_culqi)

caso('al_payment_izipay', 'Proveedor Izipay en prueba: formToken, firma de la IPN y confirmación',
     'Proveedores de pago → Izipay: tienda y contraseña de prueba; el cliente paga en el formulario '
     'incrustado y llega la IPN firmada (simulada).')


def _p3_izipay():
    from odoo.addons.al_payment_izipay.controllers.main import IzipayController
    password = 'testpassword_qa2000000000'
    prov = registro(_p3_provider('izipay', {
        'izipay_shop_id': '89289758', 'izipay_password': password,
        'izipay_public_key': '89289758:testpublickey_qa2000000000'}), 'proveedor (test)')
    igual(prov._build_request_auth(), ('89289758', password), 'Autenticación básica tienda/contraseña')
    check(prov.izipay_webhook_url.endswith('/payment/izipay/webhook'), 'URL de IPN', prov.izipay_webhook_url)
    partner = registro(_p3_pay_partner(vat='20131312955'))
    ref = _p3_ref('IZI')
    tx = registro(_p3_tx(prov, partner, 'card', 120.50, ref), 'transacción')
    answer_tok = {'formToken': 'QA20FORMTOKEN', '_type': 'V4/Charge/PaymentForm'}
    with _p3_patch(_p3_API, return_value=answer_tok) as api:
        values = tx._get_processing_values()
    payload = api.call_args.kwargs['json']
    igual((payload['amount'], payload['currency'], payload['metadata']), (12050, 'PEN', {'odoo_reference': ref}),
          'Payload CreatePayment')
    igual(payload['customer']['billingDetails']['identityCode'], '20131312955', 'RUC del cliente en el payload')
    igual(values['izipay_form_token'], 'QA20FORMTOKEN', 'formToken al navegador')
    check(password not in str(values), 'La contraseña no llega al navegador')
    uuid = 'qa20p3uuid0000000000000000000001'
    trx = {'shopId': '89289758', 'uuid': uuid, 'amount': 12050, 'currency': 'PEN', 'paymentMethodType': 'CARD',
           'status': 'PAID', 'detailedStatus': 'AUTHORISED', 'operationType': 'DEBIT',
           'creationDate': '2026-10-30T10:00:00+00:00', 'metadata': {'odoo_reference': ref},
           'transactionDetails': {'cardDetails': {'effectiveBrand': 'VISA'}}, '_type': 'V4/PaymentTransaction'}
    answer = {'shopId': '89289758', 'orderCycle': 'CLOSED', 'orderStatus': 'PAID',
              'orderDetails': {'orderTotalAmount': 12050, 'orderCurrency': 'PEN', 'orderId': tx._izipay_order_id()},
              'transactions': [trx], '_type': 'V4/Payment'}
    raw = _p3_json.dumps(answer)
    data = {'kr-answer': raw, 'kr-hash-key': 'password', 'kr-hash-algorithm': 'sha256_hmac',
            'kr-hash': _p3_hmac.new(password.encode(), raw.encode(), _p3_hashlib.sha256).hexdigest()}
    try:
        IzipayController._verify_signature(data, tx)
        check(True, 'Firma HMAC-SHA256 de la IPN válida')
    except Exception as exc:  # noqa: BLE001
        check(False, 'Firma HMAC-SHA256 de la IPN válida', exc)
    try:
        IzipayController._verify_signature(dict(data, **{'kr-hash': 'x' * 64}), tx)
        check(False, 'IPN con firma alterada rechazada')
    except Exception as exc:  # noqa: BLE001
        check(type(exc).__name__ == 'Forbidden', 'IPN con firma alterada rechazada')
    pdata = tx._izipay_payment_data_from_answer(answer)
    igual(pdata['reference'], ref, 'La IPN ubica la transacción por metadata')
    tx.with_context(payment_safe_write=True)._process(pdata)
    igual((tx.state, tx.provider_reference), ('done', uuid), 'Transacción confirmada por la IPN')
    omitido('Llamada real a api.micuentaweb.pe', 'sin credenciales de prueba')


ejecutar(_p3_izipay)

caso('al_payment_niubiz', 'Proveedor Niubiz en prueba: autorización aprobada y rechazada (mock)',
     'Proveedores de pago → Niubiz: comercio y llaves de integración; el cliente paga con tarjeta '
     'en el botón de pago (autorización simulada).')


def _p3_resp(status=200, json_data=None, text=''):
    import requests as _rq
    r = _p3_MagicMock(status_code=status, text=text or str(json_data))
    r.json.return_value = json_data or {}
    r.raise_for_status.side_effect = None if status < 400 else _rq.exceptions.HTTPError(str(status))
    return r


def _p3_niubiz():
    REQ = 'odoo.addons.al_payment_niubiz.models.payment_provider.requests'
    jwt = 'eyJhbGciOiJIUzI1NiJ9.qa20'
    prov = registro(_p3_provider('niubiz', {
        'niubiz_merchant_id': '456879852', 'niubiz_access_key': 'integraciones@niubiz.com.pe',
        'niubiz_secret_key': 'secreto-qa20', 'niubiz_ruc': '20557912879'}), 'proveedor (test)')
    igual(sorted(prov._get_supported_currencies().mapped('name')), ['PEN', 'USD'], 'Monedas PEN/USD')
    partner = registro(_p3_pay_partner(phone=False))
    tx = registro(_p3_tx(prov, partner, 'card', 150.0, _p3_ref('NBZ'), operation='online_redirect'), 'transacción')
    with _p3_patch(REQ + '.request', return_value=_p3_resp(200, {'sessionKey': 'S1'})) as post:
        prov._niubiz_get_session_token(jwt, tx)
    body = post.call_args.kwargs['json']
    igual(body['dataMap']['cardholderPhoneNumber'], '000000000', 'Sesión sin teléfono usa 000000000')
    approved = {'header': {'ecoreTransactionUUID': 'qa20', 'ecoreTransactionDate': 1791232000000},
                'order': {'actionCode': '000', 'authorizationCode': '173424', 'traceNumber': '75',
                          'purchaseNumber': '1'}, 'dataMap': {'STATUS': 'Authorized', 'BRAND': 'visa'}}
    with _p3_patch(REQ + '.post', return_value=_p3_resp(200, approved)):
        data = prov._niubiz_authorize(jwt, 'TKN', tx)
    tx.with_context(payment_safe_write=True)._process({**data, 'reference': tx.reference})
    igual((tx.state, tx.provider_reference, tx.niubiz_trace_number), ('done', '173424', '75'),
          'Autorización aprobada confirma la transacción')
    tx2 = registro(_p3_tx(prov, partner, 'card', 150.0, _p3_ref('NBZ2'), operation='online_redirect'),
                   'transacción rechazada')
    declined = {'errorCode': 400, 'errorMessage': 'NOT AUTHORIZED',
                'data': {'ACTION_CODE': '116', 'STATUS': 'Not Authorized', 'BRAND': 'visa', 'TRACE_NUMBER': '76'}}
    with _p3_patch(REQ + '.post', return_value=_p3_resp(400, declined)):
        data2 = prov._niubiz_authorize(jwt, 'TKN', tx2)
    tx2.with_context(payment_safe_write=True)._process({**data2, 'reference': tx2.reference})
    igual(tx2.state, 'error', 'Autorización rechazada → error')
    check('Fondos insuficientes' in (tx2.state_message or ''), 'Mensaje de código 116 traducido', tx2.state_message)
    omitido('Llamada real a la API de Niubiz', 'sin credenciales de prueba')


ejecutar(_p3_niubiz)

caso('al_payment_pagoefectivo', 'Proveedor PagoEfectivo en prueba: firma de autorización, CIP y notificación firmada',
     'Proveedores de pago → PagoEfectivo: servicio y claves de prueba; el cliente genera un CIP en el '
     'portal y llega la notificación de pago firmada (simulada).')


def _p3_pagoefectivo():
    from odoo.addons.al_payment_pagoefectivo.controllers.main import PagoEfectivoController
    secret = 'secreto-qa20-p3'
    prov = registro(_p3_provider('pagoefectivo', {
        'pagoefectivo_service_id': '1035', 'pagoefectivo_access_key': 'clave-acceso-qa20',
        'pagoefectivo_secret_key': secret}), 'proveedor (test)')
    igual(prov._build_request_url('cips'), 'https://pre1a.services.pagoefectivo.pe/v1/cips',
          'URL del entorno de pruebas')
    auth = {'token': 'eyJ.qa20', 'codeService': '1035'}
    calls = []
    cip_data = {}

    def _fake(method, endpoint, **kw):
        calls.append((endpoint, kw))
        return auth if endpoint == 'authorizations' else cip_data
    with _p3_patch(_p3_API, _p3_Mock(side_effect=_fake)):
        token = prov._pagoefectivo_authorize()
    pl = calls[0][1]['json']
    expected = _p3_hashlib.sha256(('1035.clave-acceso-qa20.%s.%s' % (secret, pl['dateRequest'])).encode()).hexdigest()
    igual(token, 'eyJ.qa20', 'Token de autorización')
    igual(pl['hashString'], expected, 'hashString SHA-256 de servicio.clave.secreto.fecha')
    check(secret not in _p3_json.dumps(pl), 'El secreto no viaja en el payload')
    partner = registro(_p3_pay_partner(phone='987 654 321', additional_identifiers={'PE_DNI': '45678912'}))
    ref = _p3_ref('PEF')
    tx = registro(_p3_tx(prov, partner, 'pagoefectivo', 120.50, ref, operation='online_redirect'), 'transacción')
    cip_data.update({'cip': 2834561, 'currency': 'PEN', 'amount': 120.5, 'transactionCode': tx._pagoefectivo_transaction_code()
                if hasattr(tx, '_pagoefectivo_transaction_code') else ref.replace('/', '-'),
                'dateExpiry': '2026-11-01T10:00:00-05:00',
                'cipUrl': 'https://pre1a.payment.pagoefectivo.pe/PE/Checkout/Cip?token=qa20&lang=es'})
    calls.clear()
    with _p3_patch(_p3_API, _p3_Mock(side_effect=_fake)):
        rv = tx._get_specific_rendering_values({})
    igual([c[0] for c in calls], ['authorizations', 'cips'], 'Autoriza y genera el CIP')
    cp = calls[1][1]['json']
    igual((cp['amount'], cp['currency'], cp['additionalData'], cp['userPhone'], cp['userCodeCountry']),
          (120.5, 'PEN', ref, '987654321', '+51'), 'Payload del CIP')
    igual((cp.get('userDocumentType'), cp.get('userDocumentNumber')), ('DNI', '45678912'), 'DNI como documento')
    igual((tx.state, tx.provider_reference), ('pending', '2834561'), 'Transacción pendiente con el CIP')
    igual(rv.get('api_url'), cip_data['cipUrl'], 'Redirección a la URL del CIP')
    notif = {'eventType': 'cip.paid', 'operationNumber': 9123,
             'data': {'cip': 2834561, 'currency': 'PEN', 'amount': 120.5,
                      'paymentDate': '2026-10-30T15:20:11-05:00', 'transactionCode': cp['transactionCode']}}
    body = _p3_json.dumps(notif, indent=2).encode()
    compact = _p3_json.dumps(notif, separators=(',', ':')).encode()
    sig = _p3_hmac.new(secret.encode(), compact, _p3_hashlib.sha256).hexdigest().upper()
    try:
        PagoEfectivoController._verify_signature(body, sig, tx)
        check(True, 'Firma PE-Signature sobre JSON compacto aceptada')
    except Exception as exc:  # noqa: BLE001
        check(False, 'Firma PE-Signature sobre JSON compacto aceptada', exc)
    try:
        PagoEfectivoController._verify_signature(body, 'a' * 64, tx)
        check(False, 'Notificación con firma inválida rechazada')
    except Exception as exc:  # noqa: BLE001
        check(type(exc).__name__ == 'Forbidden', 'Notificación con firma inválida rechazada')
    found = env['payment.transaction'].sudo()._search_by_reference('pagoefectivo', notif)
    igual(found, tx, 'La notificación ubica la transacción por el CIP')
    tx.with_context(payment_safe_write=True)._process(notif)
    igual(tx.state, 'done', 'CIP pagado confirma la transacción')
    omitido('Llamada real a services.pagoefectivo.pe', 'sin credenciales de prueba')


ejecutar(_p3_pagoefectivo)

# ============================================================ cash_forecast
caso('al_l10n_pe_cash_forecast', 'Flujo de caja proyectado: saldo inicial, partidas por vencimiento, escenario y XLSX',
     'Contabilidad → Flujo de caja proyectado → Nuevo: 12 semanas; revisar cobranzas/pagos por '
     'semana, mover una partida, agregar una manual y exportar a Excel.')


def _p3_cash_forecast():
    today = fields.Date.context_today(env['res.partner'])
    partner = registro(_p3_partner('Socio flujo'))
    outstanding = env['account.account'].create({
        'name': qa_name('P3 Pendientes flujo'), 'code': '104196', 'account_type': 'asset_current',
        'reconcile': True})
    bank = env['account.journal'].create({'name': qa_name('P3 Banco flujo'), 'code': 'Q3BF', 'type': 'bank',
                                          'company_id': company.id})
    (bank.inbound_payment_method_line_ids | bank.outbound_payment_method_line_ids).payment_account_id = outstanding
    restricted = env['account.journal'].create({
        'name': qa_name('P3 Detracciones BN'), 'code': 'Q3BN', 'type': 'bank', 'company_id': company.id,
        'l10n_pe_forecast_exclude': True})
    sale_j = env['account.journal'].create({'name': qa_name('P3 Ventas flujo'), 'code': 'Q3VF', 'type': 'sale',
                                            'l10n_latam_use_documents': False, 'company_id': company.id})
    pur_j = env['account.journal'].create({'name': qa_name('P3 Compras flujo'), 'code': 'Q3CF', 'type': 'purchase',
                                           'l10n_latam_use_documents': False, 'company_id': company.id})
    registro(bank | restricted | sale_j | pur_j, 'diario')
    misc = env['account.journal'].search([('company_id', '=', company.id), ('type', '=', 'general')], limit=1)
    equity = env['account.account'].search([('account_type', '=', 'equity'),
                                            ('company_ids', 'in', company.root_id.id)], limit=1)

    def _deposit(journal, amount):
        m = env['account.move'].create({'move_type': 'entry', 'journal_id': misc.id,
                                        'date': today - _p3_td(days=3), 'line_ids': [
            Command.create({'account_id': journal.default_account_id.id, 'balance': amount}),
            Command.create({'account_id': equity.id, 'balance': -amount})]})
        m.action_post()
        return m

    def _doc(mtype, amount, due):
        m = env['account.move'].create({
            'move_type': mtype, 'partner_id': partner.id,
            'journal_id': (sale_j if mtype.startswith('out') else pur_j).id,
            'invoice_date': today - _p3_td(days=40), 'invoice_date_due': due,
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})]})
        m.action_post()
        return m
    base = env['l10n_pe.cash.forecast'].create({'name': qa_name('P3 base')})
    opening0, restricted0 = base.opening_balance, base.restricted_balance
    base.unlink()
    registro(_deposit(bank, 10000) | _deposit(restricted, 500), 'saldo de bancos')
    inv = _doc('out_invoice', 1200, today + _p3_td(days=9))
    bill = _doc('in_invoice', 800, today + _p3_td(days=20))
    overdue = _doc('out_invoice', 300, today - _p3_td(days=15))
    registro(inv | bill | overdue, 'documento proyectado')
    fc = registro(env['l10n_pe.cash.forecast'].create({'name': qa_name('P3 Flujo 12 semanas')}), 'flujo')
    igual(fc.opening_balance - opening0, 10000.0, 'Saldo inicial suma el banco disponible')
    igual(fc.restricted_balance - restricted0, 500.0, 'Fondos restringidos (detracciones) excluidos')
    periods = fc.period_ids.sorted('sequence')
    igual(len(periods), 13, '12 semanas y «Desde…»')

    def _line(m):
        return fc.line_ids.filtered(lambda l: l.move_id == m)
    il, bl, ol = _line(inv), _line(bill), _line(overdue)
    igual((il.category, il.amount), ('receivable', 1200.0), 'Cobranza proyectada')
    igual((bl.category, bl.amount), ('payable', -800.0), 'Pago proyectado')
    check(ol.is_overdue and ol.date_expected == fc.date_from and ol.period_id == periods[0],
          'Vencido se proyecta en el primer periodo')
    check(il.period_id.date_start <= il.date_expected <= (il.period_id.date_end or il.date_expected),
          'Partida en el periodo de su vencimiento')
    igual(fc.closing_balance, fc.opening_balance + sum(fc.line_ids.mapped('amount')), 'Saldo final encadenado')
    later = today + _p3_td(days=45)
    il.write({'date_expected': later, 'amount': 600})
    check(il.is_edited, 'Partida editada marcada como escenario')
    fc.action_refresh()
    il = _line(inv)
    igual((il.date_expected, il.amount, il.is_edited), (later, 600.0, True), 'El escenario sobrevive al refrescar')
    fc.line_ids = [Command.create({'name': 'Planilla de noviembre', 'amount': -3000,
                                   'date_expected': today + _p3_td(days=25)})]
    manual = fc.line_ids.filtered(lambda l: l.category == 'manual')
    fc.action_refresh()
    check(manual in fc.line_ids and manual.period_id, 'Partida manual se conserva con periodo')
    action = fc.action_export_xlsx()
    att = env['ir.attachment'].search([('res_model', '=', fc._name), ('res_id', '=', fc.id)])
    registro(att, 'XLSX exportado')
    check(action['type'] == 'ir.actions.act_url' and att.name.endswith('.xlsx') and att.file_size > 1000,
          'Exporta el flujo a XLSX', '%s (%s bytes)' % (att.name, att.file_size))


ejecutar(_p3_cash_forecast)

# -*- coding: utf-8 -*-
"""Cronograma de un préstamo bancario.

Funciones puras (sin ORM) para que el cálculo se pruebe solo. Convenciones de
la banca peruana:

* La tasa es la **TEA**; el interés de cada cuota es el del número real de días
  del periodo: ``saldo × ((1 + TEA)^(días / base) − 1)`` con base 360 o 365.
* **Francés** (cuota fija): la cuota iguala el valor presente de las cuotas al
  saldo, descontando cada una con el factor de sus días; así la cuota queda fija
  aunque los meses tengan distinta duración.
* **Alemán**: amortización constante; **al vencimiento**: solo intereses y el
  capital en la última cuota.
* **Periodo de gracia**: *parcial*, se pagan solo los intereses; *total*, no se
  paga nada y los intereses se suman al capital.
* El seguro de desgravamen es una tasa mensual sobre el saldo; la comisión, un
  importe fijo por cuota.
"""
from dateutil.relativedelta import relativedelta


def period_rate(tea, days, basis):
    """Tasa efectiva de ``days`` días a partir de la TEA (en %)."""
    return (1 + tea / 100.0) ** (days / float(basis)) - 1 if tea else 0.0


def due_dates(first_due, count, months):
    """Fechas de vencimiento: la primera y luego cada ``months`` meses (mismo día)."""
    return [first_due + relativedelta(months=months * index) for index in range(count)]


def build_schedule(principal, tea, basis, start, dates, method='french', grace_count=0, grace_type='none',
                   insurance_rate=0.0, fee=0.0, months=1, rounding=2, fixed_installment=None):
    """Devuelve una lista de cuotas (diccionarios) desde ``start`` con el saldo
    ``principal`` y los vencimientos ``dates``.

    ``fixed_installment`` mantiene una cuota francesa dada (prepago que reduce el
    plazo): se generan cuotas hasta cancelar el saldo y sobran las demás fechas.
    """
    def rnd(value):
        return round(value + 0.0, rounding)

    lines = []
    balance = principal
    previous = start
    count = len(dates)
    grace = min(grace_count if grace_type != 'none' else 0, max(count - 1, 0))
    rates, starts = [], []
    for due in dates:
        starts.append(previous)
        rates.append(period_rate(tea, (due - previous).days, basis))
        previous = due
    # Periodo de gracia.
    for index in range(grace):
        interest = rnd(balance * rates[index])
        insurance = rnd(balance * insurance_rate / 100.0 * months)
        line = {'date_start': starts[index], 'date_due': dates[index], 'balance_start': rnd(balance), 'principal': 0.0, 'interest': interest,
                'insurance': insurance, 'fee': fee, 'grace': True}
        if grace_type == 'total':
            # No se paga: el interés (y el seguro) se capitalizan.
            balance = rnd(balance + interest + insurance)
            line.update({'interest': 0.0, 'insurance': 0.0, 'fee': 0.0, 'capitalized': interest + insurance})
        line['balance_end'] = rnd(balance)
        lines.append(line)
    rest = list(range(grace, count))
    if not rest:
        return lines
    # Cuota francesa: saldo / Σ factores de descuento acumulados.
    installment = fixed_installment
    if method == 'french' and installment is None:
        discount, factor = 0.0, 1.0
        for index in rest:
            factor /= (1 + rates[index])
            discount += factor
        installment = balance / discount if discount else balance
    german_principal = balance / len(rest) if method == 'german' else 0.0
    for position, index in enumerate(rest):
        if balance <= 0:
            break
        interest = rnd(balance * rates[index])
        insurance = rnd(balance * insurance_rate / 100.0 * months)
        last = position == len(rest) - 1
        if method == 'french':
            principal_part = rnd(installment - interest)
        elif method == 'german':
            principal_part = rnd(german_principal)
        else:
            principal_part = 0.0
        if last or principal_part >= balance:
            principal_part = rnd(balance)
        balance_start = rnd(balance)
        balance = rnd(balance - principal_part)
        lines.append({'date_start': starts[index], 'date_due': dates[index], 'balance_start': balance_start, 'principal': principal_part,
                      'interest': interest, 'insurance': insurance, 'fee': fee, 'grace': False,
                      'balance_end': balance})
    return lines


def irr_annual(cash_flows, basis=360, guess=0.1):
    """TCEA: tasa efectiva anual que iguala a cero los flujos ``[(días desde el
    desembolso, importe)]`` (Newton; ``None`` si no converge)."""
    rate = guess
    for _iteration in range(100):
        npv = sum(amount / (1 + rate) ** (days / float(basis)) for days, amount in cash_flows)
        derivative = sum(-days / float(basis) * amount / (1 + rate) ** (days / float(basis) + 1)
                         for days, amount in cash_flows)
        if not derivative:
            return None
        new_rate = rate - npv / derivative
        if new_rate <= -0.99:
            new_rate = (rate - 0.99) / 2
        if abs(new_rate - rate) < 1e-10:
            return new_rate
        rate = new_rate
    return None

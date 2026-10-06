"""Validación de al_payment_culqi contra el sandbox real de Culqi.

Crea tokens con las tarjetas de prueba oficiales
(https://docs.culqi.com/es/documentacion/pagos-online/tarjetas-de-prueba) por
la API de tokens (``secure.culqi.com/v2/tokens``, solo para validar: en la
tienda los tokens los crea el Checkout en el navegador) y los cobra con el
flujo del módulo. En Odoo todo se deshace al final; en el sandbox de Culqi
quedan los cargos de prueba.

Las llaves de integración se leen de variables de entorno (no se guardan)::

    CULQI_PK=pk_test_… CULQI_SK=sk_test_… \\
    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < docs/culqi/validar_sandbox.py
"""
import os

import requests

PK, SK = os.environ.get('CULQI_PK'), os.environ.get('CULQI_SK')
assert PK and SK and PK.startswith('pk_test_') and SK.startswith('sk_test_'), \
    'Defina CULQI_PK y CULQI_SK con las llaves de integración (pk_test_/sk_test_).'

env = env  # noqa: F821 (lo inyecta odoo-bin shell)
company = env.ref('base.main_company')
env = env(context=dict(env.context, allowed_company_ids=[company.id]))

# (tarjeta, mes, año, cvv, monto, moneda, resultado esperado)
CASOS = [
    ('Visa débito', '4111111111111111', '09', '2030', '123', 120.50, 'PEN', 'done'),
    ('Visa crédito', '4111111110101113', '09', '2030', '123', 75.00, 'PEN', 'done'),
    ('Mastercard', '5111111111111118', '12', '2030', '039', 35.90, 'USD', 'done'),
    ('Amex', '371212121212122', '12', '2030', '2841', 49.99, 'PEN', 'done'),
    ('Diners', '36001212121210', '12', '2030', '964', 15.00, 'PEN', 'done'),
    ('Robada (stolen_card)', '4000020000000000', '10', '2030', '354', 20.00, 'PEN', 'error'),
    ('Fondos insuficientes', '4000040000000008', '03', '2030', '295', 20.00, 'PEN', 'error'),
    ('CVV incorrecto', '5400020000000003', '07', '2030', '203', 20.00, 'PEN', 'error'),
    ('3DS con desafío (Visa)', '4456530000001096', '07', '2030', '111', 60.00, 'PEN', 'review'),
]

provider = env.ref('al_payment_culqi.payment_provider_culqi')
provider.write({'culqi_public_key': PK, 'culqi_secret_key': SK, 'state': 'test',
                'company_id': company.id})
partner = env['res.partner'].create({
    'name': 'Rosa María Quispe Huamán', 'email': 'rosa.quispe@example.com', 'phone': '987654321',
    'street': 'Av. Arequipa 123', 'city': 'Lima', 'country_id': env.ref('base.pe').id})
card = env.ref('payment.payment_method_card')


def token(number, month, year, cvv):
    response = requests.post('https://secure.culqi.com/v2/tokens', timeout=20, headers={
        'Authorization': f'Bearer {PK}', 'Content-Type': 'application/json'}, json={
        'card_number': number, 'cvv': cvv, 'expiration_month': month,
        'expiration_year': year, 'email': partner.email})
    data = response.json()
    assert response.status_code in (200, 201), data
    return data['id']


resultados = []
try:
    for name, number, month, year, cvv, amount, currency, expected in CASOS:
        currency_rec = env.ref(f'base.{currency}')
        currency_rec.active = True
        tx = env['payment.transaction'].create({
            'provider_id': provider.id, 'payment_method_id': card.id, 'amount': amount,
            'currency_id': currency_rec.id, 'partner_id': partner.id, 'operation': 'online_direct',
            'reference': env['payment.transaction']._compute_reference('culqi', prefix='VAL'),
        })
        data = tx._culqi_create_charge(token(number, month, year, cvv), device_id=None)
        if data.get('action_code') == 'REVIEW':
            got = 'review'
        else:
            tx._process('culqi', data)
            got = tx.state
        detail = tx.provider_reference or tx.state_message or data.get('user_message', '')
        refund = ''
        if got == 'done':
            refund_tx = tx._refund(amount_to_refund=round(amount / 2, 2))
            refund = f'devolución parcial {refund_tx.state} {refund_tx.provider_reference or refund_tx.state_message}'
        ok = 'OK ' if got == expected else 'FALLA'
        resultados.append(f'{ok} {name:26} {amount:>8} {currency}  esperado={expected:7} obtenido={got:7} {detail[:70]} {refund}')
finally:
    env.cr.rollback()
    print('\n'.join(resultados))

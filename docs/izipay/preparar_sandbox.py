"""Prepara (o revisa) la validación de Izipay en una base de prueba. Se ejecuta
con ``odoo-bin shell``::

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/izipay/preparar_sandbox.py

Sin variables, pone el proveedor Izipay en «Modo de prueba» con las claves de
la tienda de prueba pública de la documentación de Izipay (89289758) y
publicado. Imprime un enlace de pago de una factura abierta en soles (o, si no
hay, un enlace de /payment/pay con referencia DEMO-IZIPAY/…).

Variables de entorno:

- ``IZIPAY_BASE_URL``: URL del servidor de prueba (por defecto
  http://127.0.0.1:18069).
- ``IZIPAY_REFUND=<referencia>:<importe>``: devuelve ese importe de la
  transacción (los tres caminos de ``_send_refund_request``).
- ``IZIPAY_SHOW=<referencia>``: muestra el estado de la transacción y sus
  devoluciones.
- ``IZIPAY_DISABLE=1``: deja el proveedor deshabilitado y sin claves.

Las claves de prueba son públicas: las publica la documentación oficial
(contraseña) y su playground (clave pública). No cobran.
"""
import os
import time

from odoo.addons.payment import utils as payment_utils

SHOP_ID = '89289758'
PASSWORD = 'testpassword_7vAtvN49E8Ad6e6ihMqIOvOHC6QV5YKmIXgxisMm0V7Eq'
PUBLIC_KEY = '89289758:testpublickey_TxzPjl9xKlhM0a6tfSVNilcLTOUZ0ndsTogGTByPUATcE'
BASE_URL = os.environ.get('IZIPAY_BASE_URL', 'http://127.0.0.1:18069')

provider = env.ref('al_payment_izipay.payment_provider_izipay')  # noqa: F821 (odoo shell)
Tx = env['payment.transaction']  # noqa: F821


def show(reference):
    tx = Tx.search([('reference', '=', reference)])
    for record in tx | Tx.search([('source_transaction_id', '=', tx.id)]):
        print(f'{record.reference}: {record.state} {record.amount} {record.currency_id.name} '
              f'ref={record.provider_reference} metodo={record.payment_method_id.code} '
              f'pago={record.payment_id.name or "-"} msg={record.state_message or ""}')


if os.environ.get('IZIPAY_DISABLE'):
    provider.write({'state': 'disabled', 'is_published': False})
    provider.sudo().write({'izipay_shop_id': False, 'izipay_password': False, 'izipay_public_key': False})
    env.cr.commit()  # noqa: F821
    print('Proveedor Izipay deshabilitado y sin claves.')
elif os.environ.get('IZIPAY_SHOW'):
    show(os.environ['IZIPAY_SHOW'])
elif os.environ.get('IZIPAY_REFUND'):
    reference, amount = os.environ['IZIPAY_REFUND'].rsplit(':', 1)
    tx = Tx.search([('reference', '=', reference)])
    refund = tx._refund(amount_to_refund=float(amount))
    env.cr.commit()  # noqa: F821
    show(reference)
    print('Devolución:', refund.reference, refund.state, refund.state_message or '')
else:
    provider.sudo().write({
        'izipay_shop_id': SHOP_ID,
        'izipay_password': PASSWORD,
        'izipay_public_key': PUBLIC_KEY,
    })
    provider.write({'state': 'test', 'is_published': True})
    if not provider.journal_id:
        provider.journal_id = env['account.journal'].search(  # noqa: F821
            [('type', '=', 'bank'), ('company_id', '=', provider.company_id.id)], limit=1)
    pen = env.ref('base.PEN')  # noqa: F821
    invoice = env['account.move'].search([  # noqa: F821
        ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
        ('payment_state', 'in', ('not_paid', 'partial')), ('currency_id', '=', pen.id),
        ('company_id', '=', provider.company_id.id), ('partner_id.email', '!=', False),
    ], order='amount_residual asc', limit=1)
    # El portal de facturas de ol_pe_v19 pide iniciar sesión: se paga con
    # /payment/pay firmado (con invoice_id, el pago se concilia con la factura).
    if invoice:
        partner, amount, extra = invoice.partner_id, invoice.amount_residual, f'&invoice_id={invoice.id}'
        print('Factura:', invoice.name, partner.name, amount)
    else:
        partner = env['res.partner'].search([('email', '!=', False)], limit=1)  # noqa: F821
        amount, extra = 120.5, f'&reference=DEMO-IZIPAY/{int(time.time())}'
    token = payment_utils.generate_access_token(partner.id, amount, pen.id, env=env)  # noqa: F821
    link = (f'{BASE_URL}/payment/pay?amount={amount}&currency_id={pen.id}'
            f'&partner_id={partner.id}&access_token={token}{extra}')
    env.cr.commit()  # noqa: F821
    print('Proveedor Izipay en modo de prueba y publicado.')
    print('ENLACE', link)

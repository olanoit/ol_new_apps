"""Capturas de la ficha de al_payment_izipay: la configuración del proveedor.

02-pago y 03-formulario son las capturas 1 y 2 de docs/izipay/validar_sandbox.py
(pago real en la tienda de prueba pública de Izipay desde /payment/pay, con
el proveedor preparado por docs/izipay/preparar_sandbox.py).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_payment_izipay') as c:
    c.abrir('/odoo/action-payment.action_payment_provider', ms=2500)
    provider = c.page.evaluate("""() => fetch('/web/dataset/call_kw', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jsonrpc: '2.0', method: 'call',
        params: {model: 'payment.provider', method: 'search', args: [[['code', '=', 'izipay']]], kwargs: {limit: 1}}})
    }).then(r => r.json()).then(r => r.result[0])""")
    c.abrir_registro('payment.provider', provider, ms=3000)
    c.foto('01-ajustes', selector='.o_form_sheet_bg')

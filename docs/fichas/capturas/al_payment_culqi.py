"""Capturas de la ficha de al_payment_culqi: la configuración del proveedor.

02-pago, 03-checkout y 04-yape se tomaron en /payment/pay con el proveedor en
modo de prueba y llaves de formato válido pero ficticias: Culqi muestra su
ventana de pago, pero no se puede cobrar con ellas. El pago real (incluido
3DS) requiere las llaves de integración del cliente (pk_test/sk_test).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_payment_culqi') as c:
    c.abrir('/odoo/action-payment.action_payment_provider', ms=2500)
    provider = c.page.evaluate("""() => fetch('/web/dataset/call_kw', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jsonrpc: '2.0', method: 'call',
        params: {model: 'payment.provider', method: 'search', args: [[['code', '=', 'culqi']]], kwargs: {limit: 1}}})
    }).then(r => r.json()).then(r => r.result[0])""")
    c.abrir_registro('payment.provider', provider, ms=3000)
    c.foto('01-ajustes', selector='.o_form_sheet_bg')

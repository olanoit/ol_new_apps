"""Capturas de backend de la ficha de al_payment_niubiz.

Las capturas del pago (modal, tarjeta, aprobado, rechazado) salen del pago
real contra el sandbox con docs/niubiz/validar_sandbox_e2e.py. Aquí: la
configuración del proveedor y la transacción DEMO-NIUBIZ-OK3, anulada en el
sandbox el mismo día.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402


def buscar(c, model, domain):
    return c.page.evaluate("""([model, domain]) => fetch('/web/dataset/call_kw', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
            model, method: 'search', args: [domain], kwargs: {limit: 1}}})
    }).then(r => r.json()).then(r => r.result[0])""", [model, domain])


with Captura('al_payment_niubiz') as c:
    c.abrir('/odoo/action-payment.action_payment_provider', ms=2500)
    provider = buscar(c, 'payment.provider', [['code', '=', 'niubiz']])
    c.abrir_registro('payment.provider', provider, ms=3000)
    c.foto('01-ajustes', selector='.o_form_sheet_bg')
    tx = buscar(c, 'payment.transaction', [['reference', '=', 'DEMO-NIUBIZ-OK3']])
    c.abrir_registro('payment.transaction', tx, ms=3000)
    c.foto('06-anulacion', selector='.o_form_sheet_bg')

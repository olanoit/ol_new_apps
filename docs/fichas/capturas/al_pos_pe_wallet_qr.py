"""Capturas de la ficha de al_pos_pe_wallet_qr con los datos DEMO de
docs/tpv_pe/preparar_demo_qr.py: la cuenta bancaria con su QR y el método de
pago. 03-qr es la captura del cobro en el TPV (Playwright, caja «DEMO TPV
Yape»)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402


def search_id(c, model, domain):
    return c.page.evaluate("""([model, domain]) => fetch('/web/dataset/call_kw', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jsonrpc: '2.0', method: 'call',
        params: {model, method: 'search', args: [domain], kwargs: {limit: 1}}})
    }).then(r => r.json()).then(r => r.result[0])""", [model, domain])


with Captura('al_pos_pe_wallet_qr') as c:
    c.abrir('/odoo', ms=2000)
    bank = search_id(c, 'res.partner.bank', [['acc_number', '=', 'DEMO-YAPE-0001']])
    c.abrir_registro('res.partner.bank', bank, ms=2500)
    c.texto('QR de billetera', ms=1200)
    c.foto('01-cuenta', selector='.o_form_sheet_bg')
    method = search_id(c, 'pos.payment.method', [['name', '=', 'DEMO Yape / Plin']])
    c.abrir_registro('pos.payment.method', method, ms=2500)
    c.foto('02-metodo', selector='.o_form_sheet_bg')

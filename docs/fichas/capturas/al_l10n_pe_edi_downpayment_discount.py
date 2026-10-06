"""Capturas de la ficha de al_l10n_pe_edi_downpayment_discount.

Usa el caso DEMO de ol_pe_v19 (cliente «DEMO Constructora Andina S.A.C.»):
pedido con un servicio gravado y uno exonerado, anticipo del 20 %, factura
final que lo deduce y nota de crédito de esa factura. Los registros se buscan
por el cliente DEMO; no se modifican.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

CLIENTE = 'DEMO Constructora Andina S.A.C.'


def buscar(c, model, domain, order='id desc'):
    return c.page.evaluate("""([model, domain, order]) => fetch('/web/dataset/call_kw', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
            model, method: 'search_read', args: [domain, ['id', 'name']], kwargs: {order, limit: 5}}})
    }).then(r => r.json()).then(r => r.result)""", [model, domain, order])


with Captura('al_l10n_pe_edi_downpayment_discount') as c:
    p = c.page
    c.abrir('/odoo/action-account.action_move_out_invoice_type', ms=2500)
    pedido = buscar(c, 'sale.order', [['partner_id.name', '=', CLIENTE]])[0]
    facturas = buscar(c, 'account.move', [['partner_id.name', '=', CLIENTE], ['move_type', '=', 'out_invoice'],
                                          ['state', '=', 'posted']], order='id asc')
    anticipo, final = facturas[-2], facturas[-1]
    nota = buscar(c, 'account.move', [['partner_id.name', '=', CLIENTE], ['move_type', '=', 'out_refund'],
                                      ['state', '=', 'posted']])[0]

    # 1. Pedido con sus facturas: anticipo y factura final
    c.abrir_registro('sale.order', pedido['id'], ms=2500)
    p.get_by_role('button', name='Crear factura').first.click()
    p.wait_for_selector('.modal-content', timeout=20000)
    c.esperar(800)
    c.foto('01-crear-factura', selector='.modal-content')
    p.keyboard.press('Escape')
    c.esperar(600)

    # Aviso del estado de envío al OSE: depende del entorno, no del módulo.
    SIN_AVISO = "() => document.querySelectorAll('.o_form_sheet_bg > .alert').forEach(e => e.remove())"

    # 2. Factura final: servicio gravado, exonerado y deducción del anticipo
    c.abrir_registro('account.move', final['id'], ms=3000)
    c.js(SIN_AVISO)
    c.foto('02-factura-final', selector='.o_form_sheet_bg')

    # 3. Nota de crédito de la factura final, ya publicada
    c.abrir_registro('account.move', nota['id'], ms=3000)
    c.js(SIN_AVISO)
    c.foto('03-nota-credito', selector='.o_form_sheet_bg')

# -*- coding: utf-8 -*-
"""Capturas de la ficha de al_l10n_pe_cpe_validation (datos DEMO CPE:
tools/cpe_validation_demo_data.py). FICHAS_URL=http://127.0.0.1:19791"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_l10n_pe_cpe_validation', viewport={'width': 1440, 'height': 900}) as c:
    p = c.page
    ids = c.js("""(async () => (await (await fetch('/web/dataset/call_kw', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jsonrpc: '2.0',
        params: {model: 'account.move', method: 'search_read', args: [[['move_type', '=', 'in_invoice'],
        ['ref', 'in', ['F002-00000318', 'F001-00009910']]]], kwargs: {fields: ['ref']}}})})).json()).result)()""")
    by_ref = {row['ref']: row['id'] for row in ids}
    # 1. Lista de facturas de proveedor con la columna SUNAT.
    c.abrir_accion('account.action_move_in_invoice_type', 2500)
    p.locator('.o_searchview_input').fill('DEMO CPE')
    p.keyboard.press('Enter'); c.esperar(1500)
    c.foto('01-lista', selector='.o_list_renderer')
    # 2. Factura con resultado no válido: pestaña Otra información.
    for name, move_id in (('02-no-valido', by_ref['F001-00009910']),
                          ('03-observado', by_ref['F002-00000318'])):
        c.abrir_registro('account.move', move_id, 2500)
        p.locator('a[name="other_info"]').first.click(); c.esperar(800)
        p.get_by_text('Validez en SUNAT').first.scroll_into_view_if_needed(); c.esperar(400)
        c.foto(name, selector='.o_form_sheet_bg')
    # 3. Ajustes ▸ Perú ▸ Consulta de comprobantes.
    c.abrir('/odoo/settings#al_account_base', 3000)
    bar = p.get_by_text('Consulta de comprobantes', exact=True).first.locator('xpath=..')
    bar.scroll_into_view_if_needed(); c.esperar(600)
    content = bar.locator('xpath=following-sibling::*[1]')
    top, body = bar.bounding_box(), content.bounding_box()
    c.foto('04-ajustes', clip={'x': top['x'], 'y': top['y'], 'width': top['width'],
                                'height': body['y'] + body['height'] - top['y']}, recortar=False)

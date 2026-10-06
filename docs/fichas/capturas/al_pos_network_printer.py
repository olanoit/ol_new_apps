"""Capturas de la ficha de al_pos_network_printer (impresora de red ESC/POS).

Usa el punto de venta «DEMO TPV Vendedores» (id 23). Una impresora simulada
escucha en 127.0.0.1:9100 (un socket que guarda lo recibido), así «Probar
impresora» imprime de verdad. Al terminar, la caja vuelve a como estaba y se
borra la impresora de cocina DEMO.
"""
import socket
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

CONFIG = 23
FIELDS = ['escpos_network_printer_enabled', 'escpos_printer_ip', 'escpos_printer_port',
          'escpos_printer_mode', 'escpos_agent_url', 'escpos_agent_token',
          'escpos_auto_print', 'escpos_retry_queue_enabled']
received = bytearray()


def impresora_simulada():
    """Acepta conexiones en 9100 y acumula los bytes ESC/POS recibidos."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', 9100))
    srv.listen(5)

    def atender(conn):
        with conn:
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                received.extend(data)

    def bucle():
        while True:
            conn, _addr = srv.accept()
            threading.Thread(target=atender, args=(conn,), daemon=True).start()
    threading.Thread(target=bucle, daemon=True).start()


def rpc(c, model, method, args, kwargs=None):
    return c.page.evaluate("""([model, method, args, kwargs]) => fetch('/web/dataset/call_kw', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
            model, method, args, kwargs}})
    }).then(r => r.json()).then(r => { if (r.error) throw new Error(JSON.stringify(r.error)); return r.result; })""",
                           [model, method, args, kwargs or {}])


def bloque_ajustes(c):
    """Recorte del bloque «Impresora ESC/POS de red» de los Ajustes."""
    p = c.page
    p.locator('#al_escpos_network_printer').first.evaluate("e => e.scrollIntoView({block: 'start'})")
    p.mouse.wheel(0, -90)
    c.esperar(600)
    return c.js("""() => {
        const r = document.querySelector('#al_escpos_network_printer').getBoundingClientRect();
        return {x: r.x - 12, y: r.y - 12, width: r.width + 24, height: r.height + 24};
    }""")


impresora_simulada()
with Captura('al_pos_network_printer') as c:
    p = c.page
    antes = rpc(c, 'pos.config', 'read', [[CONFIG], FIELDS])[0]
    antes.pop('id', None)
    categ = rpc(c, 'pos.category', 'search', [[]], {'limit': 2})
    cocina = None
    try:
        rpc(c, 'pos.config', 'write', [[CONFIG], {
            'escpos_network_printer_enabled': True, 'escpos_printer_ip': '127.0.0.1',
            'escpos_printer_port': '9100', 'escpos_printer_mode': 'backend',
            'escpos_auto_print': True, 'escpos_retry_queue_enabled': True}])

        # 1. Ajustes ▸ Punto de venta ▸ Impresora ESC/POS de red (servidor)
        c.abrir('/odoo/settings#point_of_sale', ms=3500)
        c.foto('01-ajustes', clip=bloque_ajustes(c))

        # 2. «Probar impresora»: ticket de prueba en la impresora simulada
        p.get_by_role('button', name='Probar impresora').first.click()
        p.get_by_text('Ticket de prueba enviado').first.wait_for(timeout=20000)
        print('bytes recibidos por la impresora simulada:', len(received))
        c.foto('02-prueba', recortar=False)

        # 3. Modo «Agente local» (Odoo en la nube)
        rpc(c, 'pos.config', 'write', [[CONFIG], {
            'escpos_printer_mode': 'agent',
            'escpos_agent_url': 'https://agente-tienda1.ejemplo.com',
            'escpos_agent_token': 'DEMO-token-del-agente'}])
        p.reload()
        p.wait_for_selector('#al_escpos_network_printer', timeout=30000)
        c.esperar(1500)
        c.foto('03-agente', clip=bloque_ajustes(c))

        # 4. Impresora de preparación (cocina) ESC/POS
        cocina = rpc(c, 'pos.printer', 'create', [{
            'name': 'DEMO Cocina', 'printer_type': 'escpos_network',
            'escpos_printer_ip': '127.0.0.1', 'escpos_printer_port': '9100',
            'product_categories_ids': [(6, 0, categ)]}])
        c.abrir_registro('pos.printer', cocina, ms=2500)
        c.foto('04-cocina', selector='.o_form_sheet_bg')
    finally:
        if cocina:
            rpc(c, 'pos.printer', 'unlink', [[cocina]])
        rpc(c, 'pos.config', 'write', [[CONFIG], antes])

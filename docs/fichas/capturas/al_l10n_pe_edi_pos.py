"""Capturas de la ficha de al_l10n_pe_edi_pos (TPV «DEMO TPV Vendedores»).

La venta de demostración B002-00000004 (orden 48) se hizo una sola vez en la
sesión DEMO con «Emitir a SUNAT: No», así que su boleta quedó retenida y no
se envió. Este guion NO valida ventas: arma una orden, abre el diálogo del
comprobante y lo cancela; el recibo se toma reimprimiendo la orden ya pagada.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

TPV = 23                      # DEMO TPV Vendedores (sesión DEMO abierta)
ORDEN = 48                    # boleta B002-00000004, retenida
REFERENCIA = '2622-23-000001'  # referencia de la orden 48 en el TPV
BOLETA = 2414                 # account.move de la orden 48


def entrar_tpv(c):
    c.abrir('/pos/ui?config_id=%s' % TPV, ms=8000)
    if c.page.get_by_text('Desbloquear caja registradora', exact=True).count():
        c.texto('Desbloquear caja registradora', ms=2000)


with Captura('al_l10n_pe_edi_pos') as c:
    c.page.set_default_timeout(15000)

    # 1. Ajustes del TPV: diarios de boletas y facturas
    c.abrir('/odoo/action-point_of_sale.action_pos_configuration?pos_config_id=%s' % TPV, ms=3000)
    c.page.locator('#al_l10n_pe_edi_pos_journals').first.evaluate(
        "e => e.scrollIntoView({block: 'center'})")
    c.esperar(600)
    c.foto('01-ajustes', selector='#al_l10n_pe_edi_pos_journals', padding=16)

    # 2. Pantalla de pago con el botón del comprobante (orden sin validar)
    entrar_tpv(c)
    for producto in ['Gaseosa 500ml', 'Gaseosa 500ml', 'Bolsa plástica', 'Libro educativo']:
        c.page.locator('.product-list article, .product-list .product').filter(
            has_text=producto).first.click()
        c.esperar(500)
    c.page.get_by_role('button', name='Pago').first.click()
    c.esperar(1500)
    c.foto('02-pantalla-pago')

    # 3. Diálogo del comprobante: boleta, serie y «Emitir a SUNAT: No»
    c.clic('.alpe-doctype-button', ms=1200)
    c.page.locator('.alpe-serie-chip').filter(has_text='B002').first.click()
    c.esperar(400)
    c.page.locator('#alpe-send-switch').click()
    c.esperar(400)
    c.foto('03-comprobante', selector='.modal-content')

    # 4. Factura: exige cliente con RUC
    c.page.locator('.alpe-doctype-card').filter(has_text='Factura electrónica').first.click()
    c.esperar(400)
    c.page.locator('#alpe-send-switch').click()
    c.esperar(400)
    c.foto('04-factura', selector='.modal-content')
    c.page.locator('.modal-content button:has-text("Cancelar")').click()
    c.esperar(600)

    # 5. Ticket con formato CPE: reimpresión de la orden ya pagada
    c.texto('Órdenes', ms=2500)
    c.texto('Activo', ms=800)
    c.page.get_by_text('Pagado', exact=True).first.click()
    c.esperar(3000)
    c.page.get_by_text(REFERENCIA).first.click()
    c.esperar(2500)
    c.page.evaluate("window.print = () => {}")
    c.page.get_by_role('button', name='Imprimir recibo').first.click()
    c.esperar(3000)
    c.js("""(() => {
        const r = document.querySelector('.render-container');
        r.style.cssText = 'position:fixed;top:0;left:0;z-index:99999;background:#fff;'
            + 'padding:16px;display:block;visibility:visible;opacity:1;transform:none;'
            + 'width:auto;height:auto;overflow:visible';
        let p = r.parentElement;
        while (p && p !== document.body) { p.style.visibility = 'visible'; p.style.display = 'block'; p = p.parentElement; }
    })()""")
    c.esperar(800)
    c.foto('05-ticket', selector='.render-container', recortar=False)

    # 6. Orden en el backend: tipo, serie y emisión
    c.abrir('/odoo/action-point_of_sale.action_pos_pos_form/%s' % ORDEN, ms=2500)
    c.foto('06-orden', selector='.o_form_view .o_form_sheet_bg')

    # 7. Boleta retenida: casilla «Emisión SUNAT retenida»
    c.abrir('/odoo/action-account.action_move_out_invoice_type/%s' % BOLETA, ms=2500)
    c.js("document.querySelectorAll('.o_attachment_preview').forEach(e => e.remove())")
    c.texto('Otra información', ms=800)
    c.foto('07-boleta-retenida', selector='.o_form_view .o_form_sheet_bg')

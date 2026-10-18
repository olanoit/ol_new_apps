"""Capturas de la ficha de al_l10n_pe_perception (datos de demostración)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_l10n_pe_perception') as c:
    # 1. Ajustes ▸ Perú: bloque de percepciones
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    c.page.get_by_text('Percepciones del IGV', exact=True).first.evaluate(
        "e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    c.foto('01-ajustes', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 560})

    # 2. Producto sujeto (pestaña Contabilidad)
    c.abrir_registro('product.template', 13994, ms=2000)
    c.texto('Contabilidad')
    c.foto('02-producto', selector='.o_form_view .o_form_sheet_bg')

    # 3. Factura de venta con la percepción
    c.abrir_registro('account.move', 28983, ms=2000)
    c.texto('Facturación PE')
    c.texto('Percepción IGV')
    c.foto('03-factura', selector='.o_form_view .o_form_sheet_bg')

    # 4. Comprobante de percepción emitido
    c.abrir_registro('l10n_pe.perception', 21, ms=2000)
    c.foto('04-comprobante', selector='.o_form_view .o_form_sheet_bg')

    # 5. Comprobante al 0,5 % (cliente agente de percepción)
    c.abrir_registro('l10n_pe.perception', 22, ms=2000)
    c.foto('05-comprobante-agente', selector='.o_form_view .o_form_sheet_bg')

    # 6. Lista de comprobantes
    c.abrir_accion('al_l10n_pe_perception.action_perception', ms=2500)
    c.foto('06-comprobantes', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 360})

    # 7. Facturas sujetas a percepción
    c.abrir_accion('al_l10n_pe_perception.action_perception_invoices', ms=2500)
    c.foto('07-facturas', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 360})

    # 8. Resumen F.V. 697
    c.abrir_accion('al_l10n_pe_perception.action_perception_fv697', ms=3000)
    c.foto('08-fv697', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 380})

    # 9. Percepción que nos cobraron (comprobante del proveedor)
    c.abrir_registro('l10n_pe.perception.received', 6, ms=2000)
    c.foto('09-recibida', selector='.o_form_view .o_form_sheet_bg')

    # 10. Percepción a la importación (DUA)
    c.abrir_registro('l10n_pe.perception.received', 7, ms=2000)
    c.foto('10-dua', selector='.o_form_view .o_form_sheet_bg')

    # 11. Resumen F.V. 621
    c.abrir_accion('al_l10n_pe_perception.action_perception_received_fv621', ms=3000)
    c.foto('11-fv621', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 380})

    # 13. Menú Perú ▸ Clientes, sección «Detracciones, retenciones y
    # percepciones»
    c.page.locator('.o_menu_sections button:visible:has-text("Clientes")').first.click()
    c.esperar(800)
    c.foto('13-menu', clip={'x': 0, 'y': 0, 'width': 900, 'height': 520})
    c.page.keyboard.press('Escape')

    # 12. Factura de proveedor con «Registrar percepción»
    c.abrir_registro('account.move', 28990, ms=2000)
    c.foto('12-factura-proveedor', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 420})

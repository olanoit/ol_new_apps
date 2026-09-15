"""Capturas de la ficha de al_account_move_name_sequence (datos «DEMO»).

Uso: ``python al_account_move_name_sequence.py [bloque …]`` (1, 2; sin
argumentos, todos)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

SERIE_F001 = 3
SERIE_F002 = 11
SERIE_F099 = 26         # serie publicada y luego inhabilitada
JOURNAL_CPE = 429       # Facturas TPV: documentos latam y series F001/F002
JOURNAL_CAJA = 1971     # DEMO Caja chica: prefijo simple CC01-
INVOICE_DRAFT = 2406    # factura en borrador del diario 429 (DEMO Distribuidora Norte)
INVOICE_F002 = 2443     # F002-00000002 · «DEMO serie F002»
REFUND_FC02 = 2444      # FC02-00000001 · nota de crédito de la anterior
ENTRY_CAJA = 2400       # CC01-00000002

BLOQUES = set(sys.argv[1:]) or {'1', '2'}
HOJA = '.o_form_view .o_form_sheet_bg'


def grupo_numeracion(c, nombre):
    grupo = c.page.locator('.o_inner_group:has(div[name=use_name_sequence])').first
    grupo.evaluate("e => e.scrollIntoView({block: 'center'})")
    c.esperar(400)
    caja = grupo.bounding_box()
    c.foto(nombre, clip={'x': caja['x'] - 16, 'y': caja['y'] - 12,
                         'width': caja['width'] + 32, 'height': caja['height'] + 24})


def ocultar_aviso_ose(c):
    c.js("document.querySelectorAll('.o_form_sheet_bg > .alert').forEach(e => e.remove())")
    c.esperar(300)


with Captura('al_account_move_name_sequence') as c:
    if '1' in BLOQUES:
        # 1. Series CPE
        c.abrir_accion('al_account_move_name_sequence.edi_invoice_series_action', ms=2000)
        c.foto('01-series-cpe')

        # Formularios más anchos: con 1300 px el chatter va debajo de la hoja.
        c.page.set_viewport_size({'width': 1300, 'height': 900})

        # 2. Serie nueva: al escribir F003 se proponen FC03 y FD03
        c.abrir('/odoo/action-al_account_move_name_sequence.edi_invoice_series_action/new', ms=2000)
        c.page.locator('div[name=l10n_latam_document_type_id] label:has-text("Factura")').first.click()
        c.esperar(500)
        nombre = c.page.locator('div[name=name] input').first
        nombre.fill('F003')
        c.page.locator('div[name=name_nc]').first.click()
        c.esperar(900)
        c.foto('02-serie-nueva', selector=HOJA)

        # 3. Formato validado: una boleta no puede ir en una serie de factura
        c.page.locator('div[name=name_nc] input').first.fill('')
        c.page.locator('div[name=name_nd] input').first.fill('')
        nombre.fill('B003')
        c.page.locator('div[name=name_nc]').first.click()
        c.esperar(700)
        c.clic('.o_form_button_save', ms=1800)
        c.foto('03-error-formato', selector='.modal-content')
        c.clic('.modal-footer button', ms=600)
        c.clic('.o_form_button_cancel', ms=900)

        # 4. Serie F002 publicada, con sus secuencias (modo desarrollador)
        # (el botón «Comprobantes» está en la barra superior del formulario)
        c.abrir('/odoo/edi.invoice.series/%s?debug=1' % SERIE_F002, ms=2500)
        hoja = c.page.locator(HOJA).first.bounding_box()
        c.foto('04-serie-publicada', clip={'x': 0, 'y': 44, 'width': 1300,
                                           'height': hoja['y'] + hoja['height'] - 44})

        # 5. Serie inhabilitada
        c.abrir_registro('edi.invoice.series', SERIE_F099, ms=2000)
        c.foto('05-serie-inhabilitada', selector=HOJA)

        # 6. Catálogo de tipos de documento
        c.page.set_viewport_size({'width': 1440, 'height': 900})
        c.abrir_accion('l10n_latam_invoice_document.action_document_type', ms=2000)
        c.foto('06-tipos-documento')

    if '2' in BLOQUES:
        c.page.set_viewport_size({'width': 1300, 'height': 900})

        # 7. Diario con documentos latam: series CPE asignadas
        c.abrir_registro('account.journal', JOURNAL_CPE, ms=2000)
        c.foto('07-diario-series', selector=HOJA)

        # 8. Factura en borrador: la serie junto al tipo de documento
        c.abrir_registro('account.move', INVOICE_DRAFT, ms=2000)
        c.clic('div[name=edi_series_id] input', ms=900)
        c.foto('08-factura-serie', selector=HOJA)
        c.page.keyboard.press('Escape')

        # 9. Factura publicada con la serie F002
        c.abrir_registro('account.move', INVOICE_F002, ms=2000)
        # Se oculta el aviso del envío de prueba al OSE: no es de este módulo
        ocultar_aviso_ose(c)
        c.foto('09-factura-f002', selector=HOJA)

        # 10. Nota de crédito: serie rectificativa FC02
        c.abrir_registro('account.move', REFUND_FC02, ms=2000)
        ocultar_aviso_ose(c)
        c.foto('10-nota-credito-fc02', selector=HOJA)

        # 11. Comprobantes numerados por la serie (botón «Comprobantes»)
        c.abrir_registro('edi.invoice.series', SERIE_F002, ms=2000)
        c.clic('button[name=action_view_invoices]', ms=2000)
        c.foto('11-comprobantes-serie')

        # 12. Diario sin documentos latam: prefijo simple
        c.abrir_registro('account.journal', JOURNAL_CAJA, ms=2000)
        c.foto('12-diario-prefijo', selector=HOJA)

        # 13. Sin secuencia aparece el botón «Generar» (sin guardar)
        campo = c.page.locator('div[name=name_sequence_id] input').first
        campo.fill('')
        c.page.locator('div[name=name_sequence_prefix]').first.click()
        c.esperar(900)
        grupo_numeracion(c, '13-boton-generar')
        c.clic('.o_form_button_cancel', ms=900)

        # 14. Asiento numerado con la secuencia del diario
        c.abrir_registro('account.move', ENTRY_CAJA, ms=2000)
        c.foto('14-asiento-cc01', selector=HOJA)

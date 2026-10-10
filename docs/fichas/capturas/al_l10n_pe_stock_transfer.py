"""Capturas de la ficha de al_l10n_pe_stock_transfer (datos «DEMO TRAS», cargados
con al_l10n_pe_stock_transfer/tools/stock_transfer_demo_data.py). No envía
nada a SUNAT.

Uso: python docs/fichas/capturas/al_l10n_pe_stock_transfer.py TRASLADO COMPRA DEVOLUCION TIPO
(ids de las transferencias DTP/INT/00002, DTP/IN/00001, DTP/OUT/00001 y del
tipo de operación de entregas de DEMO TRAS Planta Ate)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_stock_transfer'
FORM = '.o_form_view .o_form_sheet_bg'
TRANSFER, PURCHASE, RETURN, OUT_TYPE = (int(arg) for arg in sys.argv[1:5])


def logistica(c, picking, name):
    c.abrir_registro('stock.picking', picking, ms=2000)
    c.texto('Logística PE', ms=1200)
    c.foto(name, selector=FORM)


with Captura(M) as c:
    # 1-3. Logística PE: traslado entre establecimientos con bienes de
    # terceros (04), compra recogida por la empresa (02) y devolución al
    # propietario (06).
    logistica(c, TRANSFER, '01-traslado-establecimientos')
    logistica(c, PURCHASE, '02-compra-recogida')
    logistica(c, RETURN, '03-devolucion-propietario')

    # 4. Motivo de traslado por defecto en el tipo de operación
    c.abrir_registro('stock.picking.type', OUT_TYPE, ms=2000)
    c.foto('04-tipo-operacion', selector=FORM)

    # 5. Existencias de terceros (filtro «De terceros»)
    c.abrir_accion('stock.action_view_quants', ms=3000)
    c.page.locator('.o_searchview_dropdown_toggler').first.click()
    c.esperar(600)
    c.texto('De terceros', ms=1500)
    c.page.keyboard.press('Escape')
    c.esperar(400)
    # Solo los bienes de la demostración.
    c.page.locator('.o_searchview_input').fill('DEMO TRAS Andamio')
    c.page.keyboard.press('Enter')
    c.esperar(1500)
    c.foto('05-existencias-terceros', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 420})

    # 6. Guía impresa del traslado: punto de partida y llegada, motivo 04 y
    # el propietario de los bienes.
    c.abrir('/report/html/al_l10n_pe_delivery_guide_report.report_guia_remision_document/%s' % TRANSFER,
            ms=2500)
    c.foto('06-guia-impresa', selector='.article', padding=8)

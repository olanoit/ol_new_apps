"""Capturas de la ficha de al_account_move_name_sequence (datos «DEMO»)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

SERIE_F001 = 3
JOURNAL_CPE = 429       # diario de ventas con documentos latam y series F001/F002
JOURNAL_CAJA = 1971     # DEMO Caja chica: prefijo simple CC01-
INVOICE_DRAFT = 2406    # DEMO serie CPE: factura en borrador del diario 429
ENTRY_CAJA = 2400       # CC01-00000002

with Captura('al_account_move_name_sequence') as c:
    # 1. Series CPE
    c.abrir_accion('al_account_move_name_sequence.edi_invoice_series_action', ms=2000)
    c.foto('01-series-cpe')

    # Formularios más anchos: con 1300 px el chatter va debajo de la hoja.
    c.page.set_viewport_size({'width': 1300, 'height': 900})

    # 2. Serie F001 publicada
    c.abrir_registro('edi.invoice.series', SERIE_F001, ms=2000)
    c.foto('02-serie-f001', selector='.o_form_view .o_form_sheet_bg')

    # 3. Diario con documentos latam: series CPE asignadas
    c.abrir_registro('account.journal', JOURNAL_CPE, ms=2000)
    c.foto('03-diario-series', selector='.o_form_view .o_form_sheet_bg')

    # 4. Factura en borrador: la serie junto al tipo de documento
    c.abrir_registro('account.move', INVOICE_DRAFT, ms=2000)
    c.clic('div[name=edi_series_id] input', ms=900)
    c.foto('04-factura-serie', selector='.o_form_view .o_form_sheet_bg')

    # 5. Comprobantes numerados por la serie (botón «Comprobantes»)
    c.abrir_registro('edi.invoice.series', SERIE_F001, ms=2000)
    c.clic('button[name=action_view_invoices]', ms=2000)
    c.foto('05-comprobantes-serie')

    # 6. Diario sin documentos latam: prefijo simple
    c.abrir_registro('account.journal', JOURNAL_CAJA, ms=2000)
    c.foto('06-diario-prefijo', selector='.o_form_view .o_form_sheet_bg')

    # 7. Asiento numerado con la secuencia del diario
    c.abrir_registro('account.move', ENTRY_CAJA, ms=2000)
    c.foto('07-asiento-cc01', selector='.o_form_view .o_form_sheet_bg')

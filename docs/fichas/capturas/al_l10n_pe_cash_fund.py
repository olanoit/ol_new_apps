"""Capturas de la ficha de al_l10n_pe_cash_fund y de las novedades de pagos
(al_l10n_pe_detraction: importar constancias; al_account_payments: compra y
venta de moneda). Argumentos: id de la entrega a rendir, de su rendición
publicada, de la caja chica y la ruta de un CSV de constancias (opcional)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_cash_fund'
FULL = '.o_action_manager'
FORM = '.o_form_view .o_form_sheet_bg'
FUND, SETTLEMENT, PETTY = (int(a) for a in sys.argv[1:4])
CSV = sys.argv[4] if len(sys.argv) > 4 else None

with Captura(M) as c:
    c.abrir_accion(f'{M}.action_cash_fund', ms=2000)
    c.foto('01-fondos', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 420})
    c.abrir_registro('l10n_pe.cash.fund', FUND, ms=2000)
    c.foto('02-entrega', selector=FULL)
    c.abrir_registro('l10n_pe.cash.settlement', SETTLEMENT, ms=2000)
    c.foto('03-rendicion', selector=FULL)
    c.clic('.o_notebook_headers a:has-text("Planilla de movilidad")', ms=900)
    c.foto('04-movilidad', selector=FORM)
    c.abrir(f'/report/html/{M}.report_mobility_sheet/{SETTLEMENT}', ms=1500)
    c.foto('05-planilla-movilidad', full_page=True)
    c.abrir(f'/report/html/{M}.report_cash_fund/{FUND}', ms=1500)
    c.foto('06-liquidacion', full_page=True)
    c.abrir_registro('l10n_pe.cash.fund', PETTY, ms=2000)
    c.foto('07-caja-chica', selector=FULL)
    c.abrir_accion('al_account_base.action_pe_settings', ms=2500)
    grupo = c.page.locator('.o_settings_container:has([name=l10n_pe_cash_advance_account_id])').first
    grupo.evaluate("e => e.scrollIntoView({block: 'center'})")
    c.esperar(500)
    caja = grupo.bounding_box()
    c.foto('08-ajustes', clip={'x': caja['x'] - 16, 'y': caja['y'] - 60,
                               'width': caja['width'] + 32, 'height': caja['height'] + 76})

with Captura('al_account_payments') as c:
    c.abrir_accion('al_account_payments.action_currency_exchange_wizard', ms=2000)
    c.foto('10-compra-venta-moneda', selector='.modal-content')

if CSV:
    with Captura('al_l10n_pe_detraction') as c:
        c.abrir_accion('al_l10n_pe_detraction.action_detraction_import_wizard', ms=2000)
        c.page.locator('.modal-content input[type=file]').set_input_files(CSV)
        c.esperar(2500)
        c.foto('21-importar-constancias', selector='.modal-content')

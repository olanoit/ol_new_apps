"""Capturas de la ficha de al_l10n_pe_retention (datos «DEMO RET»)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_l10n_pe_retention') as c:
    # 1. Ajustes ▸ Perú: bloque de retenciones
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    c.page.get_by_text('Retenciones del IGV', exact=True).first.evaluate(
        "e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    c.foto('01-ajustes')

    # 2. Factura de proveedor sujeta a retención
    c.abrir_registro('account.move', 326, ms=2000)
    c.foto('02-factura', selector='.o_form_view .o_form_sheet_bg')

    # 3. Asistente de pago con la línea de retención (factura «DEMO RET ficha»)
    c.abrir_registro('account.move', 2395, ms=2000)
    c.clic('.o_form_statusbar button:has-text("Pagar")', ms=2500)
    c.foto('03-registrar-pago', selector='.modal-content')
    c.clic('.modal-header .btn-close', ms=800)

    # 4. Pago con número de comprobante y botón XML CRE
    c.abrir_registro('account.payment', 20, ms=2000)
    c.foto('04-pago-cre', selector='.o_form_view .o_form_sheet_bg')

    # 5. Retenciones efectuadas
    c.abrir_accion('al_l10n_pe_retention.action_retention_payments', ms=2000)
    c.foto('05-efectuadas')

    # 6. Retención sufrida registrada
    c.abrir_registro('l10n_pe.retention.received', 3, ms=2000)
    c.foto('06-sufrida', selector='.o_form_view .o_form_sheet_bg')

    # 7. Resumen 626 generado (julio 2026)
    c.abrir_accion('al_l10n_pe_retention.action_retention_summary', ms=2000)
    c.clic('.modal-dialog div[name=month] input', ms=500)
    c.page.locator('.o_select_menu_item:has-text("07")').first.click(); c.esperar(400)
    c.clic('.modal-dialog button[name=action_export]', ms=2500)
    c.foto('07-resumen-626', selector='.modal-content')

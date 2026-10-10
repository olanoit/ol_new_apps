"""Capturas de la ficha de al_l10n_pe_lease (datos «DEMO NIIF16», cargados con
al_l10n_pe_lease/tools/lease_demo_data.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_lease'
FORM = '.o_form_view .o_form_sheet_bg'
FULL = '.o_action_manager'
OFFICE, WAREHOUSE, FORKLIFT = 29, 30, 31
ASSET, LOAN, BILL_2 = 312, 7, 17860

with Captura(M) as c:
    # 1. Contratos
    c.abrir_accion(f'{M}.action_lease', ms=2000)
    c.foto('01-contratos', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 360})

    # 2. Oficina en curso: resultado y tabla del pasivo; 3. sus cuentas
    c.abrir_registro('l10n_pe.lease', OFFICE, ms=2500)
    c.foto('02-contrato', selector=FULL)
    c.page.locator('a.nav-link:text-is("Contabilidad")').first.click()
    c.esperar(800)
    c.foto('03-cuentas', selector=FORM)

    # 4. Montacargas en borrador: aviso NIIF 16 y cálculo
    c.abrir_registro('l10n_pe.lease', FORKLIFT, ms=2500)
    c.foto('04-borrador', selector=FORM)

    # 5. Almacén exento (corto plazo)
    c.abrir_registro('l10n_pe.lease', WAREHOUSE, ms=2000)
    c.foto('05-exento', selector=FORM)

    # 6. Activo por derecho de uso y 7. pasivo (préstamo)
    c.abrir_registro('account.asset', ASSET, ms=2500)
    c.foto('06-activo', selector=FORM)
    c.abrir_registro('account.loan', LOAN, ms=2500)
    c.foto('07-pasivo', selector=FORM)

    # 8. Factura del arrendador de la cuota 2 (contra el pasivo)
    c.abrir_registro('account.move', BILL_2, ms=2500)
    c.foto('08-factura', selector=FORM)

    # 9. Análisis
    c.abrir_accion(f'{M}.action_lease_analysis', ms=2500)
    c.foto('09-analisis', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 420})

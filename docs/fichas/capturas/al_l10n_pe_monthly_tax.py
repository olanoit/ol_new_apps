"""Capturas de la ficha de al_l10n_pe_monthly_tax (periodos 09/2026 y 10/2026
calculados con al_l10n_pe_monthly_tax/tools/monthly_tax_demo_data.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_monthly_tax'
FORM = '.o_form_view .o_form_sheet_bg'

with Captura(M) as c:
    # 1. Lista de declaraciones mensuales
    c.abrir_accion(f'{M}.action_l10n_pe_monthly_tax', ms=2000)
    c.foto('01-lista', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 300})
    # 2. Periodo: IGV con saldo a favor, percepciones y retenciones
    c.texto('621 10/2026', ms=2000)
    c.foto('02-igv', selector=FORM)
    # 3. Pestaña Renta: pago a cuenta según el régimen
    c.page.locator('a.nav-link:text-is("Renta")').first.click()
    c.esperar(800)
    c.foto('03-renta', selector=FORM)
    # 4. Régimen tributario
    c.abrir_accion(f'{M}.action_l10n_pe_tax_regime', ms=2000)
    c.foto('04-regimen', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 260})

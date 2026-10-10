"""Capturas de la ficha de al_l10n_pe_factoring (datos «DEMO FAC», cargados con
al_l10n_pe_factoring/tools/factoring_demo_data.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_factoring'
FORM = '.o_form_view .o_form_sheet_bg'
# Los botones de cabecera y los inteligentes van fuera de la hoja.
FULL = '.o_action_manager'
OP_WITHOUT, OP_WITH, OP_DRAFT, INVOICE_WITH = 46, 47, 48, 16769

with Captura(M) as c:
    # 1. Operaciones
    c.abrir_accion(f'{M}.action_factoring', ms=2000)
    c.foto('01-operaciones', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 420})

    # 2. Operación en borrador: botón «Ceder facturas»
    c.abrir_registro('l10n_pe.factoring', OP_DRAFT, ms=2000)
    c.foto('02-borrador', selector=FULL)

    # 3. Sin recurso desembolsada: adelanto, cargos y neto
    c.abrir_registro('l10n_pe.factoring', OP_WITHOUT, ms=2000)
    c.foto('03-sin-recurso', selector=FULL)

    # 4. Con recurso: devengo de intereses (asistente, sin aplicar)
    c.abrir_registro('l10n_pe.factoring', OP_WITH, ms=2000)
    c.foto('04-con-recurso', selector=FULL)
    c.texto('Devengar intereses', ms=1500)
    c.foto('05-devengo', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(600)

    # 6. Facturas cedidas
    c.abrir_accion(f'{M}.action_factoring_lines', ms=2000)
    c.foto('06-facturas-cedidas', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 420})

    # 7. La factura: Facturación PE ▸ Factoring
    c.abrir_registro('account.move', INVOICE_WITH, ms=2500)
    c.texto('Facturación PE', ms=1200)
    c.page.locator('a.nav-link:text-is("Factoring")').last.click()
    c.esperar(900)
    c.foto('07-factura', selector=FORM)

    # 8. Análisis y 9. cuentas
    c.abrir_accion(f'{M}.action_factoring_analysis', ms=2500)
    c.foto('08-analisis', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 480})
    c.abrir_accion(f'{M}.action_factoring_account_config', ms=2000)
    c.foto('09-cuentas', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 360})

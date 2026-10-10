"""Capturas de la ficha de al_l10n_pe_term_deposit (datos «DEMO DEP», cargados
con al_l10n_pe_term_deposit/tools/term_deposit_demo_data.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_term_deposit'
FULL = '.o_action_manager'
FORM = '.o_form_view .o_form_sheet_bg'
TERM, GUARANTEE = int(sys.argv[1]), int(sys.argv[2])

with Captura(M) as c:
    # 1. Lista
    c.abrir_accion(f'{M}.action_term_deposit', ms=2000)
    c.foto('01-depositos', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 420})

    # 2-3. Depósito a plazo y sus saldos
    c.abrir_registro('l10n_pe.term.deposit', TERM, ms=2000)
    c.foto('02-deposito', selector=FULL)
    c.texto('Saldos', ms=800)
    c.foto('03-saldos', selector=FORM)

    # 4. Renovar (asistente, sin aplicar)
    c.texto('Renovar', ms=1500)
    c.foto('04-renovar', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(600)

    # 5. Garantía de alquiler
    c.abrir_registro('l10n_pe.term.deposit', GUARANTEE, ms=2000)
    c.foto('05-garantia', selector=FORM)

    # 6. Análisis y 7. cuentas
    c.abrir_accion(f'{M}.action_term_deposit_analysis', ms=2500)
    c.foto('06-analisis', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 480})
    c.abrir_accion(f'{M}.action_term_deposit_account_config', ms=2000)
    c.foto('07-cuentas', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 320})

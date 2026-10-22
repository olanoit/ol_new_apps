"""Recorrido de la interfaz de Cobranza y Recaudación bancaria.

Abre cada menú y el primer registro de cada lista, y falla si aparece un diálogo
de error o un error de JavaScript. Deja capturas para las fichas.

    FICHAS_URL=http://127.0.0.1:18069 FICHAS_DB=test_pe_collection \\
        python3 docs/cobranza/pruebas/recorrido_interfaz.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'fichas'))
from capturar import Captura  # noqa: E402

PANTALLAS = [
    # (módulo de la captura, acción, nombre de la captura o None, abrir el primer registro)
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_worklist_server', 'worklist', False),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_action', None, True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_promise', None, True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_dispute', 'disputes', True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_bureau', 'bureaus', True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_provision', 'provision', True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_dispute_reason', None, False),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_interest_wizard', None, False),
    ('al_l10n_pe_bank_collection', 'al_l10n_pe_bank_collection.action_bank_collection_agreement', None, True),
    ('al_l10n_pe_bank_collection', 'al_l10n_pe_bank_collection.action_bank_collection_layout', 'layouts', True),
    ('al_l10n_pe_bank_collection', 'al_l10n_pe_bank_collection.action_bank_collection_batch', 'batch', True),
    ('al_l10n_pe_bank_collection', 'al_l10n_pe_bank_collection.action_bank_collection_response', 'response', True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_agency', 'agency', True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_agency_assignment', 'agency-portfolio', False),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_commission', 'commission', True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_commission_line', None, False),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_commission_plan', 'commission-plan', True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_lawsuit', 'lawsuit', True),
]

#: Lo que ve el usuario de una agencia externa (FICHAS_USER=estudio_recupera).
PANTALLAS_AGENCIA = [
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_worklist_server', 'agency-worklist', False),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_portfolio_server', 'agency-user-portfolio', False),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_action', None, True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_promise', None, False),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_agency_assignment', None, True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_commission', None, True),
    ('al_l10n_pe_collection', 'al_l10n_pe_collection.action_collection_lawsuit', 'agency-lawsuit', True),
]
if os.environ.get('FICHAS_USER', 'admin') != 'admin':
    PANTALLAS = PANTALLAS_AGENCIA
if os.environ.get('SOLO'):
    # SOLO=lawsuit,commission: solo las acciones que contienen alguno de esos textos.
    PANTALLAS = [p for p in PANTALLAS if any(t in p[1] for t in os.environ['SOLO'].split(','))]

problemas = []
for module, xmlid, foto, abrir in PANTALLAS:
    with Captura(module) as c:
        errores = []
        c.page.on('console', lambda msg: msg.type == 'error' and errores.append(msg.text))
        c.page.on('pageerror', lambda exc: errores.append(str(exc)))
        c.abrir_accion(xmlid)
        if abrir and c.page.locator('.o_data_row').count():
            c.clic('.o_data_row td.o_data_cell')
        dialogo = c.page.locator('.o_error_dialog, .o_dialog .modal-title:has-text("Error")')
        if dialogo.count():
            errores.append('diálogo de error: %s' % c.page.locator('.o_dialog').first.inner_text()[:300])
        titulo = c.page.locator('.o_breadcrumb, .modal-title').first.inner_text() if c.page.locator(
            '.o_breadcrumb, .modal-title').count() else '?'
        if foto:
            c.foto('v3-%s' % foto)
        estado = 'OK   ' if not errores else 'FALLA'
        print('%s %s · %s %s' % (estado, xmlid.split('.')[-1], titulo.replace('\n', ' ‣ ')[:70],
                                 '; '.join(errores)[:300]))
        if errores:
            problemas.append(xmlid)

print('\nRESUMEN: %s pantallas, %s con problemas %s' % (len(PANTALLAS), len(problemas), problemas or ''))

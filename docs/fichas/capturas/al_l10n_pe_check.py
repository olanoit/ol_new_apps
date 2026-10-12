# -*- coding: utf-8 -*-
"""Capturas de la ficha de al_l10n_pe_check (datos DEMO CHQ de la demo en
«PE Company»). Argumentos: id de la compañía, del diario «Cheques de
terceros» y del cheque diferido. FICHAS_URL=http://127.0.0.1:19771
FICHAS_DB=test_pe_demo"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

COMPANY, JOURNAL, CHECK = (int(a) for a in sys.argv[1:4])
CIDS = '?cids=%s' % COMPANY
with Captura('al_l10n_pe_check', viewport={'width': 1440, 'height': 900}) as c:
    c.abrir('/odoo/action-l10n_latam_check.action_third_party_check' + CIDS, 3000)
    c.foto('01-cartera', selector='.o_action_manager')
    c.abrir('/odoo/l10n_latam.check/%s%s' % (CHECK, CIDS), 2500)
    c.foto('02-cheque', selector='.o_form_view .o_form_sheet_bg')
    # Depósito de los cheques en cartera: el asistente avisa del diferido y
    # del vencido.
    c.abrir('/odoo/action-l10n_latam_check.action_third_party_check' + CIDS, 3000)
    rows = c.page.locator('.o_data_row')
    for i in range(rows.count()):
        if 'CHQT' in rows.nth(i).inner_text() or 'Cheques de terceros' in rows.nth(i).inner_text():
            rows.nth(i).locator('.o_list_record_selector input').check()
    c.esperar(800)
    c.texto('Transferir Cheque', 2500)
    field = c.page.locator('.modal div[name=destination_journal_id] input')
    field.fill('Banco')
    c.esperar(1200)
    c.page.locator('.o-autocomplete--dropdown-item').first.click()
    c.esperar(1500)
    c.foto('03-depositar', selector='.modal-content')
    c.page.locator('.modal .btn-secondary').first.click()
    c.esperar(800)
    c.abrir('/odoo/account.journal/%s%s' % (JOURNAL, CIDS), 2500)
    c.texto('Pagos entrantes', 1200)
    c.foto('04-diario', selector='.o_form_view .o_form_sheet_bg')
    c.abrir('/odoo/action-l10n_latam_check.action_own_check' + CIDS, 3000)
    c.foto('05-cheques-propios', selector='.o_action_manager')

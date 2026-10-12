# -*- coding: utf-8 -*-
"""Capturas de la ficha de al_l10n_pe_batch_payment (datos DEMO de
tools/batch_payment_demo_data.py). FICHAS_URL=http://127.0.0.1:19771"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

BATCH, JOURNAL, ACCOUNT = (int(a) for a in sys.argv[1:4])
with Captura('al_l10n_pe_batch_payment', viewport={'width': 1440, 'height': 900}) as c:
    c.abrir_registro('account.batch.payment', BATCH, 3000)
    c.foto('01-lote', selector='.o_form_view .o_form_sheet_bg')
    c.abrir_registro('res.partner.bank', ACCOUNT, 2500)
    c.foto('02-cuenta-cci', selector='.o_form_view .o_form_sheet_bg')
    c.abrir_registro('account.journal', JOURNAL, 2500)
    c.foto('03-diario', selector='.o_form_view .o_form_sheet_bg')

#!/usr/bin/env python3
"""Capturas de la ficha de al_stock_base (transferencia con guía de remisión)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

PICKING_GRE = 237  # DEMO GRE Obra Ate, con guía de remisión enviada

with Captura('al_stock_base') as c:
    c.abrir_registro('stock.picking', PICKING_GRE, ms=3000)
    c.foto('01-formulario', selector='.o_form_view .o_form_sheet_bg')
    c.clic(".o_notebook .nav-link[name='l10n_pe_stock']")
    c.foto('02-logistica-pe', selector='.o_form_view .o_form_sheet_bg')

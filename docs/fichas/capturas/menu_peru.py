# -*- coding: utf-8 -*-
"""Capturas del menú de la app Perú (una por sección general), para la
página de la localización. FICHAS_URL=http://127.0.0.1:19771"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_account_base', viewport={'width': 1440, 'height': 1300}) as c:
    c.abrir('/odoo?menu_id=%s' % sys.argv[1], 3000)
    c.foto('menu-00', selector='.o_main_navbar')
    for i, name in enumerate(('Clientes', 'Proveedores', 'Tesorería', 'Contabilidad', 'SUNAT', 'Informes'), start=1):
        c.page.locator('.o_menu_sections .dropdown-toggle', has_text=name).first.click()
        c.esperar(800)
        c.foto('menu-%02d' % i, selector='.o_menu_sections .dropdown-menu.show, .o-dropdown--menu', padding=4)
        c.page.keyboard.press('Escape')
        c.esperar(400)

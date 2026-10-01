"""Capturas de la ficha de al_construction_material_request (datos «DEMO RQO»,
cargados con al_construction_material_request/tools/construction_demo_data.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_construction_material_request'
FORM = '.o_form_view .o_form_sheet_bg'
# En 19.0 los botones inteligentes van en el panel de control, fuera de la
# hoja: las vistas que deben mostrarlos se capturan completas.
FULL = '.o_action_manager'
R_DRAFT, R_APPROVAL, R_PROCESS, R_DONE = 243, 244, 245, 246
PICK_DISPATCH, PICK_PENDING, PR, PO, SITE_A, TIER_1 = 665, 666, 139, 242, 548, 37

with Captura(M) as c:
    # 1-2. Lista y kanban de requerimientos
    c.abrir_accion(f'{M}.action_construction_material_request', ms=2000)
    c.foto('01-lista')
    c.clic('.o_switch_view.o_kanban', ms=1500)
    c.foto('02-kanban')

    # 3. Borrador: disponibilidad del almacén central por línea
    c.abrir_registro('construction.material.request', R_DRAFT, ms=2000)
    c.foto('03-borrador', selector=FORM)

    # 4. En aprobación: nivel 1 aprobado, gerencia pendiente
    c.abrir_registro('construction.material.request', R_APPROVAL, ms=2000)
    c.foto('04-en-aprobacion', selector=FORM)

    # 5-6. Procesado: botones inteligentes, situación por línea y chatter
    c.abrir_registro('construction.material.request', R_PROCESS, ms=2000)
    c.foto('05-procesado', selector=FULL)
    msg = '.o-mail-Message:has-text("Requerimiento procesado")'
    c.page.locator(msg).first.evaluate("e => e.scrollIntoView({block: 'center'})")
    c.esperar(500)
    c.foto('06-chatter-division', selector=msg, padding=8)

    # 7-8. Transferencia reservada y transferencia en espera de la compra
    c.abrir_registro('stock.picking', PICK_DISPATCH, ms=2000)
    c.foto('07-despacho', selector=FORM)
    c.abrir_registro('stock.picking', PICK_PENDING, ms=2000)
    c.foto('08-pendiente-compra', selector=FORM)

    # 9-10. Requerimiento de compra y orden de compra
    c.abrir_registro('purchase.request', PR, ms=2000)
    c.foto('09-requerimiento-compra', selector=FORM)
    msg = '.o-mail-Message:has-text("Orden de compra")'
    c.page.locator(msg).first.evaluate("e => e.scrollIntoView({block: 'center'})")
    c.esperar(500)
    c.foto('17-chatter-compra', selector=msg, padding=8)
    c.abrir_registro('purchase.order', PO, ms=2000)
    c.foto('10-orden-compra', selector=FORM)

    # 11. Hecho
    c.abrir_registro('construction.material.request', R_DONE, ms=2000)
    c.foto('11-hecho', selector=FULL)

    # 12. Proyecto marcado como obra (pestaña Ajustes)
    c.abrir_registro('project.project', SITE_A, ms=2000)
    c.clic('.o_notebook a[name=settings]', ms=900)
    c.foto('12-proyecto-obra', selector=FULL)

    # 13. Ajustes ▸ Requerimientos de obra (sección propia de la app)
    c.abrir('/odoo/settings#al_construction_material_request', ms=3000)
    c.foto('13-ajustes', selector='.app_settings_block[data-key=al_construction_material_request]')

    # 19. Calendario de fechas requeridas (octubre 2026)
    c.abrir_accion(f'{M}.action_construction_material_request', ms=2000)
    c.clic('.o_switch_view.o_calendar', ms=2500)
    c.foto('19-calendario')

    # 14. Regla de aprobación del nivel 1
    c.abrir_registro('tier.definition', TIER_1, ms=2000)
    c.foto('14-regla-aprobacion', selector=FORM)

# Vista móvil: el residente pide desde el celular
with Captura(M, viewport={'width': 390, 'height': 844}) as c:
    c.abrir_registro('construction.material.request', R_DRAFT, ms=2500)
    c.foto('15-movil-borrador', full_page=True)
    c.page.locator('.o_notebook').first.evaluate("e => e.scrollIntoView({block: 'start'})")
    c.esperar(500)
    c.foto('16-movil-materiales')
    c.abrir_accion(f'{M}.action_construction_material_request', ms=2500)
    c.foto('18-movil-lista')

# 20. Vale de requerimiento de obra (PDF). Se descarga con sesión HTTP:
# desde el shell wkhtmltopdf no recibe la base de datos y sale sin estilos.
import subprocess  # noqa: E402

import requests  # noqa: E402
from capturar import DB, PASSWORD, ROOT, URL, USER  # noqa: E402

session = requests.Session()
session.post(f'{URL}/web/session/authenticate', json={
    'jsonrpc': '2.0', 'params': {'db': DB, 'login': USER, 'password': PASSWORD}})
pdf = session.get(f'{URL}/report/pdf/{M}.report_construction_request/{R_PROCESS}').content
out = ROOT / M / 'static' / 'description' / 'screenshots'
(out / 'vale.pdf').write_bytes(pdf)
subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', str(out / 'vale.pdf'),
                str(out / '20-vale')], check=True)
(out / 'vale.pdf').unlink()
print('captura', (out / '20-vale.png').relative_to(ROOT))

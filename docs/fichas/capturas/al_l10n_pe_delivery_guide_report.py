"""Capturas de la ficha de al_l10n_pe_delivery_guide_report (datos «DEMO GRE»).

Datos creados por odoo shell: cliente «DEMO GRE Constructora Los Andes
S.A.C.», conductor «DEMO GRE Carlos Quispe Mamani», vehículo DEM-701,
tres productos «DEMO GRE» (el fierro con lotes) y la entrega validada con
origen «DEMO GRE Obra Ate», marcada como guía T001-00000101 enviada (sin
envío real: el número y el ticket son de demostración).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

ENTREGA = 237  # ACL/OUT/00061
REPORTE = '/report/html/al_l10n_pe_delivery_guide_report.report_guia_remision_document/%s'

with Captura('al_l10n_pe_delivery_guide_report') as c:
    # 1. Entrega validada con el botón «Guía de remisión»
    c.abrir('/odoo/inventory', ms=1500)
    c.abrir('/odoo/inventory/action-stock.action_picking_tree_all/%s' % ENTREGA, ms=2500)
    c.foto('01-entrega', selector='.o_form_view .o_form_sheet_bg')

    # 2. Pestaña EDI PE: transporte, vehículo y conductor
    c.texto('EDI PE', ms=800)
    c.foto('02-datos-traslado', selector='.o_form_view .o_notebook', padding=14)

    # 3. Representación impresa
    c.abrir(REPORTE % ENTREGA, ms=2000)
    c.foto('03-guia-remision', selector='.gre-a4', padding=14)

    # 4. Vehículos desde la app Perú
    c.abrir_accion('al_l10n_pe_detraction.action_detraction_type', ms=2000)  # entra en la app Perú
    c.clic('.o_main_navbar button:has-text("Configuración")', ms=600)
    c.clic('.o-dropdown--menu a:has-text("Vehículos (guías de remisión)")', ms=2000)
    c.foto('04-vehiculos')

"""Capturas de la ficha de al_hr_pe_reports.

Datos: planilla de pruebas de «Comercial Demo Perú S.A.C.» (trabajadores
ficticios) y la trabajadora «DEMO FICHA HR2 Salazar Ríos Andrea». Los
asistentes de certificados se crean por RPC (son transitorios) y se ven en
la vista previa HTML del PDF. El logotipo de la compañía de pruebas se
oculta: no forma parte del módulo. No se envían correos ni se generan TXT.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

EMPLEADA = 2451          # DEMO FICHA HR2 Salazar Ríos Andrea
VERSION = 2553           # su versión, con plantilla de contrato
BOLETA = 759             # Planilla 2026-06, trabajador de pruebas
PAGO_MASIVO = 11         # PM-000007, lote de abril 2026 (BCP)

RPC = """async ([model, method, args, kwargs]) => {
    const r = await fetch('/web/dataset/call_kw', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
            model, method, args, kwargs}})});
    const j = await r.json();
    if (j.error) throw new Error(JSON.stringify(j.error));
    return j.result;
}"""


def rpc(c, model, method, args, kwargs=None):
    return c.page.evaluate(RPC, [model, method, args, kwargs or {}])


def sin_logo(c):
    c.js("document.querySelectorAll('.article img').forEach(i => i.style.visibility = 'hidden')")


with Captura('al_hr_pe_reports') as c:
    # 1. Boleta de pago del régimen general (vista previa del PDF)
    c.page.set_viewport_size({'width': 1440, 'height': 1300})
    c.abrir('/report/html/al_hr_pe_reports.report_l10n_pe_boleta_pago_document/%d' % BOLETA, ms=2000)
    sin_logo(c)
    c.foto('01-boleta', selector='.article', padding=12)

    # 2. Boleta en Nómina: Imprimir y Enviar boleta en la cabecera
    c.page.set_viewport_size({'width': 1440, 'height': 900})
    c.abrir_registro('hr.payslip', BOLETA, ms=2500)
    c.foto('02-boleta-form', selector='.o_form_view .o_form_sheet_bg')

    # 3. Asistente del certificado de trabajo desde la ficha del empleado
    c.abrir_registro('hr.employee', EMPLEADA, ms=2500)
    c.clic('.o_cp_action_menus button', ms=900)
    c.texto('Certificado de trabajo', ms=2000)
    c.foto('03-certificado-asistente', selector='.modal-content')
    c.clic('.modal-footer button:has-text("Cancelar")', ms=800)

    # 4. Certificado de trabajo impreso
    cert = rpc(c, 'hr.certificate.wizard', 'create', [{
        'employee_id': EMPLEADA, 'des_empl': 'la Sra.', 'city': 'Lima',
        'date_ini': '2025-03-01', 'date_fin': '2026-08-31', 'company_id': 1}])
    c.abrir('/report/html/al_hr_pe_reports.report_certificate/%d' % cert, ms=2000)
    sin_logo(c)
    c.foto('04-certificado', selector='.article', padding=12)

    # 5. Certificado de rentas y retenciones de 5ta categoría
    fifth = rpc(c, 'hr.fifth.certificate.wizard', 'create', [{
        'year': 2026, 'date': '2026-09-14', 'company_id': 1,
        'employee_ids': [[6, 0, [161]]]}])
    c.page.set_viewport_size({'width': 1440, 'height': 1300})
    c.abrir('/report/html/al_hr_pe_reports.report_fifth_certificate/%d' % fifth, ms=2000)
    sin_logo(c)
    c.foto('05-certificado-5ta', selector='.article', padding=12)

    # 6. Plantilla de contrato con sus marcadores
    c.page.set_viewport_size({'width': 1440, 'height': 1100})
    c.abrir_registro('l10n_pe.hr.contract.template', 1, ms=2500)
    c.foto('06-plantilla-contrato', selector='.o_form_view .o_form_sheet_bg')

    # 7. Contrato impreso para la trabajadora DEMO
    c.page.set_viewport_size({'width': 1440, 'height': 1300})
    c.abrir('/report/html/al_hr_pe_reports.report_contract/%d' % VERSION, ms=2000)
    sin_logo(c)
    c.foto('07-contrato', selector='.article', padding=12)

    # 8. Pago masivo bancario del lote (formato BCP)
    c.page.set_viewport_size({'width': 1440, 'height': 1000})
    c.abrir_registro('hr.automate.multipayment', PAGO_MASIVO, ms=2500)
    c.foto('08-pago-masivo', selector='.o_form_view .o_form_sheet_bg')

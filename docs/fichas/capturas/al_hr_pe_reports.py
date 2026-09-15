"""Capturas de la ficha de al_hr_pe_reports.

Datos: planilla de pruebas de «Comercial Demo Perú S.A.C.» (trabajadores
ficticios), la trabajadora «DEMO FICHA HR2 Salazar Ríos Andrea» y los pagos
masivos en borrador PM-000007 (lote) y PM-000009 (gratificación). Los
asistentes de certificados se crean por RPC (son transitorios) y se ven en
la vista previa HTML del PDF. El logotipo de la compañía de pruebas se
oculta: no forma parte del módulo. No se envían correos, no se generan TXT
ni se finaliza ningún pago; la página de confirmación se abre con un token
inválido, que no modifica nada.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

EMPLEADA = 2451          # DEMO FICHA HR2 Salazar Ríos Andrea
VERSION = 2553           # su versión, con plantilla de contrato
BOLETA = 759             # Planilla 2026-06, trabajador de pruebas
PAGO_LOTE = 11           # PM-000007, lote de abril 2026 (BCP)
GRATIFICACION = 20
PARAMETROS = 90
TRABAJADOR_CTS = 160     # trabajador de pruebas con cuenta CTS
CUENTA = 28              # cuenta corriente de la compañía
PLANTILLA_CORREO = 40

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


SOLO = sys.argv[1:]  # p. ej. «03 04»: repetir solo esas capturas


def quiere(nn):
    return not SOLO or nn in SOLO


def vista(c, w=1440, h=900):
    c.page.set_viewport_size({'width': w, 'height': h})
    c.viewport = {'width': w, 'height': h}


def menu_accion(c, texto):
    c.clic('.o_cp_action_menus button', ms=900)
    c.page.locator('.dropdown-menu .dropdown-item:has-text("%s")' % texto).first.click()
    c.esperar(2000)


with Captura('al_hr_pe_reports') as c:
    # ---------------- Boleta de pago ----------------
    if quiere('01'):
        vista(c, 1440, 1300)
        c.abrir('/report/html/al_hr_pe_reports.report_l10n_pe_boleta_pago_document/%d' % BOLETA, ms=2000)
        sin_logo(c)
        c.foto('01-boleta', selector='.article', padding=12)

    if quiere('02'):
        vista(c)
        c.abrir_registro('hr.payslip', BOLETA, ms=2500)
        c.foto('02-boleta-form', selector='.o_form_view .o_form_sheet_bg')

    # Lista de boletas: columnas de seguimiento y acción de envío masivo
    if quiere('03'):
        vista(c, 1440, 900)
        c.abrir_accion('hr_payroll.action_view_hr_payslip_month_form', ms=2500)
        buscar = c.page.locator('.o_searchview_input').first
        buscar.fill('Quispe Mamani Juan Carlos')
        buscar.press('Enter')
        c.esperar(1500)
        c.clic('.o_optional_columns_dropdown button', ms=700)
        for etiqueta in ('Fecha de envío de boleta', 'Recepción confirmada', 'Fecha de confirmación'):
            item = c.page.locator('.o-dropdown--menu .dropdown-item:has-text("%s") input' % etiqueta).first
            if not item.is_checked():
                item.click()
                c.esperar(500)
        for etiqueta in ('Costo para el empleador', 'Salario bruto'):
            item = c.page.locator('.o-dropdown--menu .dropdown-item:has-text("%s") input' % etiqueta).first
            if item.count() and item.is_checked():
                item.click()
                c.esperar(500)
        c.page.keyboard.press('Escape')
        c.esperar(500)
        c.page.locator('.o_data_row .o_list_record_selector input').first.click()
        c.esperar(700)
        c.clic('.o_cp_action_menus button', ms=900)
        c.foto('03-boletas-lista')
        c.page.keyboard.press('Escape')

    # Menú del lote en el kanban de periodos de nómina
    if quiere('04'):
        vista(c)
        c.abrir_accion('hr_payroll.action_hr_payslip_run', ms=2500)
        card = c.page.locator('.o_kanban_record:has-text("Planilla 2026-06")').first
        card.evaluate("e => e.scrollIntoView({block: 'end'})")
        c.esperar(500)
        card.locator('button.o-dropdown:has(.fa-ellipsis-v)').first.click()
        c.esperar(900)
        cbox = card.bounding_box()
        mbox = c.page.locator('.o-dropdown--menu:visible').last.bounding_box()
        top = min(cbox['y'], mbox['y']) - 10
        bottom = max(cbox['y'] + cbox['height'], mbox['y'] + mbox['height']) + 10
        c.foto('04-lote-menu', recortar=False, clip={
            'x': 0, 'y': top, 'width': 1440, 'height': bottom - top})
        c.page.keyboard.press('Escape')

    if quiere('05'):
        vista(c)
        c.abrir_registro('mail.template', PLANTILLA_CORREO, ms=2500)
        c.foto('05-plantilla-correo', selector='.o_form_view .o_form_sheet_bg')

    if quiere('06'):
        c.abrir('/boleta/confirmar/1/token-invalido', ms=800)
        c.foto('06-confirmacion', selector='.boleta-card', padding=40, recortar=False)

    # ---------------- Certificados ----------------
    if quiere('07'):
        vista(c)
        c.abrir_registro('hr.employee', EMPLEADA, ms=2500)
        menu_accion(c, 'Certificado de trabajo')
        c.foto('07-certificado-asistente', selector='.modal-content')
        c.clic('.modal-footer button:has-text("Cancelar")', ms=800)

    if quiere('08'):
        cert = rpc(c, 'hr.certificate.wizard', 'create', [{
            'employee_id': EMPLEADA, 'des_empl': 'la Sra.', 'city': 'Lima',
            'date_ini': '2025-03-01', 'date_fin': '2026-08-31', 'company_id': 1}])
        vista(c, 1440, 1300)
        c.abrir('/report/html/al_hr_pe_reports.report_certificate/%d' % cert, ms=2000)
        sin_logo(c)
        c.foto('08-certificado', selector='.article', padding=12)

    if quiere('09'):
        vista(c)
        c.abrir_registro('hr.employee', EMPLEADA, ms=2500)
        menu_accion(c, 'Carta de retiro CTS')
        c.foto('09-carta-cts-asistente', selector='.modal-content')
        c.clic('.modal-footer button:has-text("Cancelar")', ms=800)

    if quiere('10'):
        # La trabajadora DEMO no tiene cuenta CTS: la carta impresa se
        # muestra con un trabajador de pruebas que sí la tiene y una fecha
        # de cese de ejemplo (el asistente es transitorio, nada se guarda).
        letter = rpc(c, 'hr.letter.wizard', 'create', [{
            'employee_id': TRABAJADOR_CTS, 'des_empl': 'el Sr.', 'city': 'Lima',
            'date_fin': '2026-06-30', 'company_id': 1}])
        vista(c, 1440, 1300)
        c.abrir('/report/html/al_hr_pe_reports.report_letter/%d' % letter, ms=2000)
        sin_logo(c)
        c.foto('10-carta-cts', selector='.article', padding=12)

    if quiere('11'):
        fifth = rpc(c, 'hr.fifth.certificate.wizard', 'create', [{
            'year': 2026, 'date': '2026-09-14', 'company_id': 1,
            'employee_ids': [[6, 0, [161]]]}])
        vista(c, 1440, 1300)
        c.abrir('/report/html/al_hr_pe_reports.report_fifth_certificate/%d' % fifth, ms=2000)
        sin_logo(c)
        c.foto('11-certificado-5ta', selector='.article', padding=12)

    # ---------------- Contratos ----------------
    if quiere('12'):
        vista(c, 1440, 1100)
        c.abrir_registro('l10n_pe.hr.contract.template', 1, ms=2500)
        c.foto('12-plantilla-contrato', selector='.o_form_view .o_form_sheet_bg')

    if quiere('13'):
        vista(c, 1440, 2200)
        c.abrir_registro('hr.employee', EMPLEADA, ms=2500)
        c.clic('.o_notebook_headers a[name=payroll_information]', ms=1200)
        sep = c.page.locator('.tab-pane.active .o_horizontal_separator:has-text("Contrato de trabajo")').first
        sbox = sep.bounding_box()
        sheet = c.page.locator('.o_form_sheet').first.bounding_box()
        nxt = c.page.locator('.tab-pane.active .o_horizontal_separator:has-text("T-Registro")').first.bounding_box()
        c.foto('13-empleado-contrato', recortar=False, clip={
            'x': sheet['x'], 'y': sbox['y'] - 12, 'width': sheet['width'],
            'height': nxt['y'] - sbox['y'] - 4})

    if quiere('14'):
        vista(c, 1440, 1300)
        c.abrir('/report/html/al_hr_pe_reports.report_contract/%d' % VERSION, ms=2000)
        sin_logo(c)
        c.foto('14-contrato', selector='.article', padding=12)

    # ---------------- Pago masivo bancario ----------------
    if quiere('15') or quiere('16'):
        vista(c, 1440, 1000)
        c.abrir_registro('hr.automate.multipayment', PAGO_LOTE, ms=2500)
        c.foto('15-pago-masivo', selector='.o_form_view .o_form_sheet_bg')
        c.clic('.o_notebook_headers a[name=bank_config]', ms=900)
        box = c.page.locator('.o_form_sheet').first.bounding_box()
        c.foto('16-pago-config-banco', clip={
            'x': box['x'], 'y': box['y'], 'width': box['width'], 'height': 480})

    if quiere('17'):
        vista(c)
        c.abrir_registro('hr.gratification', GRATIFICACION, ms=2500)
        c.foto('17-origen-gratificacion', recortar=False, clip={
            'x': 0, 'y': 48, 'width': 1440, 'height': 290})

    if quiere('18'):
        vista(c)
        c.abrir_registro('hr.main.parameter', PARAMETROS, ms=2500)
        c.clic('.o_notebook_headers a[name=multipayment]', ms=900)
        nb = c.page.locator('.o_notebook').first.bounding_box()
        c.foto('18-parametros-pagos', recortar=False, clip={
            'x': nb['x'], 'y': nb['y'], 'width': nb['width'], 'height': 150})

    if quiere('19'):
        vista(c)
        c.abrir_registro('res.partner.bank', CUENTA, ms=2000)
        c.foto('19-cuenta-bancaria', selector='.o_form_view .o_form_sheet_bg')

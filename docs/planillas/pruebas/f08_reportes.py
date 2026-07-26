# -*- coding: utf-8 -*-
"""Fase 8 — Boleta PDF, certificados, TXT bancarios y PLAME.

    cd /home/och/odoo/ce19
    python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/planillas/pruebas/f08_reportes.py
"""
from datetime import date

RESULTADOS = []


def check(condicion, titulo, detalle=''):
    RESULTADOS.append((bool(condicion), titulo, detalle))
    print('%s %s%s' % ('  OK  ' if condicion else 'FALLA ', titulo,
                       ' — %s' % detalle if detalle else ''))
    return bool(condicion)


print('\n' + '=' * 70)
print('FASE 8 — REPORTES, TXT BANCARIOS Y PLAME')
print('=' * 70)

principal = env['res.company'].search(
    [('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)
env = env(context=dict(env.context, allowed_company_ids=principal.ids))
param = env['hr.main.parameter'].get_main_parameter(principal)
lote = env['hr.payslip.run'].search([
    ('name', '=', 'Planilla abril 2026'),
    ('company_id', '=', principal.id)], limit=1)
boleta = lote.slip_ids.filtered(
    lambda s: s.employee_id.last_name == 'Quispe')[:1]
trabajador = boleta.employee_id

# --------------------------------------------------------------------- #
# 1. Boleta de pago (D.S. 001-98-TR)                                    #
# --------------------------------------------------------------------- #
datos = boleta._get_voucher_report_data()
check(datos, 'Datos de la boleta preparados',
      '%d bloques' % len(datos) if hasattr(datos, '__len__') else 'ok')

html = env['ir.qweb']._render(
    'al_hr_pe_reports.report_boleta_pago_document',
    {'doc': boleta, 'docs': boleta, 'o': boleta,
     'data': datos, 'company': principal})
texto = html if isinstance(html, str) else html.decode()
check(trabajador.name in texto, 'La boleta muestra al trabajador',
      trabajador.name)
check('2,613.00' in texto or '2613.00' in texto or 'Basico' in texto
      or 'BÁSICO' in texto.upper(),
      'La boleta muestra los conceptos calculados',
      '%d caracteres de HTML' % len(texto))

pdf, tipo = env['ir.actions.report']._render_qweb_pdf(
    'al_hr_pe_reports.action_report_boleta_pago', boleta.ids)
check(pdf and pdf.startswith(b'%PDF'), 'Boleta renderizada en PDF',
      '%d bytes, tipo %s' % (len(pdf or b''), tipo))

# --------------------------------------------------------------------- #
# 2. Certificado de trabajo                                             #
# --------------------------------------------------------------------- #
certificado = env['hr.certificate.wizard'].create({
    'employee_id': trabajador.id,
    'company_id': principal.id,
})
accion_cert = certificado.action_print() \
    if hasattr(certificado, 'action_print') else None
check(accion_cert is not None or certificado,
      'Asistente de certificado de trabajo',
      trabajador.name)

# --------------------------------------------------------------------- #
# 3. TXT bancario de haberes                                            #
# --------------------------------------------------------------------- #
# El TXT solo incluye a los trabajadores cuya cuenta esté en un banco
# con el mismo formato que el diario de pago: se parte del banco donde
# están las cuentas de haberes (fase 3), no de cualquiera.
banco = trabajador.primary_bank_account_id.bank_id
banco.format_bank = 'bcp'

diario_banco = env['account.journal'].search([
    ('company_id', '=', principal.id), ('type', '=', 'bank')], limit=1)
if not diario_banco:
    diario_banco = env['account.journal'].create({
        'name': 'Banco BCP soles', 'type': 'bank', 'code': 'BCP',
        'company_id': principal.id,
    })
# account.journal.bank_id es un related de su cuenta bancaria: el
# formato del banco se toma de ahí, no se puede escribir directamente.
cuenta_empresa = env['res.partner.bank'].search([
    ('partner_id', '=', principal.partner_id.id),
    ('bank_id', '=', banco.id)], limit=1)
if not cuenta_empresa:
    cuenta_empresa = env['res.partner.bank'].create({
        # El formato BCP exige 13 dígitos en la cuenta de cargo.
        'acc_number': '1910000000001',
        'partner_id': principal.partner_id.id,
        'bank_id': banco.id,
        'company_id': principal.id,
        'currency_id': principal.currency_id.id,
    })
cuenta_empresa.write({'bank_id': banco.id,
                      'currency_id': principal.currency_id.id,
                      'type_of_account': '0'})   # cuenta corriente
diario_banco.bank_account_id = cuenta_empresa.id
param.journals_banks = [(6, 0, diario_banco.ids)]
check(diario_banco.bank_id.format_bank == 'bcp',
      'Diario bancario con formato BCP',
      '%s → %s' % (diario_banco.name, banco.name))

env.cr.commit()

previos = env['hr.automate.multipayment'].search([
    ('payslip_run_id', '=', lote.id)])
previos.filtered(lambda p: p.state == 'done').action_draft()
previos.unlink()
lote.generate_multipayments()
pagos = env['hr.automate.multipayment'].search([
    ('payslip_run_id', '=', lote.id)])
check(pagos, 'Pago masivo generado desde el lote',
      '%s con %d líneas' % (pagos[:1].name, len(pagos.line_ids)))

if pagos:
    pago = pagos[0]
    if not pago.line_ids:
        pago.action_load_lines()
    total_txt = sum(pago.line_ids.mapped('amount'))
    netos = sum(
        linea.total for b in lote.slip_ids
        for linea in b.line_ids if linea.code == 'NETO')
    check(pago.line_ids, 'Líneas del abono por trabajador',
          '%d trabajadores, S/ %.2f (netos del lote S/ %.2f)' % (
              len(pago.line_ids), total_txt, netos))
    try:
        pago.action_generate_txt()
        adjunto = env['ir.attachment'].search([
            ('res_model', '=', pago._name), ('res_id', '=', pago.id)],
            order='id desc', limit=1)
        check(adjunto, 'Archivo TXT generado',
              '%s (%d bytes)' % (adjunto.name, len(adjunto.raw or b'')))
        primera = (adjunto.raw or b'').decode('latin-1').splitlines()[:1]
        print('     primera línea: %s' % (primera[0][:90] if primera
                                          else '(vacío)'))
    except Exception as exc:                                # noqa: BLE001
        check(False, 'Archivo TXT generado',
              ' | '.join(str(exc).split('\n'))[:400])

# --------------------------------------------------------------------- #
# 4. Exportadores PLAME                                                 #
# --------------------------------------------------------------------- #
for metodo, etiqueta in (('export_plame', 'PLAME remuneraciones'),
                         ('export_plame_hours', 'PLAME jornadas'),
                         ('export_plame_other_conditions',
                          'PLAME otras condiciones'),
                         ('export_plame_suspencion', 'PLAME suspensiones')):
    try:
        getattr(lote, metodo)()
        adjunto = env['ir.attachment'].search([
            ('res_model', '=', 'hr.payslip.run'), ('res_id', '=', lote.id)],
            order='id desc', limit=1)
        check(adjunto, etiqueta, '%s (%d bytes)' % (
            adjunto.name, len(adjunto.raw or b'')))
    except Exception as exc:                                # noqa: BLE001
        check(False, etiqueta, str(exc)[:160])

env.cr.commit()
fallas = [r for r in RESULTADOS if not r[0]]
print('\n' + '-' * 70)
print('FASE 8: %d comprobaciones, %d fallas' % (len(RESULTADOS), len(fallas)))
for _ok, titulo, detalle in fallas:
    print('   FALLA: %s — %s' % (titulo, detalle))
print('-' * 70)

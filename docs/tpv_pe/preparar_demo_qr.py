"""Datos DEMO para probar el cobro con QR de billetera en el TPV (odoo shell)::

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/tpv_pe/preparar_demo_qr.py

Crea (si no existen) una cuenta bancaria DEMO con un QR de ejemplo, el diario
«DEMO Yape», el método de pago «DEMO Yape / Plin» con el formato «QR de
billetera» y la caja «DEMO TPV Yape» con ese método (una caja aparte: Odoo no
deja cambiar los métodos de pago de una caja con la sesión abierta). El QR de
ejemplo solo contiene un texto: no cobra.
"""
import base64

company = env.company  # noqa: F821 (odoo shell)
Report = env['ir.actions.report']  # noqa: F821
qr_png = Report.barcode('QR', 'DEMO YAPE - QR de ejemplo, no cobra', width=400, height=400)
bank = env['res.partner.bank'].search([('acc_number', '=', 'DEMO-YAPE-0001')], limit=1)  # noqa: F821
if not bank:
    bank = env['res.partner.bank'].create({  # noqa: F821
        'acc_number': 'DEMO-YAPE-0001', 'partner_id': company.partner_id.id})
bank.l10n_pe_wallet_qr_image = base64.b64encode(qr_png)
journal = env['account.journal'].search([('code', '=', 'DYAPE'), ('company_id', '=', company.id)], limit=1)  # noqa: F821
if not journal:
    journal = env['account.journal'].create({  # noqa: F821
        'name': 'DEMO Yape', 'code': 'DYAPE', 'type': 'bank', 'company_id': company.id,
        'bank_account_id': bank.id})
# Cuenta de cobros pendientes: misma regla que el onchange del diario en
# point_of_sale (obligatoria para cerrar la caja).
chart = env['account.chart.template'].with_context(allowed_company_ids=company.root_id.ids)  # noqa: F821
outstanding = (chart.ref('account_journal_payment_debit_account_id', raise_if_not_found=False)
               or company.transfer_account_id)
method = env['pos.payment.method'].search([('name', '=', 'DEMO Yape / Plin')], limit=1)  # noqa: F821
if not method:
    method = env['pos.payment.method'].create({  # noqa: F821
        'name': 'DEMO Yape / Plin', 'journal_id': journal.id, 'company_id': company.id,
        'outstanding_account_id': outstanding.id,
        'payment_method_type': 'qr_code', 'qr_code_method': 'l10n_pe_wallet'})
config = env['pos.config'].search([('name', '=', 'DEMO TPV Yape')], limit=1)  # noqa: F821
if not config:
    config = env['pos.config'].create({  # noqa: F821
        'name': 'DEMO TPV Yape', 'company_id': company.id, 'payment_method_ids': [(6, 0, method.ids)]})
env.cr.commit()  # noqa: F821
print('Método', method.name, method.id, 'en', config.name, config.id, '| QR por defecto:', bool(method.default_qr))

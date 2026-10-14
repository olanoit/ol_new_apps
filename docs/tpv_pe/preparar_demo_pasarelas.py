"""Datos DEMO para cobrar en el TPV con las pasarelas (pago en línea nativo de
Odoo, ``pos_online_payment``), en odoo shell::

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
        < myodoo/ol_new_apps/docs/tpv_pe/preparar_demo_pasarelas.py

Crea el método «DEMO Pago en línea» con los proveedores publicados (Izipay,
Culqi o Niubiz en modo de prueba) y la caja «DEMO TPV Pasarelas». El cliente
escanea el QR del TPV, paga en su teléfono y el TPV recibe el pago solo.
Antes, Izipay en modo de prueba: docs/izipay/preparar_sandbox.py.
"""
company = env.company  # noqa: F821 (odoo shell)
providers = env['payment.provider'].search([  # noqa: F821
    ('code', 'in', ('izipay', 'culqi', 'niubiz')), ('state', 'in', ('test', 'enabled')),
    ('is_published', '=', True), ('company_id', '=', company.id)])
method = env['pos.payment.method'].search([('name', '=', 'DEMO Pago en línea')], limit=1)  # noqa: F821
if not method:
    method = env['pos.payment.method'].create({  # noqa: F821
        'name': 'DEMO Pago en línea', 'company_id': company.id, 'is_online_payment': True})
method.online_payment_provider_ids = providers
config = env['pos.config'].search([('name', '=', 'DEMO TPV Pasarelas')], limit=1)  # noqa: F821
if not config:
    config = env['pos.config'].create({  # noqa: F821
        'name': 'DEMO TPV Pasarelas', 'company_id': company.id,
        'payment_method_ids': [(6, 0, method.ids)]})
env.cr.commit()  # noqa: F821
print('Proveedores', providers.mapped('code'), '| método', method.id, '| caja', config.name, config.id)

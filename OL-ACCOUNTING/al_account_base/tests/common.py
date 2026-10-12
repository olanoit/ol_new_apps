# -*- coding: utf-8 -*-
"""Utilidades comunes para las pruebas de la suite.

Las pruebas de la localización necesitan una compañía peruana con el plan
contable de Perú (IGV 18 %, cuentas, diarios, tipos de documento). En una
base de desarrollo la compañía principal ya lo es; en una base nueva con
datos de demostración la compañía principal es la de Odoo (EE. UU.), así que
se usa la compañía demo de l10n_pe o, si no existe, una creada para la
prueba.
"""
from odoo import Command


def use_pe_company(cls):
    """Deja ``cls.env`` en una compañía peruana con el plan contable de Perú
    y la devuelve. Llamar al inicio de ``setUpClass``, antes de crear datos."""
    company = cls.env.user.company_id
    if company.chart_template == 'pe':
        return cls.env.company
    company = cls.env.ref('base.demo_company_pe', raise_if_not_found=False)
    if not company or company.chart_template != 'pe':
        company = cls.env['res.company'].create({
            'name': 'Compañía Perú (pruebas)',
            'country_id': cls.env.ref('base.pe').id,
            'currency_id': cls.env.ref('base.PEN').id,
        })
        cls.env['account.chart.template'].try_loading('pe', company=company, install_demo=False)
    # Como BaseCommon de Odoo: se cambia la compañía del usuario, no el
    # contexto; si no, ``allowed_company_ids`` pasaría a los ``with_user`` de
    # las pruebas y los usuarios de otra compañía darían AccessError.
    cls.env.user.write({'company_ids': [Command.link(company.id)], 'company_id': company.id})
    for cached in ('company', 'companies'):
        cls.env.__dict__.pop(cached, None)
    # La compañía demo de l10n_pe se crea antes que inventario y Odoo solo da
    # almacén a la primera compañía de la base: sin él no hay tipos de operación.
    Warehouse = cls.env.get('stock.warehouse')
    if Warehouse is not None and not Warehouse.search_count([('company_id', '=', company.id)], limit=1):
        Warehouse.create({'name': company.name, 'code': 'PE', 'company_id': company.id,
                          'partner_id': company.partner_id.id})
    return company

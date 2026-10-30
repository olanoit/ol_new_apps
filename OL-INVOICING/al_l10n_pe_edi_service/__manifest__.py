# -*- coding: utf-8 -*-
{
    'name': 'PE - Envío de otros CPE a SUNAT (AL)',
    'summary': 'Firma, envío y consulta de comprobantes que no son facturas '
               '(retención, percepción, liquidación de compra y sus reversiones) '
               'con el operador electrónico de la compañía.',
    'description': """
Servicio técnico sobre ``l10n_pe_edi`` (Odoo 20)
===============================================
En Odoo 20 ``l10n_pe_edi`` dejó ``account.edi.format``: sus servicios son
métodos de la factura. ``l10n_pe.edi.cpe.service`` arma lo mismo para
cualquier documento a partir de sus primitivas (credenciales, firma, zip,
SOAP e IAP): ``sendBill``, ``sendSummary``, ``getStatus`` y
``getStatusCdr``.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVOICING/Technical',
    'version': '20.0.1.0.0',
    'license': 'OPL-1',
    'depends': ['l10n_pe_edi'],
    'installable': True,
    'auto_install': False,
}

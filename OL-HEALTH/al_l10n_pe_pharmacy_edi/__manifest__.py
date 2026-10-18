# -*- coding: utf-8 -*-
{
    'name': 'PE - Farmacia: unidad SUNAT de las presentaciones (AL)',
    'summary': 'Código de unidad del comprobante electrónico (catálogo 03 de SUNAT) para la unidad '
               'de cada presentación: caja BX, frasco BO; las demás, el de la unidad del producto.',
    'description': """
PE - Farmacia: unidad SUNAT de las presentaciones
=================================================
Puente entre el maestro farmacéutico y la facturación electrónica de Perú:
la unidad «Caja x 100» que crea una presentación lleva el código de unidad
del catálogo 03 de SUNAT, así la boleta o factura que sale del TPV con la
línea en esa unidad tiene un unitCode válido.

Se instala solo cuando están al_pharmacy_base y l10n_pe_edi.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-HEALTH/Apps',
    'version': '1.20261018',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_base', 'l10n_pe_edi'],
    'installable': True,
    'application': False,
    'auto_install': True,
}

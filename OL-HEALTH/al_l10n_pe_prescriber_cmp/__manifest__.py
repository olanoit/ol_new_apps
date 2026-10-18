# -*- coding: utf-8 -*-
{
    'name': 'PE - Farmacia: consulta del médico en el CMP (AL)',
    'summary': 'Valida al médico prescriptor en el portal «Conoce a tu médico» del Colegio Médico '
               'del Perú: nombre, especialidad, consejo regional y si está hábil.',
    'description': """
PE - Farmacia: consulta del médico en el CMP
============================================
Botón «Consultar en el CMP» en el prescriptor (médico): con su colegiatura
consulta el portal público del Colegio Médico del Perú y completa nombre,
especialidad, consejo regional y estado (hábil o inhábil). Una receta de un
prescriptor inhábil no se valida.

Porta solo la consulta de al_peru_medico_data (Odoo 18), con lxml en lugar de
BeautifulSoup y sin su registro propio de médicos: el médico es el contacto
prescriptor. El portal no tiene API: si cambia, los datos se registran a mano.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_base/static/description/icon.png',
    'version': '1.20261018',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_prescription', 'l10n_pe'],
    'data': [
        'data/ir_config_parameter_data.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
}

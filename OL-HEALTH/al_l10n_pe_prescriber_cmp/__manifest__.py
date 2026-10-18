# -*- coding: utf-8 -*-
{
    'name': 'PE - Farmacia: verificación del médico en el CMP (AL)',
    'summary': 'Abre el portal «Conoce a tu médico» del Colegio Médico del Perú para buscar la '
               'colegiatura y registra si el médico está hábil, con fecha y responsable.',
    'description': """
PE - Farmacia: verificación del médico en el CMP
================================================
La receta debe llevar el nombre y la colegiatura del prescriptor (BPOF
7.5.2.9). El portal del Colegio Médico (https://conoceatumedico.cmp.org.pe)
pide iniciar sesión y reCAPTCHA desde 2026, así que no admite consultas
automáticas: el botón «Consultar en el CMP» lo abre y el químico
farmacéutico registra el resultado («Verificado: hábil» o «inhábil») con
fecha y responsable. Una receta de un prescriptor inhábil no se valida.

Reemplaza la lectura automática del portal antiguo de al_peru_medico_data
(Odoo 18), que ya no existe.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_base/static/description/icon.png',
    'version': '3.20261018',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_prescription', 'l10n_pe'],
    'data': [
        'data/ir_config_parameter_data.xml',
        'views/res_partner_views.xml',
    ],
    'demo': ['demo/prescriber_cmp_demo.xml'],
    'installable': True,
    'application': False,
}

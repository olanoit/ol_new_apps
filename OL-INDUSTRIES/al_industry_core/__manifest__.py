# -*- coding: utf-8 -*-
{
    'name': 'Industrias: registro (AL)',
    'summary': 'Registro de cada industria con su actividad CIIU, aplicable por compañía, '
               'sin comprobantes electrónicos: sirve también a los paquetes que no facturan '
               'desde Odoo.',
    'description': """
Industrias: registro
====================
El modelo de los paquetes ``al_industry_<rubro>``: cada paquete deja un
registro en Ajustes ▸ Usuarios y compañías ▸ Industrias con su actividad
económica principal (CIIU) y, si el rubro planifica obras, el perfil de
vertical del planificador. Se aplica a la compañía activa al instalar y a las
demás con el botón «Aplicar a la compañía activa»; solo completa lo que falta.

No instala comprobantes electrónicos: los paquetes que facturan desde Odoo
dependen de ``al_industry_base``, que agrega la localización completa de la
suite. Los paquetes que no facturan desde Odoo (ediciones Lite) dependen solo
de este módulo y funcionan en Odoo Community.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'icon': '/al_industry_core/static/description/icon.png',
    'version': '1.20261108',
    'license': 'OPL-1',
    'depends': [
        # Catálogo CIIU y actividades económicas del contacto (sin EDI).
        'l10n_pe_vat_sunat',
    ],
    'data': [
        'views/al_industry_views.xml',
        'security/ir.access.csv',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
}

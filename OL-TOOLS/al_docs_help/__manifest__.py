# -*- coding: utf-8 -*-
{
    'name': 'Ayuda contextual de la suite (AL)',
    'summary': 'Botón «?» en cada pantalla y asistente de la suite que abre '
               'la página que la explica en el sitio de documentación.',
    'description': """
Ayuda contextual
================
Cada pantalla de la suite AL lleva a la página de la documentación que la
explica, sin buscarla:

* Botón **?** en la barra superior: aparece en las pantallas de la suite
  (vistas de sus modelos y pantallas propias como el inicio del planificador)
  y abre la página de esa funcionalidad en la sección que corresponde.
* El mismo botón en la cabecera de los asistentes, junto a cerrar.
* También en pantallas oficiales que la suite amplía (facturas, pagos,
  contactos, empleados, contratos, boletas, tipos de cambio, transferencias).
* La ayuda solo aparece si el módulo que documenta la página está instalado.
* Sitio: la URL de Ajustes ▸ Perú ▸ Documentación (al_account_base) o, sin
  ella, https://docs.altalatam.com/latest/.
* Ajustes ▸ Técnico ▸ Ayuda contextual: la lista de pantallas, con su
  sección y un acceso a la página; se pueden agregar pantallas a mano.

La lista la genera ``scripts/gen_docs_help.py`` desde el código de cada
módulo y las páginas de la documentación que lo declaran (``modulos:``);
``docs/ayuda/ayuda_contextual.yml`` para las pantallas oficiales.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-TOOLS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/base/static/description/settings.png',
    'version': '8.20261022',
    'license': 'OPL-1',
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'data/al_docs_help_data.xml',
        'views/al_docs_help_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_docs_help/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
}

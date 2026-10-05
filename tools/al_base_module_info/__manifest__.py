# -*- coding: utf-8 -*-
{
    'name': 'Aplicaciones - Ficha completa del módulo (AL)',
    'summary': 'En Aplicaciones, el botón «Más información» de los módulos '
               'con ficha propia abre la ficha completa del módulo.',
    'description': """
Ficha completa del módulo en Aplicaciones
=========================================
En Aplicaciones, Odoo sanea la descripción del módulo y descarta sus estilos,
así que la ficha (``static/description/index.html``) se ve sin diseño. Las
fichas de la suite AL traen un enlace para abrirla completa; este módulo lleva
ese enlace a la tarjeta del kanban:

* El botón **Más información** de la tarjeta pasa a ser **Ver la ficha
  completa del módulo** cuando el módulo tiene ficha.
* El menú de la tarjeta suma la misma opción; «Más información» sigue
  llevando a la web del autor.
* Los módulos sin ficha (incluidos los de Odoo) no cambian.

Una ficha cuenta como tal cuando la ha preparado
``docs/validacion/fichas_modulos.py`` (lleva la marca ``al-ficha-link``).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-BASE/Apps',
    'version': '1.20260914',
    'license': 'OPL-1',
    'depends': ['base'],
    'data': [
        'views/ir_module_views.xml',
    ],
    'installable': True,
    'application': False,
}

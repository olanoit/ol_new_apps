# -*- coding: utf-8 -*-
{
    'name': 'Peru Holidays',
    'summary': "Calendario completo de 10 años de días festivos de Peru, listo para Odoo HR. Festivos nacionales y religiosos — aplicados automáticamente al resource.calendar como ausencias.",
    'description': """Peru 2026-2035 — Odoo HR

Calendario completo de 10 años de días festivos en Peru (2026-2035): festivos nacionales y religiosos integrados automáticamente en Odoo HR resource.calendar.

Este módulo carga automáticamente todos los días festivos oficiales de Peru para los años 2026 a 2035 en su sistema Odoo. Se incluyen festivos nacionales (fecha fija) y religiosos (fecha móvil) según las fuentes oficiales del país. Cada festivo está a un clic de ser añadido a todos los registros resource.calendar activos como entradas de ausencia, lo que permite calcular correctamente las asignaciones de vacaciones de los empleados desde el primer momento. Un ir.cron integrado vuelve a aplicar los festivos del nuevo año cada 2 de enero.

== Características principales ==

* 10 años de datos: Todos los festivos oficiales 2026-2035 a nivel federal / nacional.
* Integración Resource Calendar: Aplicación con un clic — todos los calendarios laborales activos reciben los festivos como ausencias.
* Cron anual automático: ir.cron integrado aplica el nuevo año automáticamente cada 2 de enero.
* Medio día / Día completo: Configurable por festivo, con marcas de tiempo conscientes de la zona horaria.
* Consciente de zona horaria: Las ausencias se almacenan en UTC pero respetan la zona horaria de cada calendario.
* Interfaz multilingüe: Traducciones de la interfaz para los idiomas oficiales de Peru.

== Requisitos ==

* Odoo 19.0
* Módulo estándar hr_holidays instalado
""",
     'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-TOOLS/Apps',
    'version': '3.20260827',
    'license': 'OPL-1',
    # hr_work_entry: los descansos del calendario llevan el tipo de entrada
    # de trabajo con el que la nómina computa el feriado.
    'depends': ['hr_holidays', 'hr_work_entry'],
    'data': [
        'security/ir.model.access.csv',
        'views/holidays_views.xml',
        'data/holidays_data.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

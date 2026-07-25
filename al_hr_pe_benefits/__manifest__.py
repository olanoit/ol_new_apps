# -*- coding: utf-8 -*-
{
    'name': 'Planillas Perú - Beneficios sociales (AL)',
    'summary': 'CTS, gratificaciones, liquidaciones, renta 5ta, provisiones, subsidios, utilidades, vacaciones, préstamos y quincena.',
    'description': """
Planillas Perú - Beneficios sociales (AL)
=========================================
Módulo del refactor de planillas v18 → v19 (27 módulos → 5); ver
``docs/planillas/PLAN_MIGRACION_PLANILLAS_V19.md``.

Fase 3:

* **CTS** (``hr.cts``): depósitos semestrales tipo '11' (may-oct) y
  '05' (nov-abr), con reserva de saldos de trabajadores con menos de
  un mes y exceso de descanso médico.
* **Gratificación** (``hr.gratification``): Fiestas Patrias ('07') y
  Navidad ('12'), con Bono Extraordinario EsSalud (Ley 29351).
* **Motor de beneficios** en ``hr.main.parameter``
  (``compute_benefits``): remuneración computable con promedios de
  variables (regla de las 3 apariciones), reutilizado por la
  liquidación de cese.

Fase 4 (actual):

* **Renta de 5ta categoría** (``hr.fifth.category``): proyección
  anual, tramos UIT generables, reproyección Art. 40 y excluidos.
* **Liquidación de cese** (``hr.liquidation``): truncos de CTS,
  gratificación y vacaciones + conceptos extra, con export a inputs.
* **Provisiones mensuales** (``hr.provisiones``): CTS, gratificación
  y vacaciones (solo cálculo; asientos en Fase 5).
* **Subsidios EsSalud** (``hr.subsidies``): enfermedad (20 días del
  empleador) y maternidad, con reparto mensual.
* **Utilidades D.L. 892** (``hr.utilities``): reparto 50 % días /
  50 % remuneraciones.
* **Adelantos y préstamos** (``hr.advance``/``hr.loan``): cuotas
  iguales a fin de mes e importación a boletas.
* **Quincena** (``hr.fortnightly``): generación de boletas
  quincenales y descuento en la mensual.

Los exportadores Excel y las boletas/certificados PDF llegan en la
Fase 7.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-PLANILLAS/Apps',
    'version': '3.20260722',
    'license': 'LGPL-3',
    'depends': ['al_hr_pe'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/hr_main_parameter_views.xml',
        'views/hr_cts_views.xml',
        'views/hr_gratification_views.xml',
        'views/hr_fifth_category_views.xml',
        'views/hr_vacation_views.xml',
        'views/hr_liquidation_views.xml',
        'views/hr_provisions_views.xml',
        'views/hr_subsidies_views.xml',
        'views/hr_utilities_views.xml',
        'views/hr_advances_loans_views.xml',
        'views/hr_fortnightly_views.xml',
    ],
    'installable': True,
    'application': False,
}

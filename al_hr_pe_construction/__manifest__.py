# -*- coding: utf-8 -*-
{
    'name': 'Planillas Perú - Construcción civil (AL)',
    'summary': 'Régimen de construcción civil: tabla salarial por convenio, '
               'categorías, BUC, BAE, bonificaciones por condiciones de '
               'trabajo, obras y CONAFOVICER.',
    'description': """
Planillas Perú - Construcción civil (AL)
========================================
El régimen de construcción civil no es el régimen general con otro
sueldo: se paga por **jornal diario** fijado por la convención colectiva
CAPECO-FTCCP, por categoría (operario, oficial, peón), con periodicidad
semanal, CTS y vacaciones pagadas en cada planilla, gratificaciones de 40
jornales y un aporte propio (CONAFOVICER 2 %).

Análisis y plan en ``docs/planillas/CONSTRUCCION_CIVIL_ANALISIS.md``.

Fase 1 — maestros:

* Categorías con su porcentaje de BUC (32 % operario, 30 % oficial y peón).
* **Tabla salarial con vigencia**: el convenio cambia cada año —y en 2026
  hasta cambió la ventana, de junio-mayo a enero-diciembre—, así que el
  jornal es un registro fechado, no una constante en el código.
* Catálogo de bonificaciones (BAE por especialidad y por condiciones de
  trabajo: altitud, contacto con agua, cota cero, altura), con importe
  fijo o porcentaje del jornal.
* Obras, con las bonificaciones que activa cada una.
* Campos en ``hr.version`` y **jornal calculado** desde la tabla vigente:
  un cambio de convenio no obliga a editar trabajador por trabajador.

Fase 2 — estructura salarial y reglas:

* Estructura ``CONSTRUCCIÓN CIVIL`` con jornal, D.S.O., BUC, movilidad,
  BAE, las bonificaciones por condiciones y el sobretiempo al 60 % y
  100 % (el régimen general va a 25/35: no se reutiliza).
* El **redondeo es el del convenio**: una sola vez sobre el importe del
  periodo, no multiplicando el diario redondeado por los días. En el
  oficial son seis céntimos por semana; en el operario los dos caminos
  coinciden por casualidad y esconden el error.
* Jornal congelado en la boleta, ajustable a mano.

Fase 3 — beneficios que este régimen paga con la planilla:

* Indemnización 15 % (la CTS de construcción), sobre el jornal del
  periodo más las horas extras a valor simple.
* Vacaciones 10 %.
* Gratificación proporcional de 40 jornales, con sus dos ventanas de
  devengo: 210 días hasta julio y 150 desde agosto.
* Bonificación extraordinaria de la Ley 30334 y asignación escolar, que
  toma los hijos de los derechohabientes de ``al_hr_pe``.
* Regla ``TREM`` con la base afecta, que **enumera** lo remunerativo: los
  beneficios sociales y la movilidad quedan fuera.

Fase 4 — periodicidad semanal:

* Generador de periodos semanales colgados de su mes, **cortados en el
  fin de mes** para que ninguna semana cruce dos declaraciones de PLAME.
* La boleta cae en el periodo más ajustado que la contenga.
* El lote semanal declara en su mes y la PLAME toma todas las boletas
  del periodo mensual.

Fase 5 — CONAFOVICER (D.L. 21067):

* Retención en cada boleta sobre el **jornal básico más el D.S.O.**: la
  tabla del convenio demuestra que la base no es solo el jornal (el
  operario retiene 12.50, y el 2 % del jornal serían 10.72).
* Resumen mensual que consolida las semanas, calcula el vencimiento del
  día 15 y exporta el detalle por trabajador para el depósito.

Fase 6 — boleta del régimen y aportes del empleador:

* Variante de la boleta legal que habla de **jornal, categoría y obra**
  en vez de sueldo mensual, sin tocar la del régimen general.
* EsSalud y SCTR (salud y pensión por separado) sobre la base afecta,
  con sus tasas por compañía y la cobertura marcada por trabajador: el
  SCTR se paga por quien está expuesto, no por toda la planilla.
* Total de descuentos y neto a pagar del régimen.

Datos cargados: tabla de la R.M. N.° 197-2025-TR (01/01/2026-31/12/2026).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-PLANILLAS/Apps',
    'version': '6.20260803',
    'license': 'LGPL-3',
    # `al_hr_pe_reports` no es opcional: la boleta del régimen hereda su
    # plantilla y el módulo extiende sus datos. Sin declararla, el orden
    # de carga es casual y los overrides de la boleta pueden perderse.
    'depends': ['al_hr_pe_benefits', 'al_hr_pe_reports'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/hr_construction_category_data.xml',
        'data/hr_construction_bonus_data.xml',
        'data/hr_construction_wage_table_data.xml',
        'data/hr_construction_structure_data.xml',
        'views/hr_construction_category_views.xml',
        'views/hr_construction_wage_table_views.xml',
        'views/hr_construction_bonus_views.xml',
        'views/hr_construction_site_views.xml',
        'views/hr_version_views.xml',
        'views/menu.xml',
        'views/hr_conafovicer_views.xml',
        'report/hr_construction_voucher_report.xml',
    ],
    'installable': True,
    'application': False,
}

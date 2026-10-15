OL-PROJECTS
===========

**Proyectos y obras.**

Para qué es esta carpeta
------------------------

Gestión de proyectos y obras: diagrama de Gantt (backend, portal web y asistente con IA) y requerimientos de materiales de obra con aprobación por niveles.

Qué va aquí
-----------

- Planificación de proyectos (Gantt, dependencias, línea base).
- Procesos de obra: requerimientos de materiales, despacho desde el almacén central y compras.

Qué no va aquí
--------------

- Planilla de construcción civil → `OL-PAYROLL/`.
- Dependencias de terceros (p. ej. `base_tier_validation`) → `OL-THIRD-PARTY/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_construction_attendance](al_construction_attendance/) | 2.20261013 | LGPL-3 | Sedes de obra con ubicación y horario, quiosco de marcación para personal propio y de contratas, asistencia diaria y costo de la planilla por obra, etapa y partida.
[al_construction_material_request](al_construction_material_request/) | 18.20261013 | LGPL-3 | El personal de obra pide materiales, se aprueba por niveles y lo disponible sale del almacén central; el faltante va a requerimiento de compra (OCA purchase_request).
[al_construction_planner](al_construction_planner/) | 33.20261013 | LGPL-3 | Plan de recursos de la obra para cualquier rubro: niveles, etapas, tipos de recurso y recetas configurables, con perfiles de vertical y funciones que se activan por puentes.
[al_construction_planner_budget](al_construction_planner_budget/) | 1.20261013 | LGPL-3 | Presupuesto analítico al aprobar el plan y control de la OC contra el presupuesto.
[al_construction_planner_crew](al_construction_planner_crew/) | 2.20261013 | LGPL-3 | Asignar cuadrilla con turnos de Planificación y horas de la hoja de horas como real.
[al_construction_planner_furniture](al_construction_planner_furniture/) | 2.20261013 | LGPL-3 | Tipologías de mueble con módulos, metros lineales y lista de materiales, generar plan desde la tipología e importación del maestro y del ETO.
[al_construction_planner_mrp](al_construction_planner_mrp/) | 2.20261013 | LGPL-3 | Órdenes de fabricación desde el plan, etapa de consumo en la lista de materiales y espera del metrado.
[al_construction_planner_purchase](al_construction_planner_purchase/) | 2.20261013 | LGPL-3 | Compra masiva, requerimiento de obra, abastecimiento de la obra, precios de compra, crear producto y material extra.
[al_construction_planner_sale](al_construction_planner_sale/) | 2.20261013 | LGPL-3 | Calendario e ingresos, contratos de obra con hitos, entrega semanal, valorización, cobranza y cronograma valorizado.
[al_construction_planner_sale_furniture](al_construction_planner_sale_furniture/) | 1.20261013 | LGPL-3 | Partidas del contrato por familia de la tipología (cocinas, closets…).
[al_construction_planner_spreadsheet](al_construction_planner_spreadsheet/) | 1.20261013 | LGPL-3 | Maestro de planificación de la obra como hoja de cálculo de Documentos, con listas de Odoo de referencia y el menú «Enviar al planificador».
[al_construction_planner_subcontract](al_construction_planner_subcontract/) | 1.20261013 | LGPL-3 | Asignar contrata con su OC de servicio, avance por driver, liquidación semanal y portal de la contrata.
[al_construction_planner_subcontract_purchase](al_construction_planner_subcontract_purchase/) | 1.20261013 | LGPL-3 | Descuento a la contrata del material extra en su liquidación semanal.
[al_construction_planner_suite](al_construction_planner_suite/) | 2.20261013 | LGPL-3 | Instala el planificador con todos sus puentes (perfil mobiliario completo) y reúne las pruebas de integración.
[al_project_gantt_ai](al_project_gantt_ai/) | 8.20261013 | OPL-1 | Panel de chat opcional para consultar el diagrama de Gantt y recibir propuestas de cambio que el usuario revisa y aplica.
[al_project_gantt_backend](al_project_gantt_backend/) | 17.20261013 | OPL-1 | Aplicación de Gantt interactivo dentro del backend de Odoo, con menú propio y carga perezosa de la librería.
[al_project_gantt_base](al_project_gantt_base/) | 18.20261011 | OPL-1 | Capa de datos, mapeo de campos, seguridad y librería Gantt compartidas por las interfaces de Gantt (backend y website).
[al_project_gantt_website](al_project_gantt_website/) | 12.20261008 | OPL-1 | Página de Gantt en el sitio web, restringida a usuarios internos autenticados.
[//]: # (end addons)

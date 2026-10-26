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
[al_construction_attendance](al_construction_attendance/) | 5.20261021 | LGPL-3 | Sedes de obra con ubicación y horario, quiosco de marcación para personal propio y de contratas, asistencia diaria y costo de la planilla por obra, etapa y partida.
[al_construction_material_request](al_construction_material_request/) | 28.20261024 | LGPL-3 | El personal de obra pide materiales, se aprueba por niveles y lo disponible sale del almacén central; el faltante va a requerimiento de compra (OCA purchase_request).
[al_construction_planner](al_construction_planner/) | 52.20261025 | LGPL-3 | Plan de recursos de la obra para cualquier rubro: niveles, etapas, tipos de recurso y recetas configurables, con perfiles de vertical y funciones que se activan por puentes.
[al_construction_planner_approvals](al_construction_planner_approvals/) | 7.20261021 | LGPL-3 | Plan de recursos y requerimiento de obra aprobados en la aplicación Aprobaciones, con tabla de rutas por tramos y aprobadores por grupo.
[al_construction_planner_approvals_mrp](al_construction_planner_approvals_mrp/) | 7.20261024 | LGPL-3 | Exceso de la orden de fabricación frente a lo presupuestado: el jefe de producción lo aprueba dentro de su margen y, por encima, va a Aprobaciones.
[al_construction_planner_budget](al_construction_planner_budget/) | 4.20261016 | LGPL-3 | Presupuesto analítico al aprobar el plan y control de la OC contra el presupuesto.
[al_construction_planner_crew](al_construction_planner_crew/) | 4.20261016 | LGPL-3 | Asignar cuadrilla con turnos de Planificación, en horas o en días con costo diario por puesto, y horas de la hoja de horas como real.
[al_construction_planner_furniture](al_construction_planner_furniture/) | 12.20261021 | LGPL-3 | Tipologías de mueble con módulos, piezas, método de unión y lista de materiales, productos por módulo, receta real y despacho a obra, e importación del maestro, del ETO y de la proyección de materiales.
[al_construction_planner_mrp](al_construction_planner_mrp/) | 12.20261024 | LGPL-3 | Órdenes de fabricación desde el plan, etapa de consumo en la lista de materiales y espera del metrado.
[al_construction_planner_mrp_request](al_construction_planner_mrp_request/) | 3.20261025 | LGPL-3 | Planchas enteras y retazo en el despacho del requerimiento, despacho a la preproducción de la planta y reposición a planta.
[al_construction_planner_production](al_construction_planner_production/) | 5.20261019 | LGPL-3 | Accesorios de armado pedidos desde la orden y presupuestado, requerido y consumido en la orden y en el planificador.
[al_construction_planner_purchase](al_construction_planner_purchase/) | 15.20261024 | LGPL-3 | Compra masiva, requerimiento de obra, abastecimiento de la obra, precios de compra, crear producto y material extra.
[al_construction_planner_sale](al_construction_planner_sale/) | 7.20261016 | LGPL-3 | Calendario e ingresos, contratos de obra con hitos, entrega semanal, valorización, cobranza y cronograma valorizado.
[al_construction_planner_sale_furniture](al_construction_planner_sale_furniture/) | 1.20261013 | LGPL-3 | Partidas del contrato por familia de la tipología (cocinas, closets…).
[al_construction_planner_spreadsheet](al_construction_planner_spreadsheet/) | 4.20261016 | LGPL-3 | Presupuesto, APU y plan de la obra en una hoja de cálculo de Documentos, con las hojas del libro de carga, validación, «Enviar al planificador» y versiones.
[al_construction_planner_spreadsheet_furniture](al_construction_planner_spreadsheet_furniture/) | 1.20261024 | LGPL-3 | Maestro de mobiliario (tipologías, muebles, módulos, piezas, BOM) en la hoja de trabajo de la obra, con «Enviar al planificador» al importador del maestro y ETO.
[al_construction_planner_subcontract](al_construction_planner_subcontract/) | 11.20261016 | LGPL-3 | Asignar contrata con su OC de servicio, avance por driver, liquidación semanal y portal de la contrata.
[al_construction_planner_subcontract_purchase](al_construction_planner_subcontract_purchase/) | 2.20261013 | LGPL-3 | Descuento a la contrata del material extra en su liquidación semanal.
[al_construction_planner_subcontract_sale](al_construction_planner_subcontract_sale/) | 1.20261023 | LGPL-3 | Adicionales de la contrata desde el cambio de obra y margen de compra por partida.
[al_construction_planner_suite](al_construction_planner_suite/) | 21.20261023 | LGPL-3 | Instala el planificador con todos sus puentes (perfil mobiliario completo) y reúne las pruebas de integración.
[al_construction_portal](al_construction_portal/) | 3.20261025 | LGPL-3 | Portal instalable y sin señal para capataces, contratas y oficina técnica: avance con fotos, parte diario, cuadrilla y tareo, requerimientos, recepción, devolución y valorizaciones, sobre servicios JSON versionados.
[al_project_gantt_ai](al_project_gantt_ai/) | 8.20261013 | OPL-1 | Panel de chat opcional para consultar el diagrama de Gantt y recibir propuestas de cambio que el usuario revisa y aplica.
[al_project_gantt_backend](al_project_gantt_backend/) | 17.20261013 | OPL-1 | Aplicación de Gantt interactivo dentro del backend de Odoo, con menú propio y carga perezosa de la librería.
[al_project_gantt_base](al_project_gantt_base/) | 18.20261011 | OPL-1 | Capa de datos, mapeo de campos, seguridad y librería Gantt compartidas por las interfaces de Gantt (backend y website).
[al_project_gantt_website](al_project_gantt_website/) | 12.20261008 | OPL-1 | Página de Gantt en el sitio web, restringida a usuarios internos autenticados.
[//]: # (end addons)

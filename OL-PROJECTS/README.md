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
[al_construction_material_request](al_construction_material_request/) | 9.20261009 | LGPL-3 | El personal de obra pide materiales, se aprueba por niveles y lo disponible sale del almacén central; el faltante va a requerimiento de compra (OCA purchase_request).
[al_construction_planner](al_construction_planner/) | 7.20261010 | LGPL-3 | Plan de recursos por obra, piso, departamento, ambiente y módulo: materiales, contratas a destajo, personal propio y producción, generado desde las tipologías de la obra.
[al_project_gantt_ai](al_project_gantt_ai/) | 6.20261010 | OPL-1 | Panel de chat opcional para consultar el diagrama de Gantt y recibir propuestas de cambio que el usuario revisa y aplica.
[al_project_gantt_backend](al_project_gantt_backend/) | 15.20261010 | OPL-1 | Aplicación de Gantt interactivo dentro del backend de Odoo, con menú propio y carga perezosa de la librería.
[al_project_gantt_base](al_project_gantt_base/) | 17.20261010 | OPL-1 | Capa de datos, mapeo de campos, seguridad y librería Gantt compartidas por las interfaces de Gantt (backend y website).
[al_project_gantt_website](al_project_gantt_website/) | 12.20261008 | OPL-1 | Página de Gantt en el sitio web, restringida a usuarios internos autenticados.
[//]: # (end addons)

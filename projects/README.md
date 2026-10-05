projects
========

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

- Planilla de construcción civil → `payroll/`.
- Dependencias de terceros (p. ej. `base_tier_validation`) → `third_party/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_construction_material_request](al_construction_material_request/) | 4.20261001 | LGPL-3 | El personal de obra pide materiales, se aprueba por niveles y lo disponible sale del almacén central; el faltante va a requerimiento de compra (OCA purchase_request).
[al_project_gantt_ai](al_project_gantt_ai/) | 3.20260817 | OPL-1 | Panel de chat opcional para consultar el diagrama de Gantt y recibir propuestas de cambio que el usuario revisa y aplica.
[al_project_gantt_backend](al_project_gantt_backend/) | 12.20260818 | OPL-1 | Aplicación de Gantt interactivo dentro del backend de Odoo, con menú propio y carga perezosa de la librería.
[al_project_gantt_base](al_project_gantt_base/) | 14.20260818 | OPL-1 | Capa de datos, mapeo de campos, seguridad y librería Gantt compartidas por las interfaces de Gantt (backend y website).
[al_project_gantt_website](al_project_gantt_website/) | 11.20260818 | OPL-1 | Página de Gantt en el sitio web, restringida a usuarios internos autenticados.
[//]: # (end addons)

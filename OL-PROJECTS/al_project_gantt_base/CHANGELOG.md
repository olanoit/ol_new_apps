Historial de cambios — Gantt de Proyectos — Base (AL)
=====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_project_gantt_base.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 16.20261008 — 08/10/2026

- Etiquetas en español: los campos sin etiqueta propia (Activo, Nombre, Compañía, contadores…) y los heredados de Odoo (Creado por, Mensajes, Actividades…) ya no se muestran en inglés.

## 15.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 14.20260818 — 27/09/2026

- Editar una subtarea cuyo padre no se ve (por un filtro o por el límite de tareas) ya no la separa de su padre: solo se guarda lo que de verdad se cambió.
- El avance de las tareas con partes de horas se muestra en su porcentaje real (antes salía 100 veces menor) y ya no se ofrece editarlo: lo calcula Odoo a partir de las horas.
- Sin el módulo de planificación de Odoo Enterprise ya se pueden editar las tareas desde el diagrama: se guarda la fecha límite y el inicio estimado se ignora.
- Las líneas base ya no dejan ver tareas de proyectos privados; solo el administrador del Gantt accede a ellas fuera del diagrama. De una línea base solo se puede cambiar el nombre.
- Excel, PDF y filtros de fecha usan la hora de cada usuario: una fecha límite a última hora ya no aparece al día siguiente.
- La reprogramación en cadena empuja también las tareas que dependen de dos predecesoras, y la ruta crítica se calcula por proyecto cuando se ven varios a la vez.
- Los colores por estado solo admiten hexadecimal o un nombre de color, y no puede haber dos colores globales para el mismo estado.
- El informe PDF solo aparece en Imprimir para quien tiene acceso al Gantt.

## 25/08/2026

- Licencia OPL-1 en toda la suite.

## 18/08/2026

- Primera versión: contrato de datos y de escritura, mapeo de campos, colores por estado, seguridad, ruta crítica, líneas base, calendario laboral, exportación a Excel y PDF y librería dhtmlxGantt 10.0.1.

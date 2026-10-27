Historial de cambios — Gantt de Proyectos — Backend (AL)
========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_project_gantt_backend.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 19.20261027 — 27/10/2026

- Recupera su ícono original; el isotipo de ALTA queda solo para los módulos que no tenían ícono.

## 18.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 17.20261013 — 13/10/2026

- Ícono propio de la app «Gantt» con el estilo de Odoo 19: icon.svg de 50×50 con formas planas y la paleta de Odoo, e icon.png de 100×100 sin fondo.

## 16.20261011 — 11/10/2026

- Modo oscuro: el diagrama (dhtmlxGantt), la barra de herramientas, el formulario de tarea, el menú contextual y las marcas de la ruta crítica, la línea base y los días no laborables toman los colores del tema oscuro de Odoo; el modo claro no cambia.

## 15.20261010 — 10/10/2026

- Puntos de extensión para pantallas que reutilizan el diagrama heredando su componente (como el cronograma de la planificación de obra): opciones extra para los datos, filas y columnas propias, casillas de selección en cascada con barra de selección y botones propios, y paneles a la derecha y debajo del diagrama. Sin heredarlo, el Gantt se ve y funciona igual.

## 14.20261009 — 09/10/2026

- Ícono propio en el menú principal (barras escalonadas de un diagrama de Gantt), con el estilo del de la app Perú (fondo de color y trazo blanco), para no confundirlo con la app oficial de Proyecto; en Aplicaciones sigue el ícono nativo.

## 13.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 12.20260818 — 27/09/2026

- Al desmarcar un proyecto ya no desaparece de la barra: se puede volver a marcar, y «Todos» recupera todos los proyectos visibles.
- Arrastrar una barra solo guarda sus fechas; ya no reescribe responsables, etiquetas ni horas con lo que había en pantalla.
- Al cambiar de proyecto, el formulario de la tarea ofrece las etapas y personas del proyecto nuevo.
- Las tareas creadas desde la fila de un proyecto se crean en ese proyecto.

## 25/08/2026

- Licencia OPL-1 en toda la suite.

## 18/08/2026

- Primera versión: diagrama con filtros, edición, ruta crítica, línea base, encadenado, herramientas de vista, formulario de tarea, menú contextual, actividades y exportación a Excel y PDF.

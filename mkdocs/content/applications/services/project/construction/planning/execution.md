---
modulos: [al_construction_planner, al_construction_planner_subcontract, al_construction_planner_crew, al_construction_planner_purchase, al_construction_planner_sale, al_construction_attendance]
---

# Ejecución: tablero de obra y menú Ejecutar

La ejecución se lanza desde dos entradas que llaman a los mismos asistentes con
la obra, el plan vigente y la tarea precargados. Cada una tiene su ajuste en
**Ajustes ‣ Planificación de obra ‣ Entradas a la ejecución** (las dos activas
al instalar); apagarla no borra datos.

## Ejecución en Planificación de obra

- El menú se ordena por momento: **Obras** (obras, tareas, cronograma, Gantt),
  **Planificación** (planes, recursos planificados, árbol, etapas del
  cronograma), **Ejecución** (contratas, personal propio, abastecimiento,
  avance y cambios), **Ingresos**, **Informes** y **Configuración**. Con el
  ajuste apagado se ve el menú de siempre.
- **Obras ‣ Obras** abre el **tablero de obra**: plan vigente, avance físico,
  indicadores (con Ve montos) y botones para ejecutar, controlar y cobrar, cada
  uno con su contador. **Abrir en Proyectos** lleva a la ficha nativa.
- **Obras ‣ Tareas de la obra** abre la **tarea de obra** con los niveles de la
  plantilla, sus recursos y avances, y el botón **Ejecutar**: asignar contrata o
  cuadrilla, pedir material, registrar avance, cambio o deductivo.

## Ejecución desde Proyectos

El tablero de un proyecto que es obra agrega la sección **Obra** (plan de
recursos, control de saldo, asignar contrata y cuadrilla, pedir material,
órdenes y valorizaciones de contrata, deductivos, cambios, requerimientos y
valorizaciones al cliente), y la tarea de Proyectos muestra **Ejecutar**. Cada
botón respeta los grupos del usuario. Los demás proyectos no cambian.

## En el celular

La tarea y sus acciones (registrar avance con fotos y ubicación, pedir
material, registrar cambio) funcionan en la vista móvil de Odoo.

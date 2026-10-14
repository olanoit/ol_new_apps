---
modulos: [al_construction_planner]
---

# Metrado del ambiente

Antes de fabricar, el supervisor mide en obra cada ambiente y anota la medida
real en la unidad de cada driver: metros lineales de mueble bajo, metros
lineales de mueble alto y cantidad de módulos. El planificador la compara con
lo planificado y valoriza la diferencia. Si hay diferencia, la Jefatura de
Proyectos la aprueba antes de lanzar la orden de fabricación del ambiente.

## Conceptos

| Término | Significado |
|---|---|
| Metrado | La medida real de un ambiente, una por ambiente, con su estado: **Borrador**, **En aprobación** o **Aprobado** |
| Planificado | Los ML de mueble bajo y alto de la tipología del ambiente y la cantidad de módulos del ambiente |
| Costo por unidad | Monto planificado de las líneas de contrata y personal propio que dependen de ese driver (instalación por ML, armado por módulo…) entre lo planificado |
| Diferencia en soles | Diferencia de la medida × costo por unidad |

Lo que no se mide por ML ni por módulo (materiales, colocación de puertas,
entarugado) no entra en la diferencia en soles: si el metrado cambia el
mueble, se ajusta con una variante de la unidad o un cambio del plan.

## Registrar el metrado

1. Vaya a **Planificación de obra ‣ Ejecución ‣ Avance ‣ Generar metrados**.
2. Elija la obra y, si quiere, los pisos, departamentos o ambientes. Vacío
   toma todos los ambientes de la obra que aún no tienen metrado.
3. Haga clic en **Generar**: se crea el metrado de cada ambiente en borrador,
   con lo planificado como medida inicial, y se abren sus medidas en una lista
   agrupada por piso y ambiente.
4. Escriba la columna **Medido** de cada ambiente.

Para cargar muchos ambientes desde Excel, exporte la lista (**Acción ‣
Exportar**, con la opción de importación compatible), complete **Medido** y
vuelva a importarla con **Importar registros**. La misma lista está siempre en
**Avance ‣ Cargar medidas**.

Un metrado se puede abrir también uno por uno en **Avance ‣ Metrados**.

## Enviar y aprobar

1. En **Avance ‣ Metrados**, marque los metrados terminados y use **Acción ‣
   Enviar metrados** (o **Enviar** en cada uno).
2. Sin diferencia, el metrado queda **Aprobado** al enviarlo.
3. Con diferencia, queda **En aprobación** y pide la revisión «Metrado con
   diferencia: jefatura de proyectos». La Jefatura lo **Aprueba** o lo
   **Rechaza**; rechazado, vuelve a **Borrador** para corregir la medida.

Ejemplo: en una cocina tipo 01 planificada con 2.12 ML de mueble bajo, el
supervisor mide 2.90 ML.

| Driver | Planificado | Medido | Diferencia | Costo por unidad | Diferencia en soles |
|---|---:|---:|---:|---:|---:|
| ML de mueble bajo | 2.12 | 2.90 | 0.78 | 18.00 | 14.04 |
| ML de mueble alto | 2.10 | 2.10 | 0.00 | 18.00 | 0.00 |
| Módulos | 7 | 7 | 0 | 7.7143 | 0.00 |
| **Total** | | | | | **14.04** |

## La orden de fabricación espera la aprobación

El asistente **Orden de fabricación** deja fuera los ambientes con un metrado
con diferencia que todavía no está aprobado, con el aviso «Metrado con
diferencia por aprobar». Cuando la Jefatura lo aprueba, el ambiente vuelve a
aparecer en el asistente. Los ambientes sin metrado o con metrado sin
diferencia no se detienen.

!!! note "Nota"
    Un metrado aprobado se puede volver a borrador para corregirlo mientras su
    ambiente no tenga una orden de fabricación.

!!! info "Ver también"
    - [Asignaciones y compras](supply.md)
    - [Niveles de la obra y tipologías](levels_typologies.md)

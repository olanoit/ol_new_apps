---
modulos: [al_construction_planner]
---

# Árbol de recursos

El **Árbol de recursos** muestra la obra como árbol (obra › piso › departamento ›
ambiente › módulo) con los recursos de cada nivel acumulados: módulos, ML,
material, contrata, total y avance. Permite seleccionar en cascada un piso, un
departamento o un ambiente y actuar sobre toda la selección: comprar, pedir,
fabricar, asignar contratas o cuadrillas, registrar avance o cambiar fechas, y
ver sus recursos como [matriz insumo-producto](#matriz-insumo-producto).

![Árbol con una selección parcial y el panel de recursos acumulados](resource_tree/partial-selection.png)

## Recorrer el árbol

1. Vaya a **Planificación de obra ‣ Obras ‣ Plan de recursos ‣ Árbol de recursos**, o haga clic en
   **Árbol de recursos** en el plan.
2. Abra cada nivel con la flecha: se carga a demanda, para que una obra con
   miles de módulos siga siendo ágil. Cada fila trae sus módulos, ML, material,
   contrata y total.
3. Cambie la **Medida**: soles, cantidad de driver o avance.
4. Use los **Filtros**: etapa, tipo de recurso, estado del módulo y contrata.
   Las etapas se eligen en un árbol con casillas: marcar **1 Producción**
   marca 1.1 Producción de piezas y 1.2 Armado; desmarcar una de ellas deja a
   la etapa padre en selección parcial.

Las columnas toman el nombre de los niveles de la plantilla de la obra
(«Actividades» en lugar de «Módulos» en una obra por partidas). **Tipología**
y **ML** solo aparecen en las obras con tipologías o metros lineales.

En el piso 05 de la demostración:

| Fila | Módulos | ML | Material | Contrata | Total |
|---|---|---|---|---|---|
| Piso 05 | 66 | 41.33 | 6,642.91 | 2,301.53 | 8,944.44 |
| Dpto 501 | 7 | 4.22 | 735.29 | 258.37 | 993.66 |

Con el filtro de etapa **2.1 Instalación**, el piso 05 muestra S/ 941.17 de
contrata.

!!! note "Nota"
    El filtro **Estado del módulo** solo aplica a lo que cuelga de un módulo:
    con él, no se ven la instalación ni las actividades por ambiente.

## Seleccionar

- **Marcar** un piso marca todos sus departamentos, ambientes y módulos. La
  barra de selección muestra, por ejemplo, «66 módulos · 8 ambientes · 41.33 ML
  · S/ 8,944.44».
- **Desmarcar** un módulo deja al ambiente, al departamento y al piso con un
  guion (selección parcial), y la barra pasa a 65 módulos.
- El panel **Recursos acumulados de la selección** agrupa los recursos por
  tipo de recurso, en el orden del catálogo (materiales, contratas, personal
  propio, equipo, servicios y producción). Cada grupo muestra su subtotal en
  cantidad y en soles, y el panel su total. Dentro de cada grupo, cada
  actividad, material o rol lleva su cantidad de driver, lo ejecutado, el
  monto y la contrata asignada («sin asignar» si falta). **Por etapa**
  subagrupa cada tipo por etapa y sub etapa; **Sin etapas** vuelve a la lista
  simple. El panel respeta el filtro de etapas. **Ver solo lo que no tiene
  contrata** filtra contratas y personal sin asignar.
- Los botones de la barra abren los asistentes sobre la selección: compra
  masiva, requerimiento de obra, orden de fabricación, asignar contrata,
  asignar cuadrilla, registrar avance y cambiar fechas.

## Matriz insumo-producto

La matriz muestra los recursos planificados como tabla: una fila por elemento
del alcance y una columna por insumo (producto, actividad o rol, con su
unidad). Las columnas se agrupan, con subtotales, por etapa › sub etapa y,
dentro, por tipo de recurso.

1. Ábrala con **Insumo-producto** en la barra del árbol o del
   [cronograma](schedule.md) (toma la selección y el filtro de etapas) o con el
   botón **Insumo-producto** del plan (toda la obra).
2. En **Filas**, elija el nivel: módulo, mueble, ambiente, departamento o piso
   en mobiliario; partida o subpartida en una obra por partidas.
3. Elija qué se ve: **Planificado**, **Comprometido**, **Real** o **Saldo**, en
   **Soles** o en **Cantidad**.
4. Use el filtro de etapas y pliegue las columnas con **Por etapa**, **Por
   tipo** o **Insumos** (o haciendo clic en el encabezado de cada grupo).
   **Toda la obra** quita la selección.
5. **Exportar a Excel** descarga la matriz con la misma agrupación.

Cada fila suma el costo del elemento y cada columna el insumo en toda la
selección. El nombre de la fila abre la tarea. Lo que cuelga de un nivel
superior al elegido se reúne en la fila «Fuera del nivel».

## Avance de cada nivel

El avance de un nivel es **valorizado**: Σ ejecutado × costo ÷ Σ planificado de
las contratas y el personal propio del nivel. Pondera por valor porque las
unidades de driver de distintas actividades no se suman. Nadie escribe un
porcentaje: la contrata reporta unidades de driver y el sistema compara contra
lo presupuestado (ver [Contratas](contractors.md)).

### Avance por el driver de la partida

En una obra por partidas, el nivel con etapas (la partida) avanza por su
**driver**: la cantidad ejecutada entre la **Cantidad presupuestada**. Cuentan
las contratas y la cuadrilla cuya actividad tiene **Driver: El de la partida**
(ver [Catálogo y árbol de la obra](catalog.md#actividades-y-tarifas)),
ponderadas por valor. Una actividad con driver propio avanza y se liquida en
su unidad sin mover el avance de la partida.

Ejemplo: una partida de muro drywall de 120 m² con 48 m² ejecutados muestra
40 %. Su contrata de emplacado, con driver propio en m² de placa, muestra su
propio avance.

La pestaña **Obra** de la partida muestra la **Cantidad presupuestada**, el
driver, lo **Ejecutado en el driver** y el **Avance por driver**. Con un filtro
de etapa o de tipo de recurso, el árbol vuelve al avance valorizado.

La pestaña **Recursos y avance** de cada piso, departamento, ambiente o módulo
(en **Proyecto**) muestra sus líneas con lo planificado, lo ejecutado y el
avance.

![Pestaña Recursos y avance de un ambiente con sus líneas](resource_tree/level-resources-progress.png)

El estado del módulo sigue al avance validado: con todo su armado validado pasa
a **Producido**; con toda la instalación de su ambiente (o del módulo, si las
actividades cuelgan de él), a **Instalado**.

!!! info "Ver también"
    - [Asignaciones y compras](supply.md)
    - [Contratas y liquidación semanal](contractors.md)
    - [Planificación de obra](../planning.md)

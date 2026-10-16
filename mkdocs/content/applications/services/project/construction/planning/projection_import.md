---
modulos: [al_construction_planner_furniture]
---

# Importar la proyección de materiales

El asistente **Importar la proyección de materiales** trae al planificador las
obras de mobiliario que ya se proyectaron en Excel: lee las hojas de
proyección en su formato de siempre y carga la receta planificada de cada
módulo, con sus piezas y sus consumos por material. Antes de escribir valida
cada código de producto contra el maestro de Odoo. Las obras nuevas se arman
en la [hoja de trabajo](planning_worksheet.md) y no pasan por este asistente.

## El libro de proyección

El asistente lee las dos variantes de la hoja de proyección:

| Rubro | Formato |
|---|---|
| Cocinas | Una pestaña por tipología («COCINA 04») y un bloque «MODULO:» por módulo, con los nombres y códigos de los materiales, las filas de piezas y la fila «Total». La marca «MODULO ALTO» separa los módulos altos de los bajos |
| Closet, baño, lavandería, ducto y estacionamiento | Una pestaña con un bloque por tipología completa («CL-01») |

La pestaña resumen («… POR PISO») trae la fila de etapas sobre cada columna
de material (PRODUCCIÓN, ARMADO, INSTALACIÓN, ACABADOS, LIMPIEZA), los nombres
cortos, los códigos y los nombres completos, y qué tipología lleva cada unidad:
por departamento («COCINA 04_DEP 104»), por piso (ductos), por sótano
(estacionamientos) o por tipología con cantidad. Las pestañas CODIGOS,
FORMULARIO, LEEME y RESUMEN no se leen.

## Importar

1. Vaya a **Planificación de obra ‣ Configuración ‣ Plan de obra ‣ Importar la
   proyección de materiales**.
2. Elija la **Obra**, suba la **Hoja de proyección (.xlsx)** y deje marcado
   **Crear el árbol de la obra** si quiere crear los pisos, las unidades y los
   ambientes del resumen.
3. Haga clic en **Leer el libro**. Sin escribir nada, el asistente propone la
   **Familia** del libro y muestra:
    - **Se importará**: tipologías, módulos, piezas, columnas de material,
      unidades del resumen y pisos;
    - los **Avisos** del libro;
    - una fila por columna de material con su código en las pestañas, su
      código en el resumen, su **Sub etapa** y el **Producto** de Odoo que le
      corresponde, con su **Control**.
4. Resuelva las columnas marcadas (ver [Validación de
   códigos](#validación-de-códigos)) y, si cambió el libro, use **Volver a
   leer**.
5. Haga clic en **Importar**. Se abre la lista de las tipologías importadas y
   el historial de la obra registra la importación.

Al importar:

- cada tipología se crea o se actualiza por su código: lo que trae el libro
  queda exactamente así;
- en cocinas, la tipología lleva un **Mueble bajo** y un **Mueble alto** con
  sus módulos; en los demás rubros, el bloque es un **Mueble completo** con un
  solo módulo;
- cada módulo lleva su nombre, su ancho (tomado del nombre), sus **Piezas** y
  sus **Materiales** con la sub etapa de consumo, y el [método de
  unión](furniture.md#método-de-unión) que proponen las reglas;
- con **Crear el árbol de la obra**, cada unidad del resumen queda en su piso
  con un ambiente por tipología. Las agrupaciones sin departamento (ductos por
  piso, estacionamientos por sótano) cuelgan del piso. Lo que ya existe no se
  duplica.

### Validación de códigos

Cada columna de material con consumo se cruza con el maestro de productos de
Odoo:

| Control | Qué pasa |
|---|---|
| Correcto | El código existe y el nombre coincide |
| Sin código | La columna no tiene código |
| Código inexistente en Odoo | Ningún código de la columna existe en el maestro |
| Códigos de productos distintos | El código de las pestañas y el del resumen llevan a productos distintos, o uno no existe |
| El nombre no coincide | El código existe, pero con otro nombre |
| Resuelto a mano | Se eligió o se aceptó el producto |

Para resolver una columna, elija el **Producto** o acepte el propuesto con
**Aceptar**. Mientras quede una columna sin resolver, **Importar** no guarda
nada y lista cada columna con su código y su problema.

!!! warning "Importante"
    Revise el producto de las columnas **Códigos de productos distintos**: es
    el caso de un mismo material con un código en la pestaña de la tipología y
    otro en el resumen.

### Avisos

| Aviso | Qué pasa |
|---|---|
| Columna fuera del rango que suma el resumen | Se importa (por ejemplo, los tarugos de una cajonera en una columna extra); revise su etapa |
| Fila de etapas corrida | Se toma la etapa de la columna corregida |
| Total con fórmula desplazada | El total del módulo no cuadra con sus piezas como en los demás módulos (por ejemplo, m² × 1.1 en lugar de planchas); revise el libro |
| Sin la pestaña resumen o sin la fila de etapas | No hay unidades ni etapas que tomar del resumen |

!!! info "Ver también"
    - [Mobiliario: módulos, productos y envíos](furniture.md)
    - [Importar maestro y ETO](import_master.md)
    - [Pestaña Planificación y hoja de trabajo](planning_worksheet.md)

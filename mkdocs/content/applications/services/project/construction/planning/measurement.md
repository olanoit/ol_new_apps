---
modulos: [al_construction_planner, al_construction_planner_furniture, al_construction_planner_mrp]
---

# Metrado

En mobiliario, el **metrado** es la receta real del mueble: el supervisor mide
el espacio y el diseño y el despiece que resultan (piezas y consumo de
materiales, accesorios y consumibles) se registran contra la receta
planificada del módulo. Producción ve lo presupuestado frente a lo real y, si
el costo real pasa el umbral, la orden de fabricación espera a la jefatura de
proyectos. El metrado es de la vertical Mobiliario: en una obra por partidas,
la partida avanza por su driver (ver [árbol de
recursos](resource_tree.md#avance-por-el-driver-de-la-partida)).

## Configuración

1. Active la función **Metrado** en **Planificación de obra ‣ Configuración ‣
   Ajustes ‣ Funciones** (el perfil **Mobiliario** la deja activa; el de
   **Construcción por partidas**, apagada). Sin ella no aparecen los menús de
   metrado.
2. En **Ajustes ‣ Planificación de obra**, revise el **Umbral del metrado
   (%)**: 10 % por defecto.
3. Los módulos de la tipología tienen su receta planificada en la pestaña
   **Materiales** (ver [Mobiliario: módulos, productos y
   envíos](furniture.md#modelo-del-mueble)).

## Registrar el metrado del mueble

1. Vaya a **Planificación de obra ‣ Ejecución ‣ Avance ‣ Metrados (receta
   real)** y haga clic en **Nuevo**.
2. Elija el **Módulo o mueble**. La **Receta planificada** es la del módulo en
   la tipología de su ambiente.
3. Cargue en **Materiales reales** cada producto con su cantidad, unidad y
   sub etapa, y en **Piezas** el despiece (cantidad, largo, ancho, tipo de
   pieza y color).
4. Revise la pestaña **Planificado y real**: material por material, lo
   planificado, lo real, la diferencia y la diferencia en soles, con el costo
   del producto. Arriba, el **Planificado**, el **Real** y la **Diferencia %**.
5. Haga clic en **Confirmar**.

Al confirmar:

- la receta real pasa a la lista de materiales del [producto del
  módulo](furniture.md#productos-por-módulo): la orden de fabricación sale con
  esos componentes;
- cada diferencia queda registrada, haya pedido autorización o no;
- si el costo real supera al planificado en más del umbral, el metrado queda
  marcado **Espera a la jefatura** y la orden de fabricación del módulo no se
  confirma hasta que la jefatura de proyectos (o el **Administrador**) hace
  clic en **Autorizar (jefatura)**. Bajo el umbral, producción sigue sin
  esperar.

La autorización queda en el historial del metrado con quién y cuándo.
**Volver a borrador** reabre un metrado confirmado y borra su autorización.

Ejemplo: con el umbral del 10 %, un mueble cuyo costo real supera en 8 % al
planificado pasa a producción con la diferencia registrada; uno con 12 %
espera la autorización de la jefatura.

## Presupuestado frente a real

**Informes ‣ Plan ‣ Presupuestado frente a real** muestra, por material, lo
presupuestado y lo real en cantidad y en soles de cada metrado confirmado, con
suma hacia departamento, piso y obra, en pivote y en lista.

## Metrado por driver del ambiente

El metrado del ambiente por metros lineales y módulos sigue disponible en
**Ejecución ‣ Avance ‣ Metrados anteriores**, **Cargar medidas** y **Generar
metrados**, con la función **Metrado** activa. Antes de fabricar,
el supervisor anota la medida real del ambiente en la unidad de cada driver:
metros lineales de mueble bajo, metros lineales de mueble alto y cantidad de
módulos. El planificador la compara con lo planificado y valoriza la
diferencia; si hay diferencia, la Jefatura de Proyectos la aprueba antes de
lanzar la orden de fabricación del ambiente.

### Conceptos

| Término | Significado |
|---|---|
| Metrado | La medida real de un ambiente, una por ambiente, con su estado: **Borrador**, **En aprobación** o **Aprobado** |
| Planificado | Los ML de mueble bajo y alto de la tipología del ambiente y la cantidad de módulos del ambiente |
| Costo por unidad | Monto planificado de las líneas de contrata y personal propio que dependen de ese driver (instalación por ML, armado por módulo…) entre lo planificado |
| Diferencia en soles | Diferencia de la medida × costo por unidad |

Lo que no se mide por ML ni por módulo (materiales, colocación de puertas,
entarugado) no entra en la diferencia en soles: si el metrado cambia el
mueble, se ajusta con una variante de la unidad o un cambio del plan.

### Registrar el metrado por driver

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

Un metrado se puede abrir también uno por uno en **Avance ‣ Metrados anteriores**.

### Enviar y aprobar

1. En **Avance ‣ Metrados anteriores**, marque los metrados terminados y use **Acción ‣
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

### La orden de fabricación ya no espera al metrado en mobiliario

Desde el paquete 1.9, en mobiliario el [ambiente medido](#ambiente-medido)
reemplaza al metrado con cantidad y su aprobación: el asistente **Orden de
fabricación** ya no deja fuera los ambientes con tipología por un metrado
pendiente. En construcción por partidas (ambientes sin tipología) el metrado
con diferencia sin aprobar sigue deteniendo la orden, con el aviso «Metrado
con diferencia por aprobar».

!!! note "Nota"
    Un metrado aprobado se puede volver a borrador para corregirlo mientras su
    ambiente no tenga una orden de fabricación.

## Ambiente medido

En mobiliario, el supervisor solo marca el ambiente como **medido**, con la
fecha y un archivo (plano, foto o exportación de SketchUp). No escribe
cantidades ni pasa por aprobación: las cantidades reales llegan con la carga
del despiece a la orden de fabricación.

1. Abra el ambiente (desde el árbol de la obra o **Planificación de obra ‣
   Ejecución ‣ Avance ‣ Ambientes medidos**, filtro **Sin medir**) y haga clic
   en **Marcar como medido**. En la lista se pueden marcar varios a la vez.
2. Indique la **Fecha de medición** y el **Archivo**, y confirme. El archivo
   queda en el historial del ambiente.
3. **Ambientes medidos** abre con el filtro **Medidos por cargar a una
   orden**: es la lista de pendientes de Optimización. El ambiente sale de
   ella cuando entra en una orden de fabricación y vuelve si la orden se
   cancela.
4. El asistente **Orden de fabricación** avisa «Sin marcar como medidos» con
   los ambientes que aún no lo están; la orden se puede crear igual.

**Desmarcar** quita la marca mientras el ambiente no tenga orden de
fabricación.

!!! info "Ver también"
    - [Mobiliario: módulos, productos y envíos](furniture.md)
    - [Aprobaciones del plan y del requerimiento](approvals.md)
    - [Asignaciones y compras](supply.md)
    - [Niveles de la obra y tipologías](levels_typologies.md)

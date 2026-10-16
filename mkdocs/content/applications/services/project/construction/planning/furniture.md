---
modulos: [al_construction_planner_furniture, al_construction_planner_mrp]
---

# Mobiliario: módulos, productos y envíos

En una obra de mobiliario, cada módulo del mueble tiene su tipo, su método de
unión, sus piezas y sus materiales. Con esos datos el plan genera las líneas
de contrata de cada módulo a la tarifa de la lista de la obra, crea al
aprobarse un producto fabricado por módulo y sigue cada módulo de la planta a
la obra. Esta página es para la Oficina Técnica y la Jefatura de Proyectos de
una contrata de muebles.

## Configuración

1. Active **Rubro mobiliario** (`al_construction_planner_furniture`) en
   **Planificación de obra ‣ Configuración ‣ Ajustes ‣ Funciones**, o aplique
   el perfil **Mobiliario** (ver [configuración por
   rubro](vertical_configuration.md)).
2. En **Ajustes ‣ Planificación de obra ‣ Método de unión del módulo**, elija
   los **Tornillos de armado** (los 4x50, no los 5x60 de instalación) y los
   **Tarugos** que cuentan las reglas del método de unión.
3. Revise las **Reglas del método de unión** y las **Listas de tarifas** en
   **Configuración ‣ Plan de obra**.

## Modelo del mueble

La plantilla **Edificio** ordena la obra en piso › departamento › ambiente ›
mueble › módulo:

- **Cocinas**: la tipología (por ejemplo, COCINA 04) va en el ambiente; el
  mueble es su tipo (**Mueble bajo**, **Mueble alto**, **Torre** o **Isla**) y
  el módulo se nombra por su función y su ancho en mm (MOD LAVADERO 900, MOD
  ALTO CAMPANA 610).
- **Closet, baño, lavandería, ducto y estacionamiento**: el bloque del
  despiece es el **Mueble completo**.

En la tipología (**Configuración ‣ Plan de obra ‣ Tipologías**), cada módulo
lleva:

| Campo | Qué es |
|---|---|
| Nombre del módulo | Su función y su ancho en mm |
| Tipo de módulo | **Estándar** o **Especial** |
| Módulo especial | Microondas, campana, alacena con puertas, repisero, torre de horno, refrigeradora, esquinero, cajonera, condimentero, botellero o zócalo. Se propone por el nombre del módulo |
| Método de unión | **Tornillo**, **Tarugo**, **Mixto**, **Minifix** o **Sin unión** |
| Actividad de armado | La que se paga; vacía, la del catálogo según el método o el tipo especial (**Actividad de armado del catálogo**) |

Al abrir un módulo se ven sus pestañas:

- **Materiales**: producto, cantidad, unidad y **Sub etapa** de consumo. Es la
  receta del módulo: genera sus materiales en el plan y su lista de
  materiales.
- **Piezas**: cantidad, largo y ancho en mm, **Tipo de pieza** (COSTADO, BASE,
  PUERTA, FRENTE, TAPA…), color, tablero, cantos y m² calculados.

## Método de unión

El método se propone contando los tornillos y los tarugos de armado de los
materiales del módulo (los de las sub etapas de instalación no cuentan) y
aplicando la primera regla que calza. Las reglas que vienen son:

| Regla | Método |
|---|---|
| Zócalo | Sin unión |
| 20 a 25 tornillos 4x50 y ningún tarugo | Tornillo |
| 12 a 15 tornillos 4x50 y 12 tarugos | Mixto |
| 20 a 28 tarugos y ningún tornillo | Tarugo |
| Sin tornillos ni tarugos | Sin unión |

Cada regla tiene sus rangos de **Tornillos desde/hasta** y **Tarugos
desde/hasta**, o un **Módulo especial** que la decide sin mirar los insumos.
Las edita el **Administrador** en **Configuración ‣ Plan de obra ‣ Reglas del
método de unión**; el orden de la lista es el orden en que se prueban.

Si la receta no calza en ninguna regla, el módulo muestra el **Aviso del
método** con los tornillos y tarugos que contó. El método se puede escribir a
mano: desde ese momento las reglas ya no lo cambian.

## Actividades de contrata de mobiliario

Las actividades de mobiliario son un catálogo aparte de los módulos. En
**Configuración ‣ Plan de obra ‣ Actividades de obra**, el grupo
**Mobiliario** de cada actividad indica:

- **Clase de actividad**: armado del casco según el método, armado en obra,
  armado de módulo especial, complementaria, instalación u otra;
- **Método de unión** o **Módulo especial** que paga, según la clase;
- **Piezas que la generan** (tipos de pieza separados por comas) y **Medida de
  las piezas**: una por pieza, ancho o largo de las piezas en ML.

El módulo estándar toma la actividad de armado de su método; el especial, la
de su tipo. El entarugado es una actividad aparte, porque se paga también en
módulos sin tarugo. Vienen estas actividades, todas en 1.2 Armado salvo el
minifix (2.1 Instalación):

| Clase | Actividades | Unidad |
|---|---|---|
| Armado del casco según el método | Armado módulo tornillo, tarugo y mixto | und |
| Armado en obra | Armado minifix en obra | und |
| Armado de módulo especial | Microondas, campana, alacena con puertas, repisero, torre de horno, refrigeradora, esquinero, cajonera, condimentero, botellero y zócalos | und |
| Complementaria | Entarugado, colocación de puertas (ml, desde el ancho de las piezas PUERTA), tapacanteo, cortes especiales, pegado de canto, repisas fijas, armado de cajón y correderas (desde las piezas FRENTE) y tapa de cajón (desde las piezas TAPA) | und o ml |

### Listas de tarifas

En **Configuración ‣ Plan de obra ‣ Listas de tarifas** hay una lista por
familia: **Cocina y baño** y **Closet y cajones**, esta con tarifas más bajas
(tornillo 5.50, tarugo 7.00, esquinero 12.00, tapacanteo y cortes 0.50, contra
6.00, 8.00, 14.00 y 1.00 en cocina). Cada línea tiene la actividad, la
**Tarifa** y la **Retención (%)**.

Como las tarifas se pactan por obra, **Versión para una obra** copia la lista
para elegirle la obra y su vigencia (**Vigente desde/hasta**). Al generar el
plan, la tarifa de cada actividad se busca así:

1. la tarifa de la obra o de la contrata de **Tarifas de contrata**, si
   existe;
2. la lista de la obra de la familia de la tipología, vigente a la fecha;
3. la lista general de esa familia;
4. el precio de la actividad.

!!! note "Nota"
    La tarifa del armado mixto viene en cero en las dos listas: escríbala en la
    lista de la obra antes de generar el plan.

## Líneas de contrata desde las piezas

Al [generar el plan](generate_plan.md), cada módulo con piezas recibe:

- una unidad de su actividad de armado (la escrita o la del catálogo);
- la colocación de puertas por la suma de los anchos de sus piezas PUERTA, en
  ML;
- el armado de cajón y las correderas por sus piezas FRENTE, y la tapa de
  cajón por sus piezas TAPA.

Ejemplo: un módulo mixto genera una línea «Armado módulo mixto» y uno de tipo
microondas genera «Armado microondas», los dos en 1.2 Armado con la tarifa de
la lista de la obra.

## Productos por módulo

Al aprobar el plan se crea en el maestro un producto fabricado por cada módulo
de cada tipología de la obra:

- se identifica por la obra, la tipología y el código del módulo (su posición
  en el mueble), no por su nombre;
- lleva los atributos **Tipo de módulo** y **Método de unión** (sin crear
  variantes), la ruta de fabricación y seguimiento por lote;
- su lista de materiales sale de los materiales del módulo, con su etapa de
  consumo;
- no se vende ni se compra.

El historial del plan dice cuántos productos se crearon. Al cerrar el plan,
los productos de módulo de la obra se archivan.

## Fabricar y enviar módulos

Con el plan **Aprobado** o **En ejecución**, haga clic en **Fabricar o enviar
módulos**, elija los **Departamentos** (vacío: todos los de la obra) y **Qué
hacer**:

- **Órdenes de fabricación por módulo**: una orden por producto de módulo y
  departamento, con el lote del departamento (nombre de la obra y del
  departamento). El lote dice qué módulo va a qué ambiente. Al terminar la
  orden, sus módulos pasan a **Producido**.
- **Envío de planta a obra**: una transferencia interna del almacén de la
  compañía a la ubicación de la obra, con los módulos producidos de los
  departamentos (con su departamento y sus ambientes en la descripción) y los
  **Recursos sueltos** que agregue. Al validar la recepción, los módulos pasan
  a **En obra**.

Registre lo que no llega o llega dañado con una foto en el historial de la
transferencia.

**Abastecimiento ‣ Envíos de planta a obra** lista los módulos por obra,
piso, departamento y ambiente con su envío, la fecha de recepción y el
**Estado del envío**: **Planificado**, **Producido**, **En tránsito**, **En
obra** o **Instalado**.

!!! warning "Importante"
    La orden de fabricación de un módulo cuyo [metrado](measurement.md) supera
    el costo planificado en más del umbral no se confirma hasta que la
    jefatura lo autoriza.

!!! info "Ver también"
    - [Catálogo y árbol de la obra](catalog.md)
    - [Generar el plan](generate_plan.md)
    - [Metrado](measurement.md)
    - [Importar la proyección de materiales](projection_import.md)
    - [Fabricación en Odoo 19](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing.html)

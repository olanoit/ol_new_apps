---
modulos: [al_construction_planner]
---

# Niveles de la obra y tipologías

No todas las obras son «piso › departamento › ambiente › módulo». Hay torres,
etapas, sótanos, dúplex, ductos y áreas comunes; hay cocinas con mueble bajo,
mueble alto y torre de horno, y unidades que piden otro color o no llevan una
pieza. Esta página explica cómo se describe cada obra tal como es, sin
inventar niveles.

## Plantilla de niveles

Cada obra tiene una **plantilla de niveles** (**Configuración ‣ Plan de obra ‣
Plantillas de niveles**) que dice cómo se llaman sus niveles y qué papel
cumple cada uno:

| Papel | Ejemplos de nombre | Notas |
|---|---|---|
| Agrupador | Torre, Etapa, Bloque, Sótano | Cero o más, por encima de la unidad. El último agrupador es el **piso**. |
| Unidad | Departamento, Local, Oficina | Exactamente uno. |
| Ambiente | Cocina, Closet, Baño | Exactamente uno; lleva la tipología. |
| Mueble | Mueble bajo, Mueble alto | Opcional, entre el ambiente y el módulo. |
| Módulo | MB01, MA03 | Exactamente uno, siempre al final. |

Vienen dos plantillas: **Edificio** (Piso › Departamento › Ambiente › Mueble ›
Módulo) y **Torres** (Torre › Piso › Departamento › Ambiente › Mueble ›
Módulo). La plantilla se elige en la obra y no se cambia cuando ya hay un plan
aprobado.

El árbol de recursos, el cronograma y los informes muestran el nombre del
nivel de la plantilla («Torre B», «Sótano 2») y suman los pisos dentro de su
agrupador.

### Tipo de unidad

Cada unidad tiene su **tipo**: departamento, nivel de dúplex, ducto,
estacionamiento, área común, depósito, local o piloto. Sirve para filtrar,
para marcar unidades en los contratos y para no confundir un ducto con un
departamento en los informes.

## Programar por ritmo

**Generar plan** puede fechar las etapas de todos los ambientes por **ritmo**:

- **Ritmo**: *pisos por semana* (cuántos pisos empiezan cada semana) o
  *semanas por piso* (cuántas semanas hay entre un piso y el siguiente, p. ej.
  1,5). *No cambiar fechas* deja las fechas como están.
- **Inicio del primer piso**.
- **Orden de los pisos**: del primero al último o al revés, recorriendo los
  agrupadores en el orden del árbol.
- **Días por etapa**: días hábiles de producción, armado, instalación y
  acabado.

Las fechas cuentan **días hábiles de la obra**: los días con horario en el
calendario de la compañía, sin los feriados nacionales de Perú. Las etapas de
un ambiente van encadenadas: si una se alarga, las siguientes se corren al día
hábil siguiente y conservan su duración. Las fechas del ambiente, de la unidad
y del piso se acumulan desde sus etapas.

## Tipologías completas

En **Configuración ‣ Plan de obra ‣ Tipologías**, cada tipología tiene ahora:

- **Familia**: cocina, closet, baño, lavandería, ducto, área común, especial u
  otra.
- **Variante de**: la tipología base de una variante con sufijo (03A es
  variante de 03). Una variante no puede tener variantes.
- **Otros nombres**: cómo se llama en la cotización, en la orden de compra del
  cliente o en el ETO («VK-01», «V-K-01», «COCINA 05»). El importador y el
  árbol reconocen la tipología por cualquiera de ellos, sin distinguir
  mayúsculas, espacios ni guiones.
- **Muebles**: mueble bajo, mueble alto, torre de horno…, con su grupo (bajo,
  alto u otro) y sus metros lineales (los calcula de los anchos de sus
  módulos o se escriben a mano). Cada módulo de la plantilla dice a qué
  mueble pertenece.

Con el nivel **Mueble** en la plantilla de la obra, **Generar plan** crea los
muebles de cada ambiente con sus módulos debajo y calcula las actividades por
metro lineal **por mueble**, con los ML del mueble y la tarifa vigente.

## Variantes por unidad

Una unidad o un ambiente puede salirse de su tipología sin crear otra
tipología. En la tarea, pestaña **Obra ‣ Variantes de la unidad**:

| Tipo | Qué hace |
|---|---|
| Color o acabado | Reemplaza un material por otro (melamina blanca por Rovere). |
| No lleva | Quita un material de esa unidad. |
| Metrado distinto | Cambia la cantidad del material en ese ambiente. |

**Generar plan** aplica las variantes solo a esa unidad. También se cargan con
la hoja **VARIANTES** del [maestro](import_master.md).

## En el maestro

El libro del maestro trae las columnas y hojas nuevas:

| Hoja | Columnas nuevas |
|---|---|
| ARBOL | **Agrupador** (varios separados por « / »: «Etapa 1 / Torre A») y **Tipo de unidad** |
| TIPOLOGIAS | **Variante de** y **Otros nombres** (separados por «;») |
| MUEBLES | Tipología, mueble, grupo y metros lineales |
| MODULOS | **Mueble** al que pertenece el módulo |
| VARIANTES | Agrupador, piso, departamento, ambiente (vacío: toda la unidad), tipo (color, excluir o metrado), código del producto, reemplazar por, cantidad y nota |
| ETO | **Agrupador** |

### Validaciones de datos

Antes de importar, el asistente avisa:

- códigos de tipología repetidos en TIPOLOGIAS (vale la última fila);
- ambientes repetidos en ARBOL (se omite la fila repetida);
- unidades cuyo número no corresponde a su piso (D601 en el piso 5);
- variantes de una unidad o de un producto que no existe.

Cada aviso dice la hoja y la fila.

---
modulos: [al_construction_planner, al_construction_planner_suite]
---

# Configuración por rubro

Una contrata de mobiliario, una constructora que trabaja por partidas, un
contratista eléctrico y una empresa de tuberías planifican de forma distinta:
cambian los niveles de la obra, las etapas, los recursos y los documentos de
Odoo que usan. **Planificación de obra** se adapta a cada rubro sin
programación, con cinco piezas:

| Pieza | Qué decide | Dónde |
|---|---|---|
| Perfil de vertical | Todo lo de abajo en un solo paso | **Configuración ‣ Plan de obra ‣ Perfiles de vertical** |
| Funciones y puentes | Qué partes de la aplicación se usan (compras, contratas, ventas…) | **Configuración ‣ Ajustes ‣ Funciones** |
| Etapas y tipos de recurso | Las fases de la obra y las clases de recurso | **Configuración ‣ Plan de obra ‣ Etapas / Tipos de recurso** |
| Plantilla de niveles | Cómo se llaman los niveles del árbol y qué hace cada uno | **Configuración ‣ Plan de obra ‣ Plantillas de niveles** |
| Recetas | Los recursos de una unidad del nivel (el APU de una partida) | **Configuración ‣ Plan de obra ‣ Recetas** |

## Perfil de vertical

Un perfil reúne la configuración de un rubro: plantilla de niveles, etapas,
tipos de recurso, puentes, funciones, parámetros de la compañía (por ejemplo,
el día en que empieza la semana de las contratas) y planes analíticos. Vienen
dos:

| Perfil | Para quién | Niveles | Puentes |
|---|---|---|---|
| **Construcción por partidas** | Constructoras que planifican por disciplina y partida con el APU de cada partida | Disciplina › Subpartida › Partida › Actividad | Compras, contratas, cuadrillas, presupuesto y ventas; sin fabricación |
| **Mobiliario** | Contratas que fabrican e instalan muebles | Piso › Departamento › Ambiente › Mueble › Módulo | Todos, incluidos fabricación y mobiliario |

Para aplicarlo:

1. Vaya a **Planificación de obra ‣ Configuración ‣ Ajustes ‣ Perfil de
   vertical**, elija el perfil y pulse **Aplicar el perfil** (o, en el
   perfil, **Aplicar a la compañía**). Solo lo hace el grupo
   **Administrador**.
2. El perfil activa sus etapas y tipos de recurso, escribe los parámetros en
   la compañía, crea los planes analíticos que falten, deja su plantilla como
   la de las obras nuevas y activa sus funciones e instala sus puentes. Al
   instalar un puente, Odoo recarga la aplicación.
3. Aplicar un perfil no borra nada: lo que ya estaba activo sigue activo.

La pestaña **Desvíos de la compañía** del perfil compara el perfil con la
configuración actual (parámetros, funciones y puentes) y muestra las
diferencias. La pestaña **Por decidir** apunta lo que falta acordar con el
cliente.

Cada obra guarda el perfil con el que nació. Las obras nuevas reciben la
**Plantilla de niveles** de los Ajustes, que aplicar el perfil deja con la
suya; una obra a la que se le elige otro perfil toma la plantilla de ese
perfil.

!!! note "Bases que ya usaban el planificador"
    Al actualizar a la versión 1.7, una compañía sin perfil que ya tiene obras
    o tipologías queda con el perfil **Mobiliario**, y sus obras con él. Las
    obras sin compañía también lo reciben cuando todas las compañías de la base
    quedan en Mobiliario. Sus plantillas, parámetros y funciones no cambian:
    una obra sin plantilla conserva el árbol piso › departamento › ambiente ›
    módulo. Las compañías que no usaban el planificador eligen su perfil en los
    Ajustes.

Cada obra tiene su cuenta analítica, por la que va el control del plan: si
nadie se la crea (Hojas de horas o el requerimiento de obra), el planificador
la crea al marcar el proyecto como obra.

!!! tip "Consejo"
    Un perfil se pasa de una base a otra con **Exportar** (descarga un JSON
    con la plantilla, las etapas, los tipos de recurso, los puentes y los
    parámetros) y **Configuración ‣ Plan de obra ‣ Importar perfil**. Importar
    el mismo archivo dos veces no duplica nada: cada pieza se reconoce por su
    código.

## Funciones y puentes

El núcleo (`al_construction_planner`) solo depende de Proyecto, el Gantt,
la analítica, los productos y las aprobaciones. Lo demás son **puentes** que
se activan en **Ajustes ‣ Funciones**:

| Función en Ajustes | Módulo | Qué agrega | Necesita |
|---|---|---|---|
| Control | (grupo) | Comprometido, real, saldo y desvío por nivel, etapa y tipo de recurso | — |
| Avance y metrados | (grupo) | Avance por driver con fotos y validación, metrado de los niveles | — |
| Contratas | `al_construction_planner_subcontract` | OC de servicio, liquidación semanal y portal de la contrata | Compras |
| Compras, abastecimiento y requerimientos de obra | `al_construction_planner_purchase` | Compra masiva, requerimientos de obra, abastecimiento, precios de compra y material extra | Requerimientos de compra y de obra |
| Cuadrillas propias | `al_construction_planner_crew` | Turnos de Planificación y horas de la hoja de horas como real | Planificación, Hojas de horas |
| Presupuesto analítico | `al_construction_planner_budget` | Presupuesto analítico al aprobar y control de la OC contra él | Presupuestos |
| Valorización e ingresos | `al_construction_planner_sale` | Calendario e ingresos, contratos, entrega semanal, valorización, cobranza y cronograma valorizado | Ventas |
| Producción | `al_construction_planner_mrp` | Órdenes de fabricación desde el plan, por nivel y etapa de producción | Fabricación |
| Rubro mobiliario | `al_construction_planner_furniture` | Tipologías de mueble, metros lineales, módulos, generar plan e importar maestro y ETO | Fabricación |

Dos puentes se instalan solos cuando están sus dos lados:
`al_construction_planner_subcontract_purchase` (contratas con compras) y
`al_construction_planner_sale_furniture` (la familia de la partida de venta
cuando hay mobiliario). `al_construction_planner_suite` instala todos los
puentes de una vez.

Desactivar **Control** o **Avance y metrados** solo oculta sus menús y
botones. Desactivar un puente lo desinstala: Odoo pide confirmación y borra lo
que el puente guardaba, así que hágalo solo en una base nueva o de pruebas. Los menús que operan un documento de otra aplicación (órdenes de
fabricación, requerimientos de compra, OC de servicio, cobranza) son accesos
directos a esa aplicación, filtrados a la obra: la OC, la OF y la factura se
gestionan en Compras, Fabricación y Contabilidad.

## Etapas y tipos de recurso

Las **etapas** son un catálogo: cada rubro usa las suyas y cada línea del plan,
del cronograma y del avance lleva una.

| Campo | Para qué |
|---|---|
| Código | Lo que guardan las líneas; no se cambia si ya está en uso |
| Tipo | **Producción** (se fabrica en taller y alimenta la OF) o **Campo** (se ejecuta en la obra) |
| Consume en la orden de fabricación | El material de esta etapa sale de la lista de materiales |
| Etapa anterior | Encadena el cronograma: la etapa empieza cuando termina la anterior |
| Duración y color | Duración por defecto en el cronograma y color de la barra |
| Niveles | Los niveles de la plantilla que la usan |

El perfil **Mobiliario** usa Producción, Armado, Instalación y Acabado; el de
**Construcción por partidas**, Trazo y replanteo, Ejecución, Acabados y Pruebas
y entrega.

Los **tipos de recurso** son el nombre visible de cada clase de recurso
(«Concreto», «Grúa», «Destajo»). Su **Comportamiento** dice qué hace el
planificador con la línea:

| Comportamiento | Documento | Su real sale de |
|---|---|---|
| Material | Compra o requerimiento de obra | Lo despachado y consumido |
| Servicio | Compra | Lo recibido |
| Equipo | Compra (alquiler) | Lo recibido |
| Contrata | OC de servicio | El avance validado |
| Personal propio | Turnos de la cuadrilla | Las horas registradas |
| Producción | Orden de fabricación | Lo producido y su consumo |

El campo **Abastecimiento** del tipo (compra, almacén, fabricación, contrata o
cuadrilla propia) dice de dónde sale por defecto. Puede haber varios tipos con
el mismo comportamiento; **Por defecto del comportamiento** marca el que se usa
cuando una línea no dice cuál.

## Plantilla de niveles

La plantilla nombra los niveles del árbol de la obra y le da a cada uno una
**Función**:

| Función | Cuántos | Ejemplos |
|---|---|---|
| Agrupador | Cero o más, arriba | Torre, Piso, Disciplina, Área |
| Unidad de entrega | Cero o uno | Departamento, Local, Tablero |
| Nivel con etapas | Exactamente uno | Ambiente, Partida, Spool |
| Subnivel | Cero o uno | Mueble, Sistema |
| Nivel de detalle | Cero o uno, al final | Módulo, Actividad |

Los niveles van en ese orden. El nivel con etapas es el que lleva las etapas
del cronograma (**Etapas del nivel** limita cuáles; vacía, todas las de la
obra) y la unidad de entrega es la que se cobra por hitos. Las demás casillas
se marcan por rubro: **Lleva receta**, **Se mide con metrado** (con su
**Unidad del metrado**), **Se valoriza o factura** y **Recibe avance**. Así, una
obra eléctrica puede usar Tablero › Sistema › Partida y medir la partida en
metros; una de tuberías, Área › Línea › Spool con el spool fabricado en
taller y montado en campo.

Vienen tres plantillas: **Edificio**, **Torres** y **Construcción por
partidas**. Ver también [niveles de la obra y
tipologías](levels_typologies.md).

## Recetas

Una **receta** (plantilla de ejecución) lista los recursos de una unidad del
nivel: material, equipo, mano de obra y contratas, con su etapa, su cantidad
por unidad y su rendimiento. Equivale al APU de una partida.

- **Plan ‣ Generar desde la receta**: elige los niveles y las etapas y crea las
  líneas del plan multiplicando la receta por el metrado de cada nivel. Si ya
  hay líneas generadas, las reemplaza o agrega otras.
- **Configuración ‣ Plan de obra ‣ Importar recetas y niveles**: lee un libro
  Excel con dos hojas opcionales.
    - **RECETAS**: una fila por recurso, con *Código de la receta*, *Tipo de
      recurso*, *Código del recurso* y *Cantidad por unidad* (obligatorias), y
      *Nombre*, *Unidad*, *Costo unitario*, *Etapa*, *Rendimiento* y
      *Personas*.
    - **NIVELES**: el árbol de la obra, con una columna por nivel de la
      plantilla más *Receta* y *Metrado*.

    Con el paquete Construction de Odoo instalado, **Copiar desde Work Items**
    trae sus APU: el material y el equipo por su naturaleza de costo y la mano
    de obra como personal propio o como contrata. Importar otra vez actualiza
    lo importado: la receta se reconoce por su código y la tarea por su nombre
    bajo su nivel superior.

## Ejemplos por rubro

| Rubro | Perfil | Niveles | Etapas | Documentos |
|---|---|---|---|---|
| Mobiliario | Mobiliario | Piso › Departamento › Ambiente › Mueble › Módulo | Producción, Armado, Instalación, Acabado | OF por ambiente, compra masiva, OC de servicio de armado e instalación, valorización por unidad |
| Edificación por partidas | Construcción por partidas | Disciplina › Subpartida › Partida › Actividad | Trazo, Ejecución, Acabados, Pruebas | Requerimiento de compra por partida, contratas y cuadrillas, valorización por avance |
| Instalaciones eléctricas | Construcción por partidas, con su plantilla | Tablero › Sistema › Partida | Propias (canalización, cableado, pruebas) | Compra masiva agrupada por partida o etapa, cuadrilla operario/oficial/peón |
| Tuberías para minería | Perfil propio con Fabricación | Área › Línea › Spool | Prefabricación (producción), Montaje (campo) | Una OF por línea con sus spools; el consumo vuelve a cada spool |

La **compra masiva** agrupa la necesidad por producto, nivel, etapa, partida o
receta; cada grupo es una línea del requerimiento de compra, que Compras cotiza
a los proveedores que quiera. La **cuadrilla** se arma por rol: cada persona
cubre la línea de personal propio de su rol.

!!! info "Ver también"
    - [Planificación de obra](../planning.md)
    - [Niveles de la obra y tipologías](levels_typologies.md)
    - [Generar el plan](generate_plan.md)
    - [Asignaciones y compras](supply.md)

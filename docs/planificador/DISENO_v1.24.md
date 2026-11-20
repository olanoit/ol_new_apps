# Diseño del paquete 1.24 · Requerimiento de obra: tipo de ambiente, orientación por campo y cabecera completa

Requerimiento: `docs/md/ALTA_Planificacion_Paquete_1.24_Requerimiento_Obra_Alcance_Cabecera.pdf`
(versión 1, 20-nov-2026), M124-01 a M124-04.

Se programó en el orden propuesto: primero M124-04 y M124-03, después M124-01 y
M124-02. Las dos entregas están en el mismo cambio, sin mezclar con otro paquete.

## 1. Ubicación (ARQUITECTURA_COMUN, sección 4)

| Qué | Capa | Módulo |
|---|---|---|
| Cabecera sin pestañas | Requerimiento de obra, común | `al_construction_material_request` |
| Orientación de cada nivel y ganchos del tipo | Núcleo | `al_construction_planner` |
| Selector de tipo, filtro, resumen, agrupación por tipo, nombre con camino y «?» | Requerimiento con plan | `al_construction_planner_purchase` |
| Qué tipo tiene cada ambiente | Vertical mobiliario | `al_construction_planner_furniture` |

No hay condiciones por vertical. El requerimiento pregunta al gancho
`project.task._construction_space_types`; si ninguna vertical responde, el
selector no aparece (obra de construcción por partidas).

## 2. Primera entrega

### M124-04 · Cabecera sin la pestaña «Otra información»

| Qué | Dónde |
|---|---|
| «Almacén por defecto», «Distribución analítica» y «Compañía» (solo con varias) en la columna izquierda; «Jefe de proyecto» bajo «Solicitado por», oculto en el interno | `al_construction_material_request/views/construction_material_request_views.xml` (grupos `site` y `dates`) |
| «Indicaciones para logística» a todo el ancho, bajo las dos columnas | misma vista, grupo `logistics_note` |
| Sin pestañas: «Materiales» titula la tabla | misma vista, `separator[@name='lines']` |
| El recuadro del alcance se ancla en el título de la tabla | `al_construction_planner_purchase/views/material_request_scope_views.xml` |
| La vista del alcance guardada en la base se anclaba en `//notebook`: se le cambia el ancla antes de actualizar | `al_construction_planner_purchase/migrations/30.20261120/pre-migrate.py` |

Los permisos de edición son los mismos atributos `readonly` y `groups` que tenían
los campos en la pestaña. No cambian `_compute_location_src_id`,
`_compute_analytic_distribution` ni el vale impreso.

### M124-03 · Orientación «?» en cada campo del alcance

| Qué | Dónde |
|---|---|
| «Orientación en el requerimiento» por nivel de la plantilla (traducible); vacía, el texto por defecto de la función, que se ve como texto de ayuda en la celda | `al_construction_planner/models/construction_level_template.py` (`request_hint`, `request_hint_default`, `_construction_request_hint_default`); `views/construction_level_template_views.xml` |
| Cada selector de nivel recibe su orientación; sin plantilla, la del nivel del planificador | `al_construction_planner_purchase/models/construction_material_request_scope.py` (`_construction_scope_slots`, `construction_scope_<n>_hint`) |
| Etiqueta con «?» para los nombres de nivel, que son valores calculados | `static/src/scope_label/scope_label.js` y `.xml` (widget `construction_scope_label`) |
| Etapas y Tarea del Gantt: la ayuda nativa del campo, con `<label for>` | `material_request_scope_views.xml` |
| El texto largo bajo «Tarea del Gantt» pasa al «?» | misma vista |

El «?» es el de las etiquetas de Odoo: se abre al pasar el mouse y con un toque
en el celular (`data-tooltip-touch-tap-to-show`).

## 3. Segunda entrega

### M124-01 · Tipo de ambiente y «Traer materiales del plan» por tipo

| Qué | Dónde |
|---|---|
| Gancho del tipo de cada nivel con etapas y de su orientación | `al_construction_planner/models/project_task.py` (`_construction_space_types`, `_construction_space_type_hint`) |
| Mobiliario: el tipo es la familia de la tipología | `al_construction_planner_furniture/models/project_task.py` |
| Elección (`construction_scope_type_keys`, lista de claves), opciones con su cantidad, posición del selector, nombre («Tipo de» + el nombre del nivel con etapas) y orientación | `construction_material_request_scope.py` (`_construction_scope_type_options`, `_compute_construction_scope`) |
| «Ambiente» ofrece solo los de los tipos elegidos, y los niveles de abajo, lo que cuelga de ellos | `_construction_scope_allowed` |
| Al cambiar lo de arriba salen los tipos y los ambientes que ya no corresponden | `_onchange_construction_scope` |
| Resumen antes de traer | `_compute_construction_fetch_summary` |
| Con tipos: solo las líneas del plan de los ambientes de esos tipos; una línea por material, etapa, tipo y nivel elegido más bajo; lo ya traído no se repite (la clave incluye el tipo) | `_construction_fetch_groups`, `action_construction_fetch_plan` |
| La línea guarda su tipo («Tipo de ambiente», entre Nivel y Etapa, 120 px, solo si la obra tiene tipos) | `construction.material.request.line.construction_space_type` y `_key` |
| Analítica de la línea con tipo: las cuentas que comparten todas sus líneas del plan (obra y Rubro) | `_construction_line_analytic_common` |
| Selector de varias opciones con la cantidad en la lista | `static/src/scope_label/scope_types.js` y `.xml` (widget `construction_scope_types`) |

Sin tipos elegidos, `_construction_fetch_groups` no agrega ninguna condición y la
clave lleva `False`: el resultado es el de antes.

### M124-02 · Ambiente con su piso, departamento y tipología

| Qué | Dónde |
|---|---|
| Con el contexto `construction_scope_path`, la tarea se nombra con su camino y el código de su tipología si el nombre no lo trae | `construction_material_request_scope.py` (`ProjectTask._compute_display_name`, `_construction_scope_long_name`) |
| La búsqueda mira el nivel de arriba, el piso, el departamento, el ambiente y el código de la tipología | `ProjectTask._search_display_name` |
| La etiqueta elegida muestra el texto corto | `construction_scope_short_name`; `static/src/scope_label/scope_tags.js` (widget `construction_scope_tags`) |
| Lista de 430 px de ancho mínimo | `static/src/scope_label/scope_label.scss` |

El contexto solo lo ponen los selectores del alcance: el árbol, el Gantt, el plan
y los informes siguen con el nombre de la tarea.

## 4. Decisiones del 20-nov-2026 (pendientes del requerimiento)

1. **Varios pisos y un tipo:** una línea por material, etapa, tipo y piso
   elegido, como dice el punto 6 del pedido. La columna Nivel muestra el piso.
2. **«Sin tipo»:** se ofrece, con su cantidad, cuando hay ambientes sin
   tipología bajo lo elegido.

## 5. Pruebas

| Código | Prueba | Dónde |
|---|---|---|
| M124-01 | Opciones según lo elegido; filtro de Ambiente; un tipo, dos tipos y ninguno; una línea por piso; no se repite; sin vertical que dé tipos | `al_construction_planner_suite/tests/test_package_124.py` (`test_type_*`, `test_fetch_*`, `test_no_selector_without_vertical_types`) |
| M124-02 | Nombre con camino, texto corto, búsqueda por departamento y por tipología, sin textos repetidos | `test_scope_names_and_search` |
| M124-03 | Texto por nivel sin plantilla y con plantilla; cambiarlo en la plantilla cambia el requerimiento | `test_hint_without_and_with_template` |
| M124-04 | Sin pestañas; campos en la cabecera; quien pide ve el almacén y no lo cambia | `test_header_without_other_tab` |
| Pantalla | Recorrido clic a clic: cabecera, cada «?», tipos, lista de Ambiente, «Traer materiales del plan» | `TestPackage124Screen`; `al_construction_planner_purchase/static/tests/tours/request_scope_tour.js` |

Todas corren con un usuario del grupo Solicitante, sin administración. El
recorrido de pantalla necesita `--db-filter` con el nombre de la base.

Resultado del 20-nov-2026 en la base de pruebas del planificador: las 11 pruebas
del paquete pasan. La regresión de `al_construction_material_request`,
`al_construction_planner_purchase`, `al_construction_planner_furniture`,
`al_construction_planner_approvals`, `al_construction_planner_mrp_request` y la
suite corre 711 pruebas con 2 fallos, los dos en `test_menus.TestMomentMenus120`
(`test_bar_execution_and_contracts` y `test_configuration_sections`), que fallan
igual con el código anterior al paquete. Las pruebas del portal de obra no se
corrieron: van en otra base.

## 6. Diferencias frente al requerimiento

1. **Texto del resumen.** Los tipos van por nombre, como en el selector
   («1 closet y 2 cocinas»), y el lugar va con «de» («de Piso 02», no «del Piso
   02»). Con más de tres niveles elegidos dice cuántos son («5 pisos»). El plural
   se arma con la regla general del español; un tipo de varias palabras queda
   como está («2 sin tipo», «2 área común»).
2. **Texto de ayuda de «Ambiente (opcional)».** Dice «Todos»; el de la maqueta
   («Todos los de los tipos elegidos») no se puso porque el texto de ayuda del
   campo no cambia según lo elegido.
3. **Camino en negrita en la lista.** La lista muestra el camino, el nombre y la
   tipología en una línea, sin negrita: es la lista nativa de Odoo, que resalta lo
   que se escribe.
4. **Analítica con cuentas por nivel.** Si los niveles de la obra tienen cuenta
   propia, la línea con tipo lleva las cuentas comunes a sus líneas del plan (obra
   y Rubro) y no las de cada departamento.
5. **Columna «Tipo de ambiente».** El nombre de la columna es fijo; solo se
   muestra en obras con tipos.
6. **Orientación por defecto del nivel con etapas.** Es la del requerimiento
   («Ambientes puntuales…»). Una compañía de construcción escribe la suya en su
   plantilla, como pide «Configuración y datos».
7. **«Compañía».** Va al final de la columna izquierda, solo con varias
   compañías.
8. **1280 × 720.** La cabecera y el inicio del recuadro entran sin desplazar; el
   recuadro completo con seis campos y las etiquetas elegidas necesita desplazar.

## 7. Correcciones de la verificación (20-nov-2026)

La primera pasada en la instancia de mobiliario mostró dos casos que las pruebas
no cubrían; quedaron corregidos y con su prueba
(`test_rubro_even_if_plan_lacks_it_and_noun_of_vertical`):

1. **Nombre del selector.** La plantilla de la obra llama «Mueble instalado» al
   nivel con etapas, y el selector salía como «Tipo de mueble instalado». La
   vertical nombra ahora lo que tiene tipo con el gancho
   `project.task._construction_space_type_noun` (mobiliario: «ambiente»); sin
   gancho, se usa el nombre del nivel. El resumen cuenta con ese mismo nombre.
2. **Rubro que el plan no trae.** Las líneas del plan se habían generado sin la
   cuenta Rubro, así que la línea del requerimiento tampoco la llevaba. La línea
   con tipo suma siempre el Rubro de sus niveles con etapas
   (`_construction_rubro_account`), que es uno solo porque todos son del mismo
   tipo (`_construction_line_analytic_common`).

## 8. Verificación en las instancias (20-nov-2026)

Desplegado en las cuatro bases de desarrollo con `c4a9bea9` y la corrección
`f7a130ed`. La verificación se hizo en el navegador, en la instancia de
mobiliario con un usuario que pide material y no es administrador, y en la de
construcción con el administrador. Las capturas quedan fuera del repositorio.

### Instancia de mobiliario

| Criterio | Resultado |
|---|---|
| M124-01 · 1 | Con un piso elegido, «Tipo de ambiente» ofrece los cuatro tipos de ese piso con las cantidades del requerimiento |
| M124-01 · 2 | Etapa, piso y «Cocina»: las 6 líneas con las cantidades del requerimiento, «Tipo de ambiente» = Cocina y analítica con la obra y el Rubro Cocina |
| M124-01 · 3 | «Cocina» y «Closet»: 11 líneas, 6 de cocina y 5 de closet; el material común sale en dos líneas, cada una con su Rubro |
| M124-01 · 4 | La segunda pulsación responde «No queda saldo por pedir…» y no crea líneas |
| M124-01 · 7 | El recorrido (elegir, abrir cada lista, traer) corre sin error con el usuario que pide |
| M124-02 · 1 y 2 | En la obra sin plantilla, la lista muestra piso, departamento, ambiente y tipología, y escribir el número de un departamento deja solo sus ambientes |
| M124-02 · 3 | Con un tipo y un piso elegidos, la lista ofrece solo los ambientes de ese tipo en ese piso |
| M124-03 · 1 | Cada campo del recuadro tiene su «?», en la obra con plantilla y en la obra sin plantilla |
| M124-04 · 1 y 2 | Almacén (de solo lectura para quien pide), analítica y jefe de proyecto en la cabecera; sin pestañas |

Queda en esa base un requerimiento en borrador con las 11 líneas, para la
aceptación. Mientras exista, sus líneas cuentan como pedidas contra el plan.

### Instancia de construcción

| Criterio | Resultado |
|---|---|
| M124-01 · 5 | En una obra por partidas no aparece el selector de tipo; el recuadro muestra etapas, especialidad, sub-especialidad, partida y tarea del Gantt |
| M124-03 · 3 | Cada nivel muestra su orientación |
| M124-04 | Almacén, analítica y jefe de proyecto en la cabecera; sin pestañas |

No se pulsó «Traer materiales del plan» ni se guardó ningún requerimiento ahí.

### Lo que no se verificó en pantalla

- M124-01 · 6 (sin tipos elegidos trae lo mismo que antes): solo por las pruebas.
- M124-03 · 2 (cambiar la orientación en la plantilla cambia el requerimiento):
  solo por las pruebas.
- M124-04 · 3 (el requerimiento interno no muestra «Jefe de proyecto»): no se
  abrió un interno.
- El requerimiento existente que cita el criterio 1 de M124-02 y de M124-04: el
  usuario de la verificación no tiene acceso a él; se comprobó en un borrador
  nuevo de la misma obra, que se descartó.
- La lista de partidas abierta, en construcción.

### Pendiente del cliente

La plantilla de niveles de construcción usa las orientaciones por defecto, que
hablan de pisos y ambientes. La compañía escribe las suyas para especialidad,
sub-especialidad y partida («Configuración y datos» del requerimiento).

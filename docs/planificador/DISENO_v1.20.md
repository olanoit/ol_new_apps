# Diseño del paquete 1.20 · Menús por momento y pantallas según la vertical

Requerimiento: `ALTA_Planificacion_Paquete_1.20_Menus_y_Vertical.pdf` (11-nov-2026),
M120-01 a M120-08. Entregas en el orden propuesto:

1. M120-07, porque M120-01 y M120-02 usan sus grupos.
2. M120-01 y M120-02.
3. M120-03 y M120-04.
4. M120-05 y M120-06.
5. M120-08.

El paquete trae pantallas nuevas y se entrega solo: no se despliega el mismo día
que otro paquete.

## 1. Regla de visibilidad

Un menú, campo, columna, filtro u opción se ve si se cumplen, en orden:

1. su puente está instalado;
2. su función del perfil está activa;
3. su etapa o tipo de recurso está en el perfil de la obra (o de la compañía si la
   pantalla no tiene obra), o la obra ya lo tiene registrado;
4. si nombra un nivel, la plantilla tiene esa función, y se ve con su nombre.

No se agregan condiciones «si la vertical es X»: todo sale de los puentes, del
perfil, de la plantilla y de los catálogos.

## 2. Entrega 1 · M120-07 · Seis funciones nuevas en el perfil

| Función | Clave | Grupo | Menús que oculta (con su puente) | Mobiliario | Construcción |
|---|---|---|---|---|---|
| Valorización por entregas e hitos | `milestones` | `group_planner_feature_milestones` | Hitos por unidad, Entregas semanales, Plantillas de hitos de cobro (`_sale`) | Activa | Apagada |
| Valorización por avance | `valuation` | `group_planner_feature_valuation` | Preparar valorización, Valorizaciones, Metas de valorización (`_sale`) | Apagada | Activa |
| Deductivos, intervenciones y fondo de garantía | `deductions` | `group_planner_feature_deductions` | Deductivos, Intervenciones, Fondos de garantía, Tipos de deductivo, Requisitos de devolución del fondo (`_subcontract`) | Apagada | Activa |
| Parte diario y tareo del residente | `daily_report` | `group_planner_feature_daily_report` | Partes diarios, Tareo de cuadrillas (`al_construction_portal`) | Apagada | Activa |
| Recetas por partida | `recipes` | `group_planner_feature_recipes` | Recetas (núcleo) | Apagada | Activa |
| Control semanal de instalación | `installation_board` | `group_planner_feature_installation_board` | Control semanal de instalación y su botón en la obra (`al_construction_attendance`) | Activa | Apagada |

Cómo se hace:

- **Perfil.** `feature_<clave>` en `construction.vertical.profile`, activos por defecto.
  `FEATURES` reúne las nueve funciones en su orden en pantalla; `FEATURE_FIELDS` y
  `FEATURE_GROUPS` salen de ella.
- **Grupos.** Uno por función, implicado en «Usuario interno» al instalar. En una base
  que ya existe, la migración `79.20261111` los suma: sin configurar, todo se ve como
  hoy (P4).
- **Perfiles estándar.** Mobiliario apaga valorización por avance, deductivos, parte
  diario y recetas; Construcción PROF 3 a 6 apagan hitos y el control semanal. Van en
  los datos `noupdate`, y la migración los escribe una vez en las bases que ya tienen
  los perfiles (los campos son nuevos: no hay nada del cliente que pisar). Los perfiles
  PROF 4 a 6 que se crean por código copian las funciones del PROF 3.
- **Menús.** Cada puente declara `[(menú, grupo)]` en `ir.ui.menu._construction_feature_menus`.
  `_visible_menu_ids` quita esos menús, y lo que cuelga de ellos, a quien no tiene el
  grupo. No se usa el campo «Grupos» del menú: los grupos de un menú se suman (basta
  uno), y una función activa abriría el menú a quien no tiene su rol.
- **Ocultar no bloquea.** Las acciones, los modelos y los permisos no cambian: un registro
  se sigue abriendo desde la obra, la orden de contrata o el portal.
- **Tabla de «Aplicar a la compañía».** Cada función que cambia dice qué menús aparecen
  o se ocultan, con su ruta («Ingresos › Entregas semanales»). Al apagar una con
  registros, agrega cuántos quedan detrás de cada opción y que siguen en la base.
- **Ajustes › Funciones.** Las nueve funciones y los puentes. Lo que el perfil de la
  compañía no usa y otro perfil sí (por ejemplo, Metrado, Producción y Rubro mobiliario
  en una constructora) pasa al bloque «Funciones de otras verticales». Ese bloque se
  abre con «Ver las funciones de otras verticales», que empieza apagado. Sin perfil, no
  hay bloque.

Pruebas: `TestProfileFeatures` (cada función oculta y restituye sus menús; la función
no abre menús a quien no tiene el rol; tabla de cambios con ruta y registros; usuario
«Planificador» sin «Administrador»; bloque de otras verticales; perfiles estándar) y la
prueba de pantalla `TestProfileFeaturesTour`. Esta abre el perfil, apaga «Valorización
por avance», aplica, recarga y comprueba Ingresos.

**C-01 después de este paquete.** Las seis funciones son grupos de toda la base, como
Control, Avance y Metrado: en una base con una compañía de cada vertical, apagar una
función la apaga para las dos. M120-03, M120-04 y M120-05 sí deciden por la obra.

## 3. Entrega 2 · M120-01 y M120-02 · Menús por momento

El menú tiene ocho secciones: Inicio, Obras, Planificación, Abastecimiento,
Contratas, Ejecución, Ingresos e Informes, más Configuración. Abastecimiento y
Contratas dejan de ser carpetas dentro de Planificación y suben a la barra.

- **Ejecución por momento.** Carpetas «Programación», «Avance y cambios»,
  «Control semanal» y «Personal propio»; dentro de Contratas, «Personal de
  contrata». Una carpeta solo aparece si tiene opciones visibles para el usuario.
- **Configuración en siete secciones.** «Vertical y etapas», «Recetas y
  actividades», «Contratas», «Hojas de trabajo», «Analítica y costos», «Portal y
  asistencia» y «Otros».
- **Cómo se hace.** El núcleo declara las carpetas en `MOMENT_FOLDERS`
  (`ir_ui_menu.py`) y cada puente dice a qué carpeta y en qué orden van sus menús
  (`_construction_moment_moves`) y con qué nombre (`_construction_moment_names`).
  `load_menus` los reubica sobre una copia del árbol (el árbol en caché no se toca).
  Los xmlid de los menús no cambian: los enlaces, los permisos y los favoritos
  siguen funcionando. Los tres menús de medición que el requerimiento retira se
  ocultan (`_construction_moment_hidden`) y su acción se sigue abriendo desde la obra.
- **Sin cuarto nivel.** Toda opción queda a dos niveles de la barra.

Pruebas: `TestMomentMenus120` en `test_menus.py` (secciones de la barra, carpetas
de Ejecución y Configuración, carpeta vacía que no aparece, menús ocultos, usuario
«Planificador» sin «Administrador»).

## 4. Entrega 3 · M120-03 y M120-04 · Niveles y etapas de la obra

- **M120-03 Nombres de nivel.** Las columnas y campos que nombran un nivel
  (piso, departamento, ambiente…) toman el nombre de la plantilla de niveles de la
  obra y se ocultan si la plantilla no tiene esa función. Las subvistas en línea se
  arman antes de leer el registro: el plan y «Registrar avance» pasan las funciones
  de la obra por contexto (`construction_level_functions`) y la columna se oculta con
  una expresión sobre ese contexto o sobre el campo del padre. Sin obra, se usa la
  plantilla de la compañía. El informe de etapas se titula «Etapa actual por
  partida» o «por ambiente», según la plantilla.
- **M120-04 Etapas del perfil.** El Cronograma ofrece las etapas del perfil de la
  obra y las que la obra ya tiene registradas, estas marcadas «(archivada)» si salieron
  del perfil (`_construction_offered_space_states`). Los cuatro filtros fijos de
  mobiliario del buscador de etapas pasan al puente de mobiliario. Los textos del
  Cronograma hablan de «filas» y no de «ambientes».

Pruebas: `TestLevelNames120` y `TestScheduleStages120` (`test_package_120_levels.py`).

## 5. Entrega 4 · M120-05 y M120-06 · Tipos de recurso y campos de mueble

- **M120-05 Tipos de recurso del perfil.** Las políticas de exceso, los días de
  anticipación y los montos del resumen por tipo de recurso solo se muestran para los
  tipos del perfil de la obra (en Ajustes, de la compañía). El plan, la obra y Ajustes
  calculan los códigos como texto con espacios (`' labor material '`) y la vista
  pregunta `' production ' in ...`: las expresiones de vista no admiten `split()`.
- **M120-06 Campos de mueble.** «Por módulo», «Por metro lineal», «Grupo ML» y
  «Pasada» de la actividad, sus filtros y las categorías de armado e instalación de
  Ajustes pasan a vistas del puente de mobiliario, en el mismo lugar de antes. Los
  campos siguen en el núcleo (D-02). Ajustes deja un ancla vacía
  (`service_categories`) en la que se cuelgan mobiliario y asistencia.

Pruebas: `TestCatalogs120` (`test_package_120_catalogs.py`).

## 6. Entrega 5 · M120-08 · Botones del plan agrupados

La cabecera del plan agrupa sus acciones en dos menús: «Programar» (Cambiar
fechas, Crear etapas del cronograma, Generar órdenes…) y «Ejecutar» (Registrar
avance, Asignar contrata, Asignar cuadrilla, Fabricar o enviar módulos…). Los
botones principales del flujo (Generar plan, Enviar a aprobación, Aprobar) quedan
como estaban.

- **Cómo se hace.** Cada módulo agrega sus opciones en
  `construction.resource.plan._construction_header_actions()` (menú, orden, rótulo,
  acción o método, grupos, estados y si exige líneas). El campo calculado
  `construction_header_actions` filtra por estado, líneas y grupos del usuario, y un
  widget de vista (`construction_plan_actions`) las muestra con los menús
  desplegables de Odoo. Los grupos y estados de cada opción son los del botón al que
  reemplaza.
- **Vistas de los puentes.** Las vistas heredadas que solo ponían botones quedan
  inactivas (`active = False`) para conservar su xmlid.

Pruebas: `TestPlanHeader120` (grupos y estados) y la prueba de pantalla
`TestScreens120`, que abre cada opción de Ejecución, Abastecimiento, Contratas y
Configuración (62 en la base de pruebas), usa los dos menús del plan y abre la ficha
de una actividad. Falla si un clic da error.

## Diferencias frente al requerimiento

- El botón «Control semanal» de la obra se muestra con la función «Control semanal de
  instalación». Antes dependía de la función «Control». Un botón de Odoo no puede pedir
  dos grupos a la vez; el tablero sigue exigiendo «Control» al abrirse.
- En una base de construcción, «Control semanal» de Ejecución tiene una sola
  opción (Control semanal de mano de obra) porque el tablero de instalación se apaga
  con su función. Se deja la carpeta para no cambiar el árbol entre verticales.
- Las columnas de nivel de pantallas sin obra (listas generales) usan la plantilla de
  la compañía; el requerimiento solo describe las de una obra.
- M120-08 pedía menús desplegables en la cabecera; Odoo no tiene un elemento de vista
  para eso, por lo que se hizo con un widget de vista que usa los desplegables
  nativos. Las opciones se declaran en Python y no en el XML de cada puente.
- El Cronograma de una obra de mobiliario ya no ofrece etapas que salieron del perfil
  salvo que la obra las tenga registradas (aparecen «(archivada)»).

## Resultado por código

| Código | Entrega | Versiones | Pruebas | Diferencias |
|---|---|---|---|---|
| M120-07 | 1 | planner 79, sale 29, subcontract 21, portal 15, attendance 13 | `TestProfileFeatures`, `TestProfileFeaturesTour` | Botón «Control semanal» con su función |
| M120-01 | 2 | planner 79, puentes con `_construction_moment_moves` | `TestMomentMenus120` | Carpeta de una opción en construcción |
| M120-02 | 2 | planner 79, furniture 30, spreadsheet_furniture 25, crew 9 | `TestMomentMenus120` | Ninguna |
| M120-03 | 3 | planner 79 | `TestLevelNames120` | Plantilla de la compañía sin obra |
| M120-04 | 3 | planner 79, furniture 30 | `TestScheduleStages120` | Etapas archivadas solo si están registradas |
| M120-05 | 4 | planner 79 | `TestCatalogs120` | Ninguna |
| M120-06 | 4 | planner 79, furniture 30, attendance 13 | `TestCatalogs120` | Ninguna |
| M120-08 | 5 | planner 79, purchase 26, mrp 18, subcontract 21, crew 9, furniture 30 | `TestPlanHeader120`, `TestScreens120` | Widget de vista; opciones en Python |

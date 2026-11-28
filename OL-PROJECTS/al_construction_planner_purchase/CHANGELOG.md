Historial de cambios — Planificación de obra: compras y abastecimiento (AL)
===========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_construction_planner_purchase.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261128.34 — 28/11/2026

- Tablero de abastecimiento: al comprar desde el tablero, si el asistente abre otra pantalla, el diálogo se cierra y la navegación sigue respondiendo.

## 20261120.31 — 20/11/2026

- La línea traída del plan por tipo lleva siempre la cuenta Rubro de su tipo, aunque las líneas del plan se hayan generado antes de configurar el Rubro.
- El selector de tipo y el resumen usan el nombre que da la vertical («Tipo de ambiente», «23 ambientes»), no el del nivel con etapas de la plantilla.

## 20261120.30 — 20/11/2026

- Requerimiento de obra (paquete 1.24): selector «Tipo de ambiente» entre el departamento y el ambiente, de varias opciones y con la cantidad de cada tipo; «Traer materiales del plan» trae el saldo de los ambientes de esos tipos, una línea por material, etapa, tipo y nivel elegido, con la analítica de la obra y del Rubro.
- Antes del botón, una línea dice lo que se va a traer (ambientes, tipos y etapa).
- La lista de cada nivel muestra el camino de cada opción («Piso 19 · 1907 · Closet 2 · CL-09») y busca en todo ese texto; la etiqueta elegida muestra el texto corto.
- Cada campo de «¿Para qué es el material?» lleva su «?» con la orientación de qué se elige; la de cada nivel sale de la plantilla de niveles.

## 20261112.29 — 16/11/2026

- Las escrituras del sistema sobre un plan aprobado usan la marca del servidor PLAN_FORCE (un contexto enviado por el cliente ya no abre el plan).

## 20261112.28 — 16/11/2026

- Rendimiento: al validar una entrega de venta, una recepción de compra o un ticket del punto de venta, la obra se busca una vez por ubicación y no una vez por movimiento.
- Rendimiento: el consumo en obra de las líneas del plan se suma en la base de datos en vez de leer todo el historial de movimientos de la obra.

## 20261104.23 — 04/11/2026

- M117-11: lo pedido en el plan descuenta lo devuelto por la asignación de cada plan, y se refresca al validar el movimiento.
- M117-14: la ruta completa del nivel en los reportes del requerimiento.

## 20261104.22 — 04/11/2026

- M117-10: la regularización incluye los requerimientos «En aprobación»; un requerimiento «Sin plan» que se aprueba con plan vigente entra a ese plan con la misma regla, con los dos motores de aprobación, y su conversación y la del plan dicen cuántas líneas quedaron asignadas y cuántas en exceso.

## 20261101.21 — 01/11/2026

- M114-01: al aprobar el plan, los requerimientos de obra pedidos sin plan se asignan a sus líneas; el exceso queda registrado con el motivo «Regularización de pedido sin plan». Filtro «Pedidos sin plan».
- M116-03 (M114-02): valor «Material fuera del plan si la obra no tiene plan» en «Requerimiento de obra sin regla»: crea la regla de validación «obra sin plan» para la jefatura del planificador, y «Control de plan» muestra «Sin plan».
- M114-03 y M116-04: el selector «Módulo» es el último nivel cuando la obra tiene módulos, y la ruta empieza en el «Primer nivel de la ruta» de la plantilla.
- M114-04, M116-01 y M116-05: la línea manual con etapa y material toma la distribución del plan con las cuentas de los niveles de su ruta; la etapa se elige entre las del perfil de la obra.
- M115-01: «Programar compra masiva» y «Requerimiento de materiales para obra» son los nuevos nombres de las acciones y sus asistentes.

## 20261027.17 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261024.16 — 26/10/2026

- CR-06: lo que el cliente entrega en la obra (recepción desde clientes, o del cliente de la obra) suma a «Recibido del cliente» de su línea de suministro del cliente; lo que se le devuelve, resta.

## 20261024.15 — 26/10/2026

- CR-16: validar recepciones, despachos, devoluciones y ajustes de inventario ya no falla sin Fabricación instalada («'stock.move' object has no attribute 'raw_material_production_id'»). Los consumos de las OF los suma al plan el puente al_construction_planner_mrp_request.

## 20261024.14 — 24/10/2026

- Requerimiento CREVAL v1.0, 6.1: bolsa de herramientas manuales. Con la categoría de herramientas manuales en Ajustes, las compras de esa categoría con la analítica de la obra son el comprometido y el real de sus líneas en % de la mano de obra.

## 20261024.13 — 24/10/2026

- Corrección CR-06 de la prueba CREVAL: las líneas de suministro del cliente no entran a la compra masiva, al requerimiento ni al tablero de abastecimiento.

## 20261024.12 — 24/10/2026

- Corrección CR-03 de la prueba CREVAL: el costo que aplica «Revisar costos del plan» guarda los decimales de «Precio del producto».

## 20261024.11 — 24/10/2026

- Paquete 1.11, M111-20 E: «¿Para qué es el material?» empieza por las etapas, muestra la planta debajo y solo los niveles que llevan la etapa elegida; «Tarea del Gantt» pasa a ser una sola, con su nota y aviso. Con niveles, «Tarea» se oculta en la cabecera.
- Paquete 1.11, M111-18 y M111-19 D: la compra masiva y el tablero de abastecimiento redondean el tablero en planchas y respetan «Aplicar en compras».
- Paquete 1.11, M111-20 E: quien ve montos en el planificador ve el valor estimado del requerimiento.

## 20261023.10 — 23/10/2026

- Requerimiento CREVAL v1.0, 6.5: la compra masiva de una línea del plan en otra moneda lleva su moneda y costo al requerimiento de compra; la orden se crea en esa moneda y el control lleva el tipo de cambio de la orden, con la diferencia de cambio aparte del desvío de precio.
- Capítulos 4 y 5: «Pedir material» y los requerimientos de obra en el tablero de obra, en el menú Ejecutar y en la sección Obra del proyecto; grupos en dos ejes.

## 20261023.9 — 23/10/2026

- Paquete 1.11, M111-09: el resumen de inventario compacto pasa a «PE - Base Inventario» (al_stock_base), para que se vea también sin el planificador; aquí ya no se modifica la vista.
- Paquete 1.11, M111-12: la compra masiva y el tablero de abastecimiento redondean a planchas enteras los tableros indivisibles (la unidad «Plancha L×A m» tiene referencia m² y antes no se redondeaba).

## 20261021.8 — 21/10/2026

- Resumen de inventario: botones pequeños y en una sola línea (en las tarjetas angostas se partían y se veían más grandes).

## 20261021.7 — 21/10/2026

- Resumen de inventario compacto: sin gráficos en las tarjetas de los tipos de operación, tarjetas más angostas y etiquetas en español (Con demora, En espera, Órdenes parciales, Movimientos).

## 20261021.6 — 21/10/2026

- Paquete 1.11, M111-06: líneas del plan del material bajo el nivel y la etapa del pedido, con o sin asignaciones, para las cifras de la solicitud de aprobación.

## 20261016.5 — 16/10/2026

- La línea agregada a mano toma el nivel y la etapa del recuadro cuando hay uno solo elegido.
- Las etapas del requerimiento son las del perfil de vertical de la obra (y las que usa su plan).
- Una fecha de necesidad del plan ya pasada propone hoy como fecha requerida.
- La regla «Exceso sobre el plan» mira la política de materiales aplicada al requerimiento y no la general del plan: con materiales en «Solo alerta» ya no pide aprobación.

## 20261016.4 — 16/10/2026

- Requerimiento de obra con selección de nivel y etapa: niveles en cascada según la plantilla de la obra, etapas, tareas del Gantt y botón «Traer materiales del plan» (una línea por material, nivel y etapa con el saldo, enlazada al plan).
- Material de la etapa Producción a la preproducción de la planta, en su propia transferencia, con ajuste para permitirlo o no.

## 20261016.3 — 16/10/2026

- Requerimientos y compras con la política de exceso del plan (v1.8, M18-05): repetición dentro de la tolerancia y registro del exceso autorizado.
- Tablero de abastecimiento sin costos ni montos para quien no tiene el grupo de montos (M18-10).

## 20261013.2 — 15/10/2026

- Compra masiva (M17-08): agrupa también por etapa, partida y receta, con el nombre del grupo en cada línea del requerimiento.
- El tipo de operación de la compra se llama «Tipo de recepción», para no confundirlo con el destino.

## 20261013.1 — 15/10/2026

- Puente nuevo (v1.7, M17-07): compras, requerimientos de obra y abastecimiento salen del núcleo.

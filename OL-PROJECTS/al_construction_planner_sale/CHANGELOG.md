Historial de cambios — Planificación de obra: valorización e ingresos (AL)
==========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_construction_planner_sale.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261117.33 — 17/11/2026

- Paquete 1.22, anexo, D1: la valorización por hitos que lleva una partida a su 100 % toma el total de su línea en la orden de venta menos lo ya valorizado; el último céntimo del descuento ya no queda sin valorizar.
- Paquete 1.22, anexo, D2: cuando un adicional cambia una tipología que ya existía, el hito de cada unidad se parte entre la línea original de la partida y la línea del adicional (en negativo si es un deductivo); las dos líneas avanzan con el mismo avance y ninguna pasa de su precio. Los hitos por unidad muestran su partida.

## 20261112.32 — 16/11/2026

- Seguridad: el estado de la valorización al cliente, de la entrega semanal y del cambio de obra solo cambia con sus acciones; antes quien ejecutaba podía confirmar una entrega, dar por confirmada una valorización o aprobar un cambio con una escritura directa.
- Seguridad: lo confirmado por el cliente ya no se cambia después de la conformidad.
- Las escrituras del sistema sobre un plan aprobado usan la marca del servidor PLAN_FORCE (un contexto enviado por el cliente ya no abre el plan).

## 20261112.31 — 16/11/2026

- Multicompañía: la meta de valorización del mes y lo facturado por partida solo se ven en las compañías del usuario (les faltaba la regla de registro).

## 20261104.21 — 04/11/2026

- M117-25: factura de valorización por partida o con una línea; forma, producto y texto por contrato y compañía; vista previa antes de crearla; anexo con el detalle y registro de lo facturado por partida.

## 20261104.20 — 04/11/2026

- M117-21: la partida en cada línea de la orden.
- M117-21: el factor de descuento del contrato guarda 6 decimales.

## 20261104.19 — 04/11/2026

- M117-09: la venta de la obra en «Por planificar» de Inicio.

## 20261101.18 — 01/11/2026

- CR-23: el envío del libro de APU y presupuesto con «Reemplazar» ya no borra las copias de líneas manuales.
- M116-01 y CR-22 a): una etapa de otro perfil es error de la fila y una actividad archivada se reactiva; la línea del cambio de obra ofrece las etapas del perfil.
- M116-11 e I-12: el libro acepta filas de título y una ruta por código de partida (1.01.01 o 1.0101); el envío crea un nivel por tramo y la cotización conserva sección y subsección.
- M116-05: columnas «Especialidad (catálogo)» y «Sub-especialidad (catálogo)»: llevan la cuenta analítica del nivel; un valor sin cuenta queda avisado en la cotización.
- M116-09: el libro reconoce cada columna también por su clave interna.
- M116-08: los cuadros dinámicos de contratos y del cronograma valorizado parten los nombres largos.

## 20261027.14 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261016.13 — 27/10/2026

- CR-18: el libro de carga y la hoja usan las columnas A a W de PRESUPUESTO (6.6) con «Costo unitario sin APU»; sin APU ni costo, error «Partida ‹ítem›: sin código de APU ni costo unitario» y no se envía (D1).
- CR-18, b: una unidad vale si es una equivalencia o el nombre de una unidad de Odoo en cualquier idioma instalado (Hours, Horas, Units…).
- CR-18, D2: en cada envío se recalculan gastos generales, imprevistos y utilidad sobre el parcial de venta de las partidas, y el descuento sobre partidas más esas líneas; cada monto se redondea una vez y la línea se busca por su rol.
- CR-18, e: la revisión lista cada partida con metrado y precio actuales y nuevos, en rojo las que bajan a 0 o cambian más del ajuste «Cambio que se marca en el envío» (20 %); con costo directo 0 o con errores no se puede enviar, y si al terminar el costo directo de la cotización no es el de la hoja, el envío se revierte.
- CR-18, D3: con la cotización confirmada o bloqueada, «presupuesto» no se envía; «presupuesto y plan» actualiza receta, metrado real y costos sin tocar precio, metrado ofertado ni el pie, y la revisión marca «Va por cambio de obra».
- CR-18, D4: sin obra, el envío guarda las recetas en la cotización (campo «Cotización de origen»), no en la biblioteca; la línea de venta guarda su receta y, al asignar la obra o crear sus niveles, las recetas se copian a la obra una sola vez.

## 20261016.12 — 26/10/2026

- CR-01: por avance, la cantidad de cada línea en la factura es la parte del periodo (monto ÷ precio), sin depender de lo facturado antes con otra cantidad.

## 20261016.11 — 26/10/2026

- CR-01 (re-prueba E14): la factura de la valorización por avance cobra cada línea por porcentaje con la precisión de la cantidad (una línea de 1 «Unidad» al 49.08 % no se podía facturar) y el ajuste de redondeo se mide contra la base sin redondear, para que cuadren base, IGV y total.

## 20261016.10 — 26/10/2026

- CR-01 (re-prueba E14): lo facturado desde la orden del contrato fuera de una valorización (una valorización facturada directo o anterior a la herramienta) cuenta como confirmado antes, y el adelanto descontado en esas facturas como amortizado antes; la valorización siguiente ya no vuelve a cobrarlo y se factura sin error.

## 20261016.9 — 26/10/2026

- CR-01 (preparación de la re-prueba E14): la valorización por avance amortiza el adelanto del contrato vigente de la obra, como el fondo y la detracción; con el adelanto de la obra en 0 %, la amortización salía negativa por la línea del descuento.

## 20261016.8 — 26/10/2026

- CR-01: la partida se reconoce por la línea de venta de su tarea aunque todas las partidas de la cotización compartan producto y no tengan receta (la valorización por avance salía en 0 %). Sirve la cotización de la obra con sus metrados.
- CR-01: el avance de la partida es, por defecto, la cantidad validada al corte ÷ la presupuestada (sin re-trabajos); la obra puede elegir el avance valorizado. «Actualizar» conserva el % escrito con su motivo, autor y fecha.
- CR-01: gastos generales, utilidad y descuento se prorratean sobre toda la venta o sobre las partidas de su sección (ajuste de la obra); adelanto, fondo de garantía y detracción salen del contrato vigente; la valorización muestra IGV, detracción y neto a cobrar.
- CR-01: la factura de la valorización suma lo mismo que la valorización (línea de ajuste de redondeo) y el asistente «Preparar valorización» muestra la base y crea la valorización por avance.

## 20261016.7 — 24/10/2026

- Requerimiento CREVAL v1.0, 6.7: el libro de APU y presupuesto lee también la pestaña PLAN de la hoja de trabajo (modalidad final y fechas de cada partida) en el destino plan.

## 20261016.6 — 24/10/2026

- Requerimiento CREVAL v1.0, 6.5: la línea de la cotización lleva el metrado real, las holguras de metrado y de costo y el margen (en % o monto); la cantidad, el precio y el costo para el margen de ventas salen de esas capas. La cotización tiene tipo de contrato (suma alzada o precios unitarios) y formato de impresión, y muestra el costo real y la reserva por holguras, que también se ve en el plan.
- 6.6 y 6.8: «Importar libro de APU y presupuesto», con las hojas OBRA, INSUMOS, APU, APU_DETALLE, PRESUPUESTO, LISTAS e INSTRUCCIONES y su plantilla descargable: crea o actualiza insumos, recetas y la cotización y, con destino plan, los niveles, la modalidad, el metrado real y el plan (con el plan aprobado, una nueva versión con su motivo). Valida códigos, insumos y APU, unidades con la tabla de LISTAS y fórmulas con error; volver a importar no duplica.

## 20261016.5 — 24/10/2026

- Corrección CR-01 de la prueba CREVAL: la obra puede valorizar al cliente por el «Avance validado de la partida» (una línea por partida de la venta, con el % escrito con motivo de siempre), sin entregas, tipologías ni hitos; la factura sale de la valorización confirmada.
- Corrección CR-12: las líneas de la venta de gastos generales, imprevistos, utilidad y descuento (se proponen por su nombre, campo «Rol en la obra») no se crean como niveles ni entran al plan, y se valorizan en la proporción del costo directo valorizado; el descuento va como línea negativa.
- Corrección CR-13: el anticipo del cliente de una obra (y su deducción) va sin analítica; el ingreso entra con cada valorización.

## 20261016.4 — 23/10/2026

- Requerimiento CREVAL v1.0, 6.4: importación del presupuesto a la cotización con secciones y subsecciones, equivalencias de unidades y aviso de duplicados, y «Crear niveles de la obra» desde la cotización.
- Capítulos 4 y 5: cambios de obra y cobro al cliente en el tablero de obra, «Registrar cambio» en el menú Ejecutar; grupos en dos ejes.

## 20261016.3 — 16/10/2026

- Valorización con porcentaje manual por línea y motivo, marcado en la factura y en el reporte, con el avance por etapa (v1.8).

## 20261013.2 — 15/10/2026

- La partida por defecto de una línea del plan sale del producto de la receta; la de la familia de mueble pasa a `al_construction_planner_sale_furniture`.
- La orden de venta de la valorización se llama «Orden de venta del contrato», distinta del contrato de obra.

## 20261013.1 — 15/10/2026

- Puente nuevo (v1.7, M17-07): la ruta del ingreso y los cambios de obra salen del núcleo.

Historial de cambios — Planificación de obra: valorización e ingresos (AL)
==========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_sale.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 10.20261016 — 26/10/2026

- CR-01 (re-prueba E14): lo facturado desde la orden del contrato fuera de una valorización (una valorización facturada directo o anterior a la herramienta) cuenta como confirmado antes, y el adelanto descontado en esas facturas como amortizado antes; la valorización siguiente ya no vuelve a cobrarlo y se factura sin error.

## 9.20261016 — 26/10/2026

- CR-01 (preparación de la re-prueba E14): la valorización por avance amortiza el adelanto del contrato vigente de la obra, como el fondo y la detracción; con el adelanto de la obra en 0 %, la amortización salía negativa por la línea del descuento.

## 8.20261016 — 26/10/2026

- CR-01: la partida se reconoce por la línea de venta de su tarea aunque todas las partidas de la cotización compartan producto y no tengan receta (la valorización por avance salía en 0 %). Sirve la cotización de la obra con sus metrados.
- CR-01: el avance de la partida es, por defecto, la cantidad validada al corte ÷ la presupuestada (sin re-trabajos); la obra puede elegir el avance valorizado. «Actualizar» conserva el % escrito con su motivo, autor y fecha.
- CR-01: gastos generales, utilidad y descuento se prorratean sobre toda la venta o sobre las partidas de su sección (ajuste de la obra); adelanto, fondo de garantía y detracción salen del contrato vigente; la valorización muestra IGV, detracción y neto a cobrar.
- CR-01: la factura de la valorización suma lo mismo que la valorización (línea de ajuste de redondeo) y el asistente «Preparar valorización» muestra la base y crea la valorización por avance.

## 7.20261016 — 24/10/2026

- Requerimiento CREVAL v1.0, 6.7: el libro de APU y presupuesto lee también la pestaña PLAN de la hoja de trabajo (modalidad final y fechas de cada partida) en el destino plan.

## 6.20261016 — 24/10/2026

- Requerimiento CREVAL v1.0, 6.5: la línea de la cotización lleva el metrado real, las holguras de metrado y de costo y el margen (en % o monto); la cantidad, el precio y el costo para el margen de ventas salen de esas capas. La cotización tiene tipo de contrato (suma alzada o precios unitarios) y formato de impresión, y muestra el costo real y la reserva por holguras, que también se ve en el plan.
- 6.6 y 6.8: «Importar libro de APU y presupuesto», con las hojas OBRA, INSUMOS, APU, APU_DETALLE, PRESUPUESTO, LISTAS e INSTRUCCIONES y su plantilla descargable: crea o actualiza insumos, recetas y la cotización y, con destino plan, los niveles, la modalidad, el metrado real y el plan (con el plan aprobado, una nueva versión con su motivo). Valida códigos, insumos y APU, unidades con la tabla de LISTAS y fórmulas con error; volver a importar no duplica.

## 5.20261016 — 24/10/2026

- Corrección CR-01 de la prueba CREVAL: la obra puede valorizar al cliente por el «Avance validado de la partida» (una línea por partida de la venta, con el % escrito con motivo de siempre), sin entregas, tipologías ni hitos; la factura sale de la valorización confirmada.
- Corrección CR-12: las líneas de la venta de gastos generales, imprevistos, utilidad y descuento (se proponen por su nombre, campo «Rol en la obra») no se crean como niveles ni entran al plan, y se valorizan en la proporción del costo directo valorizado; el descuento va como línea negativa.
- Corrección CR-13: el anticipo del cliente de una obra (y su deducción) va sin analítica; el ingreso entra con cada valorización.

## 4.20261016 — 23/10/2026

- Requerimiento CREVAL v1.0, 6.4: importación del presupuesto a la cotización con secciones y subsecciones, equivalencias de unidades y aviso de duplicados, y «Crear niveles de la obra» desde la cotización.
- Capítulos 4 y 5: cambios de obra y cobro al cliente en el tablero de obra, «Registrar cambio» en el menú Ejecutar; grupos en dos ejes.

## 3.20261016 — 16/10/2026

- Valorización con porcentaje manual por línea y motivo, marcado en la factura y en el reporte, con el avance por etapa (v1.8).

## 2.20261013 — 15/10/2026

- La partida por defecto de una línea del plan sale del producto de la receta; la de la familia de mueble pasa a `al_construction_planner_sale_furniture`.
- La orden de venta de la valorización se llama «Orden de venta del contrato», distinta del contrato de obra.

## 1.20261013 — 15/10/2026

- Puente nuevo (v1.7, M17-07): la ruta del ingreso y los cambios de obra salen del núcleo.

Historial de cambios — Planificación de obra: valorización e ingresos (AL)
==========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_sale.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

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

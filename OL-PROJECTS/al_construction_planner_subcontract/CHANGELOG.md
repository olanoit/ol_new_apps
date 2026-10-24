Historial de cambios — Planificación de obra: contratas (AL)
============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_subcontract.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 10.20261016 — 24/10/2026

- Un plan en ejecución no se cancela con liquidaciones de contrata sin anular.

## 9.20261016 — 24/10/2026

- Corrección CR-07 de la prueba CREVAL: «Asignar contrata» toma el precio de cada partida del costo del plan (o la tarifa de la actividad, a elección), editable en cada línea con el total a la vista.
- Corrección CR-11: la tarifa de la valorización guarda los decimales de «Precio del producto», como la orden; cada línea se redondea una sola vez y la factura da lo mismo que la valorización.
- Corrección CR-13: la factura de adelanto y su regularización ya no llevan la analítica de la obra; el costo entra con las líneas del servicio de cada valorización.
- Corrección CR-02 (parcial): si la cuenta del producto de anticipo es por pagar o por cobrar, «Registrar adelanto» lo dice antes y pide una cuenta de activo; la vía contable definitiva espera la decisión de contabilidad.

## 8.20261016 — 24/10/2026

- Corrección CR-10 de la prueba CREVAL: la valorización semanal usa la semana de la obra, la misma del avance. El corte semanal de la orden fija el cierre de esa semana al asignar la contrata (con un mensaje en la obra); si la obra ya tiene valorizaciones con otra semana, pide corregir el corte. La migración alinea las obras con órdenes de corte semanal.
- «Preparar valorizaciones» ya no se detiene en una semana sin avances: salta al periodo del primer avance o deductivo pendiente, incluidos los adicionales aprobados.

## 7.20261016 — 24/10/2026

- Corrección CR-08 de la prueba CREVAL del 24-oct: el avance de re-trabajo entra a la valorización con 0 a liquidar y queda en la revisión; solo se paga si quien valida la ejecución marca «Pagar el re-trabajo» con su motivo. Sin pagar, no va en la factura.
- Corrección CR-09: «Actualizar» la valorización conserva los deductivos que ya estaban en ella y recalcula los montos; antes los soltaba y volvían a Pendiente.

## 6.20261016 — 24/10/2026

- Deductivos: los creados a la vez ya no repiten número, y borrar uno pendiente no hace que el siguiente repita el del último; el número sigue al mayor de la obra.

## 5.20261016 — 24/10/2026

- Con detracciones instaladas, la factura de adelanto lleva el código de detracción del servicio de la orden (requerimiento CREVAL v1.0, 3.6); antes tomaba el del producto de anticipo, que no tiene código, y el adelanto salía sin detracción.

## 4.20261016 — 24/10/2026

- Valorización con condiciones: aprobar la revisión por niveles de la liquidación ya no falla al recalcular el resumen; antes el control de la revisión abierta bloqueaba la escritura de los totales.

## 3.20261016 — 23/10/2026

- Requerimiento CREVAL v1.0, capítulo 3: condiciones de contrata con su esquema de cálculo, copiadas a la orden de contrata; valorización por orden con periodicidad semanal, quincenal, mensual o al término, resumen del periodo (contractual, anterior, actual, acumulado y saldo), adelanto y su regularización, deductivos, fondo de garantía en una cuota propia de la factura y su reporte, liquidación y cierre de la orden, carga inicial con valorización de apertura, valorizado impreso con casillas de firma, resumen y análisis de valorizaciones y despacho semanal.
- Sin condiciones, la orden se comporta como antes. «OC de servicio» pasa a «Órdenes de contrata» y «Liquidaciones semanales» a «Valorizaciones de contrata»; los XMLID no cambian.
- Capítulos 4 y 5: contratas en el tablero de obra, en el menú Ejecutar y en la sección Obra del proyecto; preparar y presentar la valorización es de Ejecución: ejecuta y validarla, de Ejecución: valida.

## 2.20261016 — 16/10/2026

- Liquidaciones con re-trabajo y repeticiones (v1.8, M18-21): las de más del plan esperan la autorización de la jefatura; porcentaje manual con motivo por línea y alcance adicional del contrato con justificación.

## 1.20261013 — 15/10/2026

- Puente nuevo (v1.7, M17-07): las contratas salen del núcleo; la OC de servicio se gestiona en Compras.

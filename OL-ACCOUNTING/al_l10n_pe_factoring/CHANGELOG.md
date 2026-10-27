Historial de cambios — PE - Factoring de facturas (AL)
======================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_factoring.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 11.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 10.20261018 — 21/10/2026

- Una factura cedida con recurso tampoco se puede pagar desde sus apuntes, un pago múltiple ni una aplicación de documentos.

## 9.20261018 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 8.20261013 — 13/10/2026

- Contratos de factoring por factor: adelanto, TEA, días mínimos, comisión (% con mínimo, fija e IGV), gastos, cuenta del factor, línea de crédito y límite por cliente, con lo usado y lo disponible.
- Simulación de la liquidación en la operación; el desembolso propone los cargos del contrato y muestra la diferencia con la liquidación real.
- Revisión previa al ceder: todas las facturas excluidas con todos sus motivos (vencida, pagada, disconforme, ya cedida, otra moneda) y la operación con las demás.
- Factura negociable en la factura: conformidad presunta automática a los 8 días (tarea diaria con aviso 2 días antes), anotación en CAVALI, tenedor, fecha de pago e historial de eventos con orden validado.
- CAVALI: paquete para el formulario masivo de Factrack (XML e información adicional), importación de estados y servicios web configurables con registro de envíos (registro, transferencia, pago, reprogramación, conformidad y consulta).
- Notificación al cliente en PDF por correo; cobro recibido por la empresa y transferencia al factor; prórroga del vencimiento; archivo de la cesión en Excel; desembolsos parciales.

## 7.20261012 — 12/10/2026

- Menú en Perú ▸ Clientes ▸ Factoring; análisis y costo financiero en Informes ▸ Análisis.

## 6.20261012 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): factor, cliente y tres operaciones: sin recurso desembolsada, con recurso desembolsada con intereses devengados y una en borrador.

## 5.20261011 — 11/10/2026

- El neto pendiente de la factura cedida usa la misma regla de retención que el comprobante impreso y el XML: entre agentes de retención no se retiene.

## 4.20261010 — 10/10/2026

- Factura negociable (DU 013-2020): conformidad expresa o presunta (8 días calendario) o disconformidad, que impide ceder; fecha de anotación en CAVALI; aviso si la factura es al contado.
- El valor nominal propuesto es el monto neto pendiente de pago: sin la detracción ni la retención del IGV del cliente agente.
- Cobro parcial por factura: lo cobrado cubre primero el adelanto y luego libera el retenido.
- Comisión facturada por el factor: se elige su factura de proveedor y el descuento la paga (el IGV queda como crédito fiscal en ella).
- Sin recurso: pérdida del retenido no liberado (6741). Con recurso en moneda extranjera: la obligación se cancela al cambio histórico y la diferencia va a diferencia de cambio.
- Costo financiero por operación y menú Perú ▸ Factoring ▸ Costo financiero.

## 3.20261010 — 10/10/2026

- Una factura cedida que sigue pendiente no se puede pagar con «Pagar» (la cobra el factor): aviso en la factura y el cobro se registra desde la operación.

## 2.20261010 — 10/10/2026

- Con recurso la factura ya no se da por pagada al cederla: sigue pendiente en la cuenta del cliente (NIIF 9), en su saldo, vencimientos y recordatorios, y queda pagada con el cobro del factor; la recompra solo devuelve el adelanto.
- Datos de demostración «DEMO FAC» (tools/factoring_demo_data.py) y capturas de la ficha.

## 1.20261010 — 10/10/2026

- Primera versión: operaciones de factoring con y sin recurso sobre las facturas de cliente (cesión, desembolso, devengo de intereses, cobro del factor y recompra), cuentas del PCGE por modalidad y moneda, «Ceder a factoring» desde la lista de facturas, pestaña Factoring en la factura y menú Perú ▸ Factoring con análisis.

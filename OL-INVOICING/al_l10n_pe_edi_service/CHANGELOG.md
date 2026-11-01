Historial de cambios — PE - Envío de otros CPE a SUNAT (AL)
===========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py`. Este módulo no tiene ficha en
`docs/fichas/`: el historial se mantiene a mano.

## 20.0.1.0.0 — 30/10/2026

- Nuevo en Odoo 20: `l10n_pe_edi` dejó `account.edi.format` y sus servicios son métodos de la factura. Este módulo arma el mismo servicio (firma, zip, SOAP e IAP: `sendBill`, `sendSummary`, `getStatus`, `getStatusCdr`) para los comprobantes que no son facturas: retención, percepción, liquidación de compra y sus reversiones.

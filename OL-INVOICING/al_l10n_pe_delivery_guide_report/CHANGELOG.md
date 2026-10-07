Historial de cambios — PE - Reporte de Guía de Remisión Electrónica (AL)
========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_delivery_guide_report.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 8.20261007 — 07/10/2026

- La fecha de emisión impresa es la del XML enviado a SUNAT; el destinatario es la empresa cliente; las cantidades no se redondean a dos decimales y el detalle tiene una línea por movimiento, como el XML.

## 7.20260828 — 27/09/2026

- El **remitente** es la empresa (razón social y RUC), igual que en el XML enviado a SUNAT; antes salían los datos del almacén, a veces vacíos.
- Nuevos bloques **Punto de partida** y **Punto de llegada** con la dirección y el ubigeo.
- En el conductor, **Licencia** muestra el número de licencia de conducir; el DNI va en su propia fila.
- El botón **Guía de remisión** solo aparece cuando SUNAT ya aceptó la guía, no mientras la respuesta está pendiente.
- El peso bruto muestra la unidad configurada (antes siempre «KGM») y los lotes salen ordenados.

## 14/09/2026

- Vehículos dentro de la sección **Comprobantes electrónicos** de la configuración de la app Perú.

## 5.20260828 — 28/08/2026

- Los vehículos de la guía, antes solo en Inventario, también desde la app Perú.
- Pruebas de la agrupación por producto y unidad, lotes y peso.

## 4.20260719 — 25/07/2026

- Versión para Odoo 19: reporte independiente del de facturas, agrupación de bienes con lotes y peso con respaldo.

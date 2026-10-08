Historial de cambios — PE - Detracciones SPOT (AL)
==================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_detraction.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 18.20261008 — 08/10/2026

- Depósito masivo desde una sucursal: cabecera, titular (modo proveedor) y correlativo del lote son los del RUC, compartido por todas sus sucursales.

## 17.20261008 — 08/10/2026

- Los asistentes validan en el servidor que lo que reciben sea de su compañía (_check_company_auto y check_company).

## 16.20261008 — 08/10/2026

- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 15.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 14.20261007 — 07/10/2026

- La detracción pasa a la pestaña interna «Facturación PE ▸ Detracción». La constancia que l10n_pe_reports mostraba aparte en la factura de proveedor ya no sale duplicada.

## 13.20261007 — 07/10/2026

- Corregido: en facturas en moneda extranjera la detracción se calculaba sobre el total en soles de la factura, que depende del T.C. elegido (compra o editado a mano). Ahora se convierte siempre al T.C. venta oficial de la fecha de emisión, como manda la R.S. 183-2004/SUNAT, y coincide con el monto que va en el XML. Ejemplo: US$ 1 180 con venta 3.80 y factura a compra 3.70 daba S/ 524 en vez de S/ 538.

## 12.20260827 — 27/09/2026

- Con la detracción separada en el asiento, las cuotas de la factura electrónica a crédito ya no incluyen la detracción ni la restan dos veces.
- El depósito masivo del Banco de la Nación deja fuera los comprobantes que ya tienen constancia, y valida también los elegidos a mano (publicados, de la compañía y de la modalidad).
- No se puede registrar dos veces el depósito de una misma detracción.
- El tipo de operación se fija según el código: 1002 recursos hidrobiológicos, 1003 transporte de pasajeros, 1004 transporte de carga; los demás, 1001.
- Corregir a mano el tipo o el porcentaje de detracción recalcula el monto y ya no se pierde; el XML usa esos mismos valores.
- Al registrar el pago de una factura con reparto se propone solo el neto: la detracción se registra con «Registrar depósito».
- Si la cuota mayor no alcanza para separar la detracción, la factura avisa al publicarse en vez de quedar sin separar.
- El número de lote del depósito masivo propone el siguiente correlativo del año.

## 16/09/2026

- Aplicar un contraste antiguo ya no falla con «El código del catálogo 54 debe ser único»: los códigos que ya existen se vinculan y los porcentajes que ya coinciden no se tocan.
- Seis códigos nuevos en el catálogo, tomados del contraste con SUNAT: 007 caña de azúcar (Anexo 1), 011 bienes gravados por renuncia a la exoneración, 016 aceite de pescado, 023 leche, 032 páprika y 041 plomo.
- Contraste del catálogo con la página de SUNAT: botón en el catálogo, historial de contrastes, aplicación manual de las diferencias y acción planificada mensual con actividad cuando cambian.
- Mínimo del Anexo 1 (códigos 001 y 003) actualizado a S/ 2.750, media UIT de 2026.

## 6.20260827 — 14/09/2026

- La app Perú agrupa las detracciones en su propio menú: **Perú ▸ Detracciones**; el catálogo pasa a **Configuración ▸ Tributos SUNAT**.

## 5.20260827 — 27/08/2026

- Con el reparto activo, registrar el depósito ya no da por pagada la deuda con el proveedor.

## 4.20260815 — 18/08/2026

- Depósito masivo de detracciones para el Banco de la Nación, cuenta de detracciones en el contacto y tipo de operación SPOT en la factura.

## 3.20260719 — 19/07/2026

- Bloque propio **Detracciones (SPOT)** en los Ajustes de Perú.

## 2.20260719 — 19/07/2026

- Reparto opcional de la detracción dentro del asiento de la factura.
- Constancia de detracción en el PLE 8.3.

## 1.20260719 — 19/07/2026

- Primera versión: catálogo 54, cálculo en facturas, tipo de operación 1001 y registro del depósito con constancia.

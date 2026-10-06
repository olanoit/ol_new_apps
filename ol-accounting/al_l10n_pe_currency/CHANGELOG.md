Historial de cambios — Tipo de cambio Perú (SUNAT)
==================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_currency.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 7.20260901 — 27/09/2026

- Cargar el tipo de cambio ya no falla en bases con sucursales: la tasa se guarda en la compañía principal, de la que la toman sus sucursales.
- El tipo de cambio del dólar solo se registra en las compañías que llevan la contabilidad en soles.
- En monedas de poco valor (yen, peso chileno…) la factura y el pago convierten con la tasa exacta, sin el redondeo a tres decimales de la venta.
- Cambiar entre compra y venta en un pago devuelto a borrador rehace su asiento.
- La diferencia de pago y el descuento por pronto pago del asistente de pagos usan el mismo tipo de cambio (compra o venta) que el pago.
- Solo los usuarios de contabilidad pueden actualizar el tipo de cambio.
- El asistente ya no muestra los tokens guardados: si el campo queda vacío se usa el de la conexión de la compañía elegida. Decolecta y apis.net.pe admiten hasta 31 días por carga; para rangos largos, el BCRP.
- «Actualizar hoy (SUNAT)» y el asistente avisan si la carga salió bien o no, y el asistente se cierra solo al terminar.
- En la lista **Tipos de cambio** se puede crear una tasa nueva (propone el dólar), y una tasa creada solo con el valor nativo completa la compra y la venta.
- El tipo de T.C. aparece en su sitio también en las facturas de proveedor.

## 14/09/2026

- Menús de la app Perú reordenados.

## 5.20260901 — 01/09/2026

- Corrección: al crear una factura el tipo de T.C. se conoce antes de calcular la tasa, que ya no cae siempre en venta.

## 4.20260828 — 28/08/2026

- Grupo **Tipo de cambio** en la app Perú con el asistente, la lista de tasas y el cierre; la lista gana la columna de moneda.

## 3.20260816 — 18/08/2026

- Compra o venta por factura y por pago, con criterio configurable para ventas y compras.
- Nuevas fuentes BCRP y Decolecta; tasa nativa y venta coherentes.
- Revisión de las cuentas de diferencia de cambio 676 / 776.

## 1.20260717 — 16/07/2026

- Tipo de cambio compra/venta SUNAT, actualización diaria y T.C. aplicado en las facturas.

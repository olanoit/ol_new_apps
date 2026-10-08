Historial de cambios — Tipo de cambio Perú (SUNAT)
==================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_currency.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 11.20261008 — 08/10/2026

- Los asistentes validan en el servidor que lo que reciben sea de su compañía (_check_company_auto y check_company).

## 10.20261008 — 08/10/2026

- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 9.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 8.20261007 — 07/10/2026

- Corregido: las tasas cargadas desde el BCRP quedaban un día hábil adelantadas (el cierre SBS del viernes es el T.C. SUNAT del sábado al lunes). Ahora cada fecha toma el cierre anterior, como publica SUNAT, y los fines de semana y feriados también quedan registrados. Al actualizar, las tasas del BCRP ya cargadas se recargan con la fecha correcta.
- La actualización automática corre cada hora: antes, si la única corrida del día caía antes de que SUNAT publicara, el día entero se facturaba con la tasa anterior.
- La actualización automática ya no pisa una tasa registrada a mano y no reescribe una tasa que no cambió.
- La carga por mes funciona aunque el mes no se haya elegido en pantalla, y ninguna carga registra fechas futuras.
- La consulta al BCRP se reintenta si el servicio devuelve una respuesta vacía.

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

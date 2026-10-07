Historial de cambios — PE - Cuentas Destino (dinámica 6↔9)
==========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_account_destinations.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 7.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 6.20261007 — 07/10/2026

- Los destinos de la factura pasan a la pestaña interna «Contabilidad PE ▸ Destinos».

## 5.20261007 — 07/10/2026

- Corregido: restablecer y volver a publicar un comprobante consumía otro número del diario de destinos y dejaba huecos en el correlativo; ahora conserva su número salvo que cambie el periodo.
- Las líneas del asiento de destino (clase 9) llevan la analítica de la línea de origen.
- Si al republicar ya no queda nada que distribuir, el asiento de destino anterior se cancela en vez de quedar en borrador.

## 4.20260828 — 27/09/2026

- Eliminar un asiento de destino ya no borra el comprobante de origen. Al eliminar un comprobante en borrador, su asiento de destino se elimina con él.
- En comprobantes en dólares, el asiento de destino se registra en soles, con los mismos importes que el debe y el haber de la línea de origen.
- Los usuarios que solo tienen Facturación ya pueden publicar comprobantes con cuentas de destino. El diario de Gastos Automáticos se crea aunque no tengan permiso sobre diarios.
- Con varias compañías, el sentido de la dinámica (6→9 o 9→6) se toma de la compañía del comprobante y no de la compañía activa.
- Desde la lista de destinos ya se pueden cargar las líneas de una en una. La suma del 100 % se comprueba al guardar la cuenta y al generar el asiento.
- Se retira el enlace a la plantilla de importación, que apuntaba a un archivo inexistente.

## 3.20260828 — 14/09/2026

- El menú de la app Perú pasa a **Configuración ▸ Cuentas de la localización ▸ Destinos por cuenta**.

## 2.20260828 — 28/08/2026

- Acceso a los destinos desde la app Perú.

## 1.20260717 — 19/07/2026

- Asiento de destino automático en el diario GA, en los dos sentidos.
- Configuración por cuenta con porcentajes que suman 100 % y cuenta de carga.
- Vista consolidada de destinos con importación.

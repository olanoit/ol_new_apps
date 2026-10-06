Historial de cambios — TPV - Vendedor por orden (AL)
====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_pos_vendedor.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 2.20260721 — 27/09/2026

- Los vendedores autorizados ya no pueden iniciar sesión en la caja como cajeros: solo se eligen como vendedor de la venta.
- El TPV ya no recibe el PIN ni el código de barras de los vendedores; sin Empleados activo en la caja, solo se cargan los vendedores de la lista y no todos los empleados de la compañía.
- El filtro «Vendedor» de la lista de órdenes agrupa por vendedor (antes no hacía nada).
- El vendedor de una orden debe ser de la misma compañía que la caja.

## 27/08/2026

- Pruebas automáticas de la lista de vendedores, la carga en el TPV y el análisis por vendedor.

## 25/08/2026

- Licencia OPL-1 en toda la suite.

## 25/07/2026

- Migración a Odoo 19: selector en la pantalla de pago, apertura automática al validar, vendedor predeterminado por sesión, vendedor en el recibo y en el análisis de órdenes.

# PE - Cuentas Destino (dinámica 6↔9) — Odoo 19

Automatiza el **asiento de destino** de la dinámica de cuentas peruana: al
contabilizar un comprobante, las cuentas de **gasto por naturaleza (clase 6)**
se reflejan en cuentas por **función/destino (clase 9)** —o al revés— usando la
**cuenta de carga (78/79)** como contrapartida.

## Objetivo y funcionamiento

1. En la compañía se define el sentido (`Destinos`): **6→9** o **9→6**.
2. En cada cuenta que "trabaja con destinos" se configuran:
   - las **cuentas destino** con su **porcentaje** (la suma debe ser 100 %),
   - la **cuenta de carga** (78/79).
3. Al **postear** un comprobante con líneas de esas cuentas, se genera
   automáticamente un asiento en el diario **GA** ("Gastos Automáticos") que
   distribuye el importe entre las cuentas destino y lo contabiliza contra la
   cuenta de carga. El asiento queda **cuadrado por diseño** (el remanente del
   redondeo se asigna a la última línea).

El asiento de destino se enlaza con el de origen (`expense_move_id` /
`origin_expense_move_id`) y sigue su ciclo: al pasar a borrador o cancelar el
origen, el destino lo hace también.

## Modelo de datos

Todos los campos custom llevan prefijo `l10n_pe_` (convención de localización,
evita colisiones), y el modelo de líneas es `l10n_pe.account.destiny`.

- `account.account`: `l10n_pe_destiny_ids` (líneas destino),
  `l10n_pe_load_account_id` (dominio 78/79), `l10n_pe_no_destiny`,
  `l10n_pe_work_destinies` (computado), `l10n_pe_has_destiny`,
  `l10n_pe_dest_type`, `l10n_pe_allowed_dest_ids` (destinos válidos).
- `l10n_pe.account.destiny`: `parent_account_id`, `dest_account_id`,
  `percentage` (validado > 0 y suma 100 %).
- `account.move`: `l10n_pe_is_destiny_entry`, `l10n_pe_destiny_move_id`,
  `l10n_pe_origin_move_id`.
- `res.company`: `l10n_pe_dest_type` (6a9 / 9a6).

> La **glosa** (`l10n_pe_gloss`) y el helper `l10n_pe_is_pe()` provienen del
> módulo base **`al_account_base`**, del que este módulo depende.

En v19 `account.account.code` es **computado y company-dependent** (`code_store`);
los filtros por prefijo de código (`code =like '6%'/'9%'/'78%'/'79%'`) funcionan
vía el `search` del campo. Las cuentas son multi-compañía (`company_ids` M2m).

## Configuración

- **Compañía ▸ Destinos (PE)**: elegir 6→9 o 9→6.
- **Plan contable ▸ (cuenta clase 6/9) ▸ pestaña "Configuración de destinos"**:
  cuentas destino, porcentajes y cuenta de carga.
- Menú **Perú ▸ Configuración ▸ Destinos** (y **Contabilidad ▸ … ▸ Destinos**):
  vista consolidada de todos los destinos, con importación por Excel.

## Refactor v19 (desde v18)

- **Se eliminó el módulo `al_account_base`** y se absorbió lo útil (glosa, menú
  "Perú", helper `is_pe`) en este módulo; todo lo demás del base era código
  muerto: `al_account_pe_active` (siempre falso), `voucher_number`, `type_entry`
  / `for_entry_opening` (sin consumidor), `separe_code_product_report` (toggle
  invisible y sin efecto), modelo `pe.catalog` (sin acción), páginas y modelos
  vacíos, controladores comentados.
- **Mejoras al motor de destinos**:
  - `deprecated` → filtro `active` (campo eliminado en v19).
  - `load_account_id` y destinos usan **dominios** en vez de `search([])` de
    todo el plan en cada compute.
  - Se quitó la red de seguridad de balance (`_auto_balance_move_lines`): el
    bloque ya cuadra por diseño.
  - `_post` no reprocesa el propio asiento de destino (sin recursión).
  - `copy_data` corregido para la firma por lote de v19.

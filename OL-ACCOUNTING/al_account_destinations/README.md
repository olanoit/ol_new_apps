# PE - Cuentas Destino (dinámica 6↔9) — Odoo 19

Automatiza el **asiento de destino** de la dinámica de cuentas peruana: al
contabilizar un comprobante, las cuentas de **gasto por naturaleza (clase 6)**
se reflejan en cuentas por **función/destino (clase 9)** —o al revés— usando la
**cuenta de carga (78/79)** como contrapartida.

## Objetivo y funcionamiento

1. En la compañía (Ajustes ▸ Perú) se define el sentido (**6→9**, el del
   PCGE, o **9→6**), la **cuenta de carga por defecto** (791) y el **diario de
   destinos**.
2. El reparto sale de dos fuentes, en este orden:
   - **centro de costo**: cada cuenta analítica puede indicar su cuenta del
     Elemento 9 (`l10n_pe_destination_account_id`); la distribución analítica
     de la línea de gasto reparte el importe;
   - **por cuenta**: cuentas destino con su porcentaje (suma 100 %) para la
     parte sin centro de costo. Es de cada compañía.
   Una cuenta sin ninguna de las dos no genera destino. Una cuenta puede
   indicar su propia cuenta de carga (78, 72).
3. **Destinos del periodo** (Perú ▸ Destinos, Contabilidad ▸ Cierre) muestra
   el cuadre 79 vs Elemento 9 que exige el PCGE y regenera los destinos de un
   rango de fechas.
3. Al **postear** un comprobante con líneas de esas cuentas, se genera
   automáticamente un asiento en el diario **GA** ("Gastos Automáticos") que
   distribuye el importe entre las cuentas destino y lo contabiliza contra la
   cuenta de carga. El asiento queda **cuadrado por diseño** (el remanente del
   redondeo se asigna a la última línea).

El tramo 60 → 2/61 (compras → inventarios) no es de este módulo: lo hace la
valoración de inventario de Odoo (`stock_account`, cuentas 20111/6111/69121 de
la plantilla PE). Análisis y fuentes: `docs/destinos/ANALISIS_Y_PLAN.md`.

El asiento de destino se enlaza con el de origen (`l10n_pe_destiny_move_id` /
`l10n_pe_origin_move_id`) y sigue su ciclo: al pasar a borrador o cancelar el
origen, el destino lo hace también.

## Modelo de datos

Todos los campos custom llevan prefijo `l10n_pe_` (convención de localización,
evita colisiones), y el modelo de líneas es `l10n_pe.account.destiny`.

- `account.account`: `l10n_pe_destiny_ids` (líneas destino de la compañía
  raíz activa), `l10n_pe_load_account_id` y `l10n_pe_no_destiny` (calculados
  sobre `l10n_pe_load_account_store` / `l10n_pe_no_destiny_store`,
  company_dependent, leídos y escritos en `company.root_id`: el mismo patrón
  que `code` / `code_store` de Odoo 19, para que las sucursales usen la
  configuración de su RUC),
  `l10n_pe_work_destinies` (computado), `l10n_pe_has_destiny`,
  `l10n_pe_dest_type`, `l10n_pe_allowed_dest_ids` (destinos válidos).
- `l10n_pe.account.destiny`: `company_id` (raíz; regla `parent_of` como
  cuentas y diarios), `parent_account_id`, `dest_account_id`,
  `percentage` (validado > 0 y suma 100 %).
- `account.move`: `l10n_pe_is_destiny_entry`, `l10n_pe_destiny_move_id`,
  `l10n_pe_origin_move_id`.
- `res.company`: `l10n_pe_dest_type` (6a9 / 9a6),
  `l10n_pe_destination_load_account_id`, `l10n_pe_destination_journal_id`.
- `account.analytic.account`: `l10n_pe_destination_account_id`.
- `l10n_pe.destination.period.wizard`: cuadre 79 vs 9 y regeneración.

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

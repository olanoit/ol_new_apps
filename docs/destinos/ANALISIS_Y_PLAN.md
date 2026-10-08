# Asientos de destino — análisis y plan de refactor de `al_account_destinations`

Fecha: 08/10/2026 · Odoo 19 · Fuentes al final.

## 1. Qué exige la norma (PCGE 2019, MEF)

- **Gasto por naturaleza → función.** Las cuentas 62, 63, 64, 65 y 68 (en todo
  o en parte) «se trasladan a cuentas de acumulación por función» del
  **Elemento 9** (mínimo: gastos de administración y de venta). El uso del
  Elemento 9 «se deja a criterio de las entidades» (pág. 206).
- **Cuenta 79 / 791** «transfiere costos y gastos acumulados por su naturaleza
  a cuentas de costo de producción o cuentas acumulativas de función (Elemento
  9)»: se **abona** por los gastos imputados con cargo al Elemento 9 y su
  saldo acreedor debe ser **igual** a la suma de los saldos deudores del
  Elemento 9, con los que se compensa al cierre (pág. 195). 792 lleva costos
  financieros a existencias (238, NIC 23); los gastos cubiertos por
  provisiones van por la 78 y la producción de activos propios por la 72.
- **Compras 60 → inventarios.** La 61 abona las compras «con cargo a las
  cuentas del Elemento 2» (611→20, 612→24, 613→25, 614→26).

## 2. Qué hace ya Odoo 19

- `l10n_pe` trae 791, 792 y 781, la 61 y la 69, pero **ninguna cuenta del
  Elemento 9**: cada empresa crea las suyas.
- El tramo **60 → 2 / 61 lo resuelve la valoración de inventario** de
  `stock_account` (plantilla PE: valoración 20111, variación 6111, costo de
  ventas 69121). El módulo de destinos **no** debe duplicarlo.
- La **analítica** (distribución analítica en cada línea y modelos de
  distribución automáticos por cuenta/producto/socio) es la herramienta nativa
  para repartir un gasto entre centros de costo.

## 3. Apps de la tienda (Odoo Apps)

| App | Enfoque | Notas |
|---|---|---|
| `l10n_pe_account_target_move` (OPeru, 13.0–19.0) | Por cuenta: «Tiene cuenta destino» + cuentas destino en el plan contable; asiento al publicar | 60–65, 67, 68 → Elemento 2 o 9, abono 61 o 79. Sin porcentajes ni analítica documentados. |
| `l10n_pe_analytic_account_target` (tagre, 16.0–17.0) | Por **analítica**: cada cuenta analítica tiene cuentas de débito/crédito; genera por **rango de fechas** según las normas de reparto | Diario configurable, generación individual o masiva, trazabilidad naturaleza↔destino. |
| `odoope_target_move` (10.0–11.0) | Igual que OPeru | Obsoleto. |

## 4. Diagnóstico del módulo actual

| Tema | Hoy | Problema |
|---|---|---|
| Fuente del reparto | Porcentajes fijos por cuenta 6 | No usa la analítica: un mismo 6311 de Administración y de Ventas va siempre al mismo reparto. |
| Cuenta de carga | Una por cuenta (78/79) | Casi siempre es 791: se repite en cada cuenta. |
| Multicompañía | Destinos sin compañía, sobre cuentas compartidas (v19) | Dos compañías no pueden tener repartos distintos para la misma cuenta. |
| Diario | «GA» creado al vuelo con sudo | No configurable. |
| Sentido | 6→9 o 9→6 por compañía, por defecto 9→6 | El estándar es 6→9; el 9→6 se mantiene para quien registra por función. |
| Cuadre 79 = Σ9 | No existe | La norma exige que coincidan; no hay control. |
| Regeneración | Solo al republicar el comprobante | Cambiar la configuración no actualiza lo ya contabilizado. |

## 5. Propuesta (implementada en la v8.20261008, decisiones de Vicente: analítica + por cuenta; al publicar + regenerar por periodo)

1. **Reparto por analítica (nuevo, prioritario) + por cuenta (se conserva).**
   Cada cuenta analítica de un plan «Destino» indica su cuenta del Elemento 9
   (p. ej. Administración → 94, Ventas → 95, Producción → 91/92). La
   distribución analítica de la línea define el reparto; si la línea no
   tiene analítica de destino, se usa el reparto por cuenta actual.
2. **Cuenta de carga por defecto por compañía** (791), sobrescribible por
   cuenta (78 o 72 en los casos que la norma indica).
3. **Configuración por compañía**: los destinos por cuenta llevan
   `company_id` (regla y check_company), y se migran los 57 existentes a la
   compañía donde se usan.
4. **Diario de destinos** configurable en Ajustes (por defecto el «GA»
   existente).
5. **Asistente de regeneración por periodo** (rango de fechas): recalcula los
   destinos de los comprobantes publicados tras cambiar la configuración.
6. **Control de cuadre 79 vs Elemento 9** por periodo (informe/aviso en
   «Contabilidad PE»).
7. Por defecto 6→9 en compañías nuevas; las que hoy están en 9→6 se respetan.
8. Fuera de alcance: 60→2/61 (lo hace `stock_account`).

## Fuentes

- PCGE 2019 (MEF): https://www.mef.gob.pe/contenidos/conta_publ/pcge/PCGE_2019.pdf
- OPeru, Asientos Destino: https://apps.odoo.com/apps/modules/18.0/l10n_pe_account_target_move
- tagre, Asientos contables destino: https://apps.odoo.com/apps/modules/16.0/l10n_pe_analytic_account_target
- Odoo Perú, Asiento Destino (11.0): https://apps.odoo.com/apps/modules/11.0/odoope_target_move

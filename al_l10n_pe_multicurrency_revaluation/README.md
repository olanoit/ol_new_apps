# PE - T.C. compra/venta en ganancias y pérdidas no realizadas

Extiende el informe de Enterprise **Contabilidad ▸ Informes ▸ Monedas no realizadas (Ganancias/pérdidas
de moneda no realizadas)** para compañías peruanas. Migración a Odoo 19 de
`mblz_l10n_pe_multicurrency_revaluation` (Odoo 18).

## Qué hace

| Pieza | Comportamiento |
|---|---|
| Cuenta contable | Pestaña Contabilidad ▸ grupo **Ganancias/pérdidas no realizadas (PE)**: **Compra** o **Venta**. Solo aparece (y es obligatorio) en cuentas por cobrar/pagar y en cuentas con moneda extranjera de compañías peruanas. |
| Informe | Cada cuenta se revalúa con el `rate_purchase` o el `rate_sale` (de `al_l10n_pe_currency`) vigente a la fecha del informe. Sin ese valor, usa el T.C. genérico. |
| Columna **T.C.** | T.C. aplicado en soles por unidad (`S/ 3.720`); en blanco en los totales que mezclan tipos de cambio. |
| Cabecera de moneda | `USD (1 USD = S/ 3.700)` en lugar de `USD (1 PEN = 0.27027 USD)`. |
| Asiento de ajuste | Cada provisión cita el T.C. de su cuenta: `Provisión de USD (T.C. S/ 3.720)`. |
| Otras compañías | Informe nativo, sin columna T.C. |

Atajo en la app **Perú ▸ Tipo de cambio ▸ Ganancias/pérdidas no realizadas**.

## Cómo se calcula sin copiar el SQL de Enterprise

La consulta nativa (`_multi_currency_revaluation_get_custom_lines`) usa una
tasa por moneda. El módulo la ejecuta **una vez por grupo de cuentas**:

1. cuentas sin tipo peruano → tasas genéricas;
2. cuentas en **compra** → `currency_rates` con `1 / rate_purchase`;
3. cuentas en **venta** → `currency_rates` con `1 / rate_sale`;

cada pasada limitada a sus cuentas con `forced_domain`. Los resultados se
suman por clave de agrupación y la paginación (`offset`/`limit`) se aplica
después de sumar. Los grupos se calculan en `_custom_options_initializer` y
viajan en las opciones, así que el asistente del asiento de ajuste revalúa
igual que el informe.

## Relación con `al_l10n_pe_exchange_closure`

Son complementarios: este módulo trabaja sobre la **provisión reversible**
nativa de Enterprise (se revierte al día siguiente); el cierre de T.C. genera
el **ajuste definitivo** del art. 61 LIR. Cada uno tiene su propio campo en
la cuenta (`l10n_pe_revaluation_rate_type` aquí, `l10n_pe_exchange_rate_type`
en el cierre) para que puedan instalarse juntos.

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 --test-tags /al_l10n_pe_multicurrency_revaluation \
    --stop-after-init --http-port 19797
```

12 pruebas: visibilidad del campo, tasas por tipo, ajuste con compra y venta,
totales con tipos mezclados, compañía no peruana y etiqueta del asiento.

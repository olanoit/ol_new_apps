# Tipo de cambio Perú (SUNAT) — Odoo 19

Gestiona el **tipo de cambio SUNAT (compra y venta)** para USD/PEN, con
actualización diaria automática, y muestra el **tipo de cambio aplicado y su
fecha** en las facturas emitidas/recibidas en moneda extranjera.

Odoo nativo solo maneja una tasa única por día; este módulo agrega el par
**compra/venta** que exige la operativa peruana.

## Funcionalidades

- Campos `rate_purchase` (compra) y `rate_sale` (venta) en `res.currency.rate`,
  además de la tasa nativa `rate` (= `1 / venta`, la venta es la tasa oficial
  para la conversión contable en Perú).
- **Actualización diaria** vía `ir.cron` desde el TXT oficial de SUNAT.
- **Asistente** para actualizar por día, rango de fechas o mes.
- En las **facturas en moneda extranjera** (distinta a la de la compañía) se
  muestra el tipo de cambio aplicado (S/ por US$ 1) y la fecha del T.C.

## Fuentes de datos

| Fuente | Uso | Token | Cobertura |
|---|---|---|---|
| **TXT oficial SUNAT** (`sunat.gob.pe/a/txt/tipoCambio.txt`) | Actualización de **hoy** (cron y botón) | No | Solo el día publicado; trae compra y venta |
| **apis.net.pe** (`/v1/tipo-cambio-sunat`) | Fechas **históricas** (asistente) | Recomendado | Por fecha; sin token puede dar límite (HTTP 429) |

El servicio de red vive en `services/sunat_rate.py` (funciones puras, sin ORM).

## Integración con l10n_pe_vat_sunat

Si el módulo **`l10n_pe_vat_sunat`** está instalado, el token de apis.net.pe se
**reutiliza automáticamente** desde su conexión `apis.net.pe` (no hay que
volver a ingresarlo). Es una dependencia *suave*: el módulo funciona igual sin
`l10n_pe_vat_sunat`, pidiendo el token en el asistente.

## Uso

1. **Monedas** → abrir **USD** → botón **"Actualizar hoy (SUNAT)"** para traer
   el T.C. del día, o **"Actualizar por fecha/mes"** para el asistente.
2. El cron *"Tipo de cambio: actualizar desde SUNAT"* corre a diario.
3. Al crear una factura en USD (con la compañía en PEN), el formulario muestra
   **Tipo de cambio** y **Fecha del T.C.** en la cabecera.

## Modelo de datos

- `res.currency.rate`: `+ rate_purchase`, `+ rate_sale`, `+ ref_origin`
  (`sunat` / `apis_net` / `manual`). Se respeta la unicidad nativa de v19
  `unique(name, currency_id, company_id)` (una tasa por día); `ref_origin` es
  informativo.
- `account.move`: `l10n_pe_exchange_rate`, `l10n_pe_exchange_rate_date`,
  `l10n_pe_show_exchange_rate` (computados, no almacenados). La tasa mostrada es
  `1 / invoice_currency_rate`, por lo que refleja también los ajustes manuales
  de tasa en la factura.
- `l10n_pe.exchange.rate.wizard`: asistente de actualización (autónomo; los
  campos de filtro de fechas están integrados, sin `al_base_mixin`).

## Migración / notas

- Refactor desde v18. Se **eliminó el módulo `al_base_mixin`** (los campos de
  fecha del asistente se inlinearon) y todo el scraping obsoleto de SBS /
  Selenium / Yahoo Finance.
- Depende solo de `account`. Requiere `requests` (Python).
- Alternativa nativa: Odoo 19 EE incluye el provider `bcrp` (`Ajustes ▸
  Contabilidad ▸ Tipo de cambio en vivo`), que trae solo la tasa única de
  venta; este módulo lo complementa con compra/venta.

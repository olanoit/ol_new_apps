# Plan — `al_l10n_pe_edi_downpayment_discount` (anticipos y descuentos globales SUNAT)

Pedido: un módulo equivalente a `dv_l10n_pe_edi_anticipos_y_descuentos_globales`
(Develogers, v18, OPL-1), adaptado a la suite. Se implementa **desde la norma
SUNAT**, sin su código (mismo criterio que el clean-room de tecport).

## Fuentes oficiales (`oficial/`)

Descargadas de https://cpe.sunat.gob.pe/guias-y-manuales el 06/10/2026:

- `Reglas_de_validacion_20260826.xlsx` — reglas de validación CPE.
- `guia_xml_factura_ubl21.pdf`, `guia_xml_boleta_ubl21.pdf`,
  `guia_xml_nota_credito_ubl21.pdf` — guías de elaboración del XML.
- `Estructuras_202606.xlsx`.

Las reglas que tocan anticipos, cargos y descuentos y totales están en
[`REGLAS_SUNAT_ANTICIPOS_DESCUENTOS.md`](REGLAS_SUNAT_ANTICIPOS_DESCUENTOS.md).

## Fase 0 — diagnóstico de Odoo 19 nativo

`tests/sunat_rules.py` del módulo implementa las reglas de cuadre (3271, 3272, 3277, 3278,
3279, 3280, 3291, 3294, 3274/3275, 3300/3301, 2509, 2365, 3211-3220, 3282/3287,
3307…) y `escenarios_xml.py` genera los XML nativos de 16 escenarios en
`ol_pe_v19` (todo en una transacción que se deshace).

Odoo 19 Enterprise (`l10n_pe_edi`) **ya cubre** lo básico de anticipos y
descuentos: `PrepaidPayment`, `AdditionalDocumentReference`, cargo `04`,
descuento global `02`, descuento de línea `00`, IGV incluido, USD y boletas
(E1-E8, E15: sin incumplimientos). Lo que falla:

| # | Fallo nativo | Escenarios | Reglas SUNAT |
|---|---|---|---|
| F1 | El anticipo de partes exoneradas/inafectas sale con código `02`: el mapa nativo usa la afectación `11`/`12` (gratuitas) en vez de `20`/`30`. | E9, E11 | 3277, 3291, 3274/3275, 3278, 3279 |
| F2 | Un anticipo deducido en varias líneas (una por impuesto) genera una referencia y un pago por línea: el mismo comprobante repetido. | E9, E11 | 2365 (ERROR), 3215 |
| F3 | El tipo del comprobante de anticipo (02/03) se toma de la factura final, no del propio anticipo. | (revisión) | 2505/2521 |
| F4 | Un descuento global sobre partes exoneradas/inafectas sale como `02`, que solo puede restarse de la base gravada. | E13, E14 | 3274/3275, 3277, 3291, 3279 |
| F5 | No se puede publicar la nota de crédito de una factura con anticipos o con descuento global: Odoo prohíbe líneas negativas en la NC. | E10, E12 | — (bloqueo) |
| F6 | No se puede publicar la NC/ND de una factura con descuento de línea: Odoo obliga a rehacer las líneas a mano. | E16 | — (bloqueo; en NC el valor del ítem debe ser precio × cantidad, regla 3271) |

## Diseño

Solo se corrige lo que falla; el resto queda en manos de `l10n_pe_edi`.

1. **F1** — código del cargo de anticipo por la afectación del IGV de la
   línea (catálogo 07 → catálogo 53): `1x` → `04`, `2x` → `05`, `3x` → `06`.
2. **F2/F3** — una `AdditionalDocumentReference` y un `PrepaidPayment` por
   **comprobante de anticipo**, con la suma de sus líneas y su propio tipo
   (factura `02`, boleta `03`).
3. **F4** — en facturas y boletas, el descuento global de un grupo no gravado
   se reparte entre los ítems de ese grupo como descuento de línea `00`
   (proporcional, sin perder céntimos). El gravado sigue con el `02` nativo.
4. **F5/F6** — en notas de crédito y débito, las líneas negativas (deducción
   de anticipo, descuento global) se reparten entre los ítems del mismo
   impuesto, y el precio unitario se informa neto (valor del ítem ÷
   cantidad), como exige la regla 3271 de la NC. Se levantan los dos
   bloqueos nativos; solo queda el error si las líneas negativas de un
   impuesto superan a las positivas.

Todo ocurre al generar el XML: **el asiento contable no cambia** (la deducción
del anticipo sigue en su cuenta).

## Pruebas

`tests/` usa ese validador y recorre los escenarios E1-E16 con el módulo
instalado: ningún incumplimiento de las reglas SUNAT y los mismos totales que
el asiento.

## Pruebas reales en SUNAT (entorno beta, 06/10/2026)

Enviados desde `ol_pe_v19` (`cfg/my/pe.cfg`, proveedor SUNAT en modo de
pruebas) con el módulo instalado. Todos **aceptados con código 0**:

| Caso | Documento | Antes (XML nativo) | Con el módulo |
|---|---|---|---|
| Anticipo gravado + exonerado, factura final | F002-00000004 | Rechazo 2365 (referencia repetida) | Aceptada |
| NC de esa factura final | FC02-00000002 | Rechazo 0306 (PrepaidPayment en la NC) | Aceptada |
| Anticipo gravado + inafecto (04 + 06) | F002-00000005/6 | — | Aceptadas |
| Descuento global exonerado | F002-00000007 | — | Aceptada |
| Descuento global mixto | F002-00000008 | — | Aceptada |
| NC de una factura con descuento global | FC02-00000003 | No se podía publicar | Aceptada |
| NC de una factura con descuento de línea | FC02-00000004 | No se podía publicar | Aceptada |

Las observaciones 4233 de las facturas vienen de usar la «Referencia» de la
factura como rótulo del caso (Odoo la envía como orden de compra); no son del
módulo.

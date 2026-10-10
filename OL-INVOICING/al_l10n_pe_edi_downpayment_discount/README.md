# PE - Anticipos y descuentos globales en el CPE (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo técnico `al_l10n_pe_edi_downpayment_discount`. Corrige el XML UBL 2.1
que Odoo 19 envía a SUNAT cuando la factura lleva anticipos o descuentos
globales, y permite emitir las notas de crédito y débito que Odoo bloquea.

## Qué corrige

La localización de Odoo 19 Enterprise (`l10n_pe_edi`) ya emite los anticipos
(`cac:PrepaidPayment`, cargo `04`) y el descuento global (`02`). Contrastada con
las reglas de validación oficiales de SUNAT (26.08.2026), falla en estos casos:

| # | Caso | Odoo 19 | Con el módulo |
|---|---|---|---|
| F1 | Anticipo de una venta con partes exoneradas o inafectas | Código `02` (rechazo 3277, 3291, 3274/3275, 3278, 3279) | `05` exonerado, `06` inafecto |
| F2 | Un anticipo deducido en varias líneas (una por impuesto) | El mismo comprobante referenciado varias veces (rechazo 2365) | Una referencia y un `PrepaidPayment` por comprobante |
| F3 | Tipo del comprobante de anticipo | Tomado de la factura final | Tomado del propio anticipo (factura `02`, boleta `03`) |
| F4 | Descuento global sobre partes exoneradas o inafectas | Código `02`, que solo resta de la base gravada | Repartido entre los ítems como descuento de línea `00` |
| F5 | Nota de crédito de una factura con anticipo o descuento global | No se puede publicar (líneas negativas) | Se publica; el XML reparte la deducción entre los ítems |
| F6 | Nota de crédito o débito de una factura con descuento de línea | No se puede publicar | Se publica; el XML informa el precio neto (regla 3271) |

**El asiento no cambia**: todo ocurre al generar el XML. La deducción del
anticipo de una nota de crédito sigue en su cuenta.

## Cómo se usa

Nada que configurar: el flujo es el nativo de Ventas.

1. Pedido de venta confirmado ▸ **Crear factura ▸ Anticipo** (porcentaje o
   monto fijo). Se emite el comprobante del anticipo.
2. Más anticipos, si hace falta.
3. **Crear factura ▸ Factura regular**: Odoo deduce los anticipos y el XML los
   informa con `PrepaidPayment` y los cargos `04`/`05`/`06`.
4. Para anular la factura final: **Nota de crédito**; se publica sin rehacer
   las líneas.

Los descuentos globales son líneas negativas con el impuesto de lo que
descuentan (por ejemplo, el producto de descuento de Ventas).

## Detalles técnicos

- `models/account_edi_xml_ubl_pe.py` extiende el exportador `account.edi.xml.ubl_pe`:
  - código del anticipo según la afectación del IGV (catálogo 07 → catálogo 53);
  - referencias y pagos agrupados por comprobante de anticipo;
  - reparto proporcional de líneas negativas entre los ítems del mismo
    impuesto, sin perder céntimos (el residuo va al ítem mayor);
  - precio neto en notas y factor de descuento calculado sobre los importes.
- `models/account_edi_format.py` y `models/account_move.py` levantan los dos
  bloqueos nativos de las notas. Solo queda el error cuando las líneas
  negativas de un impuesto superan a las positivas.

## Pruebas

`tests/sunat_rules.py` implementa las reglas de cuadre de SUNAT (3271, 3272,
3277-3280, 3291, 3294, 3274/3275, 3300/3301, 2509, 2365, 3211-3220, 3282/3287,
3307…). `tests/test_sunat_rules.py` recorre 20 escenarios: anticipos simples,
dobles, en dólares, con IGV incluido, en boletas, mixtos y notas de crédito.
Todos sin incumplimientos y con el mismo total que el asiento.

El diagnóstico de Odoo nativo y las fuentes oficiales están en
`docs/anticipos/` del repositorio.

## Procedencia y licencia

Equivalente funcional del módulo comercial
`dv_l10n_pe_edi_anticipos_y_descuentos_globales` (Develogers), implementado
desde las reglas de validación de SUNAT, sin su código. Licencia **OPL-1**.
El historial de versiones está en [`CHANGELOG.md`](CHANGELOG.md).

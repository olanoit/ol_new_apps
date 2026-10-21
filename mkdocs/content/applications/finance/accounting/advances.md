---
modulos: [al_l10n_pe_payment_application]
---

# Anticipos y aplicación de documentos

Un **anticipo** es dinero que se paga o se recibe antes del comprobante. El módulo
**Anticipos y aplicación de documentos** (`al_l10n_pe_payment_application`) lo
registra como un pago normal en la cuenta de anticipos y permite **aplicarlo** a la
factura cuando llega. El mismo documento sirve para **compensar** lo que el socio
nos debe con lo que le debemos y para **aplicar notas de crédito**.

## Conceptos

| Cuenta (PCGE) | Uso |
|---|---|
| 122 Anticipos de clientes | Lo que el cliente pagó a cuenta, antes de su factura |
| 422 Anticipos a proveedores | Lo que se pagó al proveedor antes de recibir su comprobante |

!!! warning "Anticipos de clientes y el IGV"
    El cobro anticipado de una venta de bienes o servicios hace nacer el IGV y
    obliga a emitir el comprobante (Ley del IGV, art. 4; Reglamento de
    Comprobantes de Pago, art. 5). Para eso use el **anticipo de venta con
    factura** del pedido ([Anticipos y descuentos](../fiscal_localizations/peru/electronic_invoicing/down_payments_discounts.md)).
    La 122 sin comprobante queda para arras, depósitos o garantías y cobros a
    cuenta aún no identificados con una venta. La 422 (proveedores) es el caso
    más frecuente.

## Configuración

En **Ajustes ‣ Perú ‣ Anticipos y aplicación de documentos**:

1. **Cuentas de anticipos**: por defecto la 122 y la 422; opcionalmente una para
   moneda extranjera de cada una.
2. **Diario de aplicaciones**: por defecto «Aplicación de documentos» (APLI).

## Registrar un anticipo

1. Vaya a **Perú ‣ Proveedores ‣ Anticipos a proveedores** (o **Perú ‣ Clientes ‣
   Anticipos de clientes**) y haga clic en **Nuevo**. La casilla **Anticipo** ya
   viene marcada.
2. Elija el socio, el diario, el importe y el medio de pago, y confirme. El
   asiento va contra la 422 (o la 122) en lugar de la cuenta por pagar (o por
   cobrar).
3. Imprima el [comprobante de pago](payment_receipts.md): muestra «Anticipo,
   queda a cuenta».

!!! note
    Si el diario no tiene cuenta de pagos pendientes, el anticipo no tiene asiento
    hasta conciliar el extracto bancario; recién entonces se puede aplicar.

## Aplicar el anticipo a la factura

1. Publique la factura del proveedor (o del cliente). Si el socio tiene anticipos
   sin aplicar, el chatter lo avisa y la factura muestra el botón **Anticipos**.
2. Haga clic en **Anticipos**: se abre una **aplicación de documentos** con la
   factura y los anticipos del socio, y los importes ya repartidos.
3. Ajuste los importes si quiere aplicar solo una parte y haga clic en **Aplicar**.

Odoo crea un asiento en el diario de aplicaciones que traslada el saldo (por
ejemplo, debe 4212 / haber 422) y concilia la factura con el anticipo. Desde el
anticipo, el botón **Aplicar a factura** hace lo mismo con las facturas abiertas
del socio.

### Ejemplo

Se paga a un proveedor un anticipo de S/ 3 000 y luego llega su factura por
S/ 5 000:

| Documento | Lado | Saldo | Aplicado |
|---|---|---|---|
| Factura F001-123 (4212) | Acreedor | 5 000,00 | 3 000,00 |
| Anticipo PBNK1/2026/00031 (422) | Deudor | 3 000,00 | 3 000,00 |

La factura queda con S/ 2 000 por pagar y el anticipo, cancelado.

## Compensar y aplicar notas de crédito

En **Perú ‣ Clientes (o Proveedores) ‣ Aplicación de documentos**, cree una
aplicación, elija el socio y haga clic en **Cargar documentos**: aparecen todos
sus saldos abiertos (facturas de venta y de compra, anticipos, notas de crédito).
**Distribuir** reparte el menor de los dos lados por antigüedad; **Quitar sin
importe** limpia las líneas que no se usan. Lo aplicado a los saldos deudores debe
ser igual a lo aplicado a los acreedores.

## Moneda extranjera

Cada línea se aplica en su moneda y se valora al cambio de la **fecha de la
aplicación**. Si un anticipo en soles cancela una factura en dólares, la
diferencia con el cambio de la factura la registra Odoo como diferencia de
cambio al conciliar.

## Anticipos pendientes

**Perú ‣ Clientes (o Proveedores) ‣ Anticipos pendientes** lista los anticipos con
saldo, agrupados por socio, con vista pivote.

## Revertir

Un administrador de contabilidad puede **Revertir** una aplicación: Odoo crea el
asiento inverso y vuelve a abrir los documentos.

## Casos especiales

| Situación | Qué pasa |
|---|---|
| Documento de otro socio | La aplicación se rechaza |
| Letra en el banco o factura cedida con recurso | No se carga y la aplicación se rechaza: la cobra el banco o el factor |
| Importe mayor que el saldo | Se rechaza |
| Lado deudor distinto del acreedor | Se rechaza (solo se admiten los céntimos del redondeo, que van a diferencia de cambio) |
| Anticipo sin cuenta configurada | No se puede confirmar |

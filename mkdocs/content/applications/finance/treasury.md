---
modulos: [al_l10n_pe_treasury, al_l10n_pe_treasury_batch_payment]
---

# Tesorería

La aplicación **Tesorería** (`al_l10n_pe_treasury`) reúne el trabajo diario del
tesorero: saber cuánto dinero hay y cuánto se puede usar, decidir qué se paga y
que alguien lo apruebe, mover fondos entre las cuentas de la empresa, comprar o
vender dólares y controlar las líneas de crédito de cada banco.

No es un registro paralelo: los saldos salen de la contabilidad, los pagos son
los de Odoo y las transferencias quedan listas para conciliar con el extracto.
Además agrupa en su menú lo que ya hacía la suite: el
[flujo de caja proyectado](accounting/cash_forecast.md), los
[depósitos a plazo y garantías](accounting/term_deposits.md), los
[cheques](accounting/checks.md), los [cierres de caja](accounting/cash_closing.md)
y las [entregas a rendir](accounting/cash_fund.md). El financiamiento se amplía
con los [préstamos y pagarés](treasury/bank_loans.md) y las
[cartas fianza](treasury/bank_guarantees.md).

Quedan fuera la conexión directa con los bancos (los extractos se importan con
[extractos de bancos peruanos](accounting/bank_statements_pe.md)) y la
conciliación, que es la de Odoo.

## Configuración

1. **Usuarios.** En *Ajustes ‣ Usuarios*, el privilegio *Tesorería* tiene tres
   niveles: **Usuario** (prepara la posición, las transferencias y las
   programaciones), **Aprobador** (además aprueba) y **Administrador** (segunda
   aprobación, líneas de crédito y configuración).
2. **Ajustes ‣ Perú ‣ Tesorería**:
    - *Aprobación de pagos*: importe desde el que una programación necesita una
      firma (con 0, todas) y, si se quiere, el importe de la segunda firma.
    - *Aprobación de transferencias*: importe en soles desde el que una
      transferencia necesita aprobación (0: ninguna).
    - *Aviso de vencimientos*: días de anticipación de los avisos.
    - *Bancarización*: no controlar, avisar o bloquear, y los montos (S/ 2 000 y
      US$ 500).
3. **Bancos y cajas** (*Tesorería ‣ Configuración ‣ Bancos y cajas*), pestaña
   *Tesorería* de cada diario: tipo de cuenta, **saldo mínimo**, **sobregiro
   autorizado** y **fondos no disponibles** (la cuenta de detracciones del
   Banco de la Nación).
4. En *Contabilidad ‣ Configuración ‣ Ajustes*, la **cuenta de transferencias
   internas** (1051) y, en cada banco, las **cuentas de pagos y cobros
   pendientes** de sus métodos de pago: sin ellas Odoo no registra el asiento
   del pago hasta conciliar el extracto.

## Posición diaria

*Tesorería ‣ Posición ‣ Posición diaria*. Cada día se guarda sola una posición
por compañía; **Actualizar** la recalcula. Por cada banco o caja muestra:

| Columna | Qué es |
|---|---|
| Saldo contable | Saldo de la cuenta del banco a la fecha, en la moneda de la cuenta. |
| Saldo del extracto | Saldo final del último extracto. |
| Cobros y pagos en tránsito | Pagos confirmados que aún no se concilian con el extracto. |
| Pagos programados | Lo aprobado en las programaciones de pago y aún no pagado. |
| Saldo proyectado | Contable + tránsito − programado. |
| Disponible | Proyectado − saldo mínimo + sobregiro; cero en las cuentas no disponibles. |

Los totales van en soles al tipo de cambio de la fecha. *Evolución del
disponible* grafica las posiciones guardadas.

## Programación de pagos

*Tesorería ‣ Operaciones ‣ Programación de pagos*.

1. Cree la programación con el **banco** y la **fecha de pago** (y el método de
   pago si no es el primero del banco).
2. **Proponer documentos**: agrega las facturas por pagar vencidas hasta una
   fecha, de los proveedores elegidos y en la moneda del banco. Un documento no
   puede estar en dos programaciones abiertas.
3. Ajuste **A pagar** para un pago parcial o quite documentos. Si el total
   supera el disponible del banco, el formulario lo avisa.
4. **Enviar a aprobar**. El aprobador recibe una actividad; quien prepara no
   puede aprobar. Desde el importe de la segunda firma hace falta además un
   administrador distinto del primero. **Devolver** deja la programación en
   borrador y borra las firmas.
5. **Pagar** registra los pagos con el asistente de Odoo: uno por proveedor (o
   uno por documento si alguno es parcial), con la retención, el ITF y el T.C.
   de la suite. Con el método **archivo TXT del banco** de los
   [pagos masivos](accounting/batch_payments.md), los pagos quedan en un lote
   listo para generar el archivo.

*Documentos programados* lista lo que está por pagar, por proveedor y
programación.

## Transferencias y cambio de moneda

*Tesorería ‣ Operaciones ‣ Transferencias y cambio de moneda*. Indique la
cuenta de origen, la de destino y el importe enviado.

- **Misma moneda**: se recibe lo mismo que se envía.
- **Compra o venta de dólares**: indique el **T.C. pactado** con el banco o la
  casa de cambio; el importe recibido se calcula (si registra lo que abonó el
  banco, se recalcula el T.C.).
- **Valorización**: *al T.C. pactado* (la parte en dólares vale en soles lo que
  se pagó) o *al T.C. contable del día*: la diferencia va a **676** (pérdida) o
  **776** (ganancia).
- **ITF**: las transferencias entre cuentas del mismo titular no están gravadas
  (Informe SUNAT 143-2010). Si el banco lo cobró, marque *ITF en el origen* o
  *en el destino*.

**Confirmar** registra la salida del origen y la entrada al destino como dos
pagos contra la cuenta de transferencias (1051), conciliados entre sí; cada uno
se concilia después con su extracto. Si el importe supera el de Ajustes, la
operación pasa por aprobación. **Anular** anula los pagos y revierte la
diferencia de cambio (no si ya se concilió con el extracto).

## Líneas de crédito

*Tesorería ‣ Financiamiento ‣ Líneas de crédito* (administradores). Por banco:
tipo (global, préstamos, cartas fianza, descuento, sobregiro), moneda, límite,
vigencia, tasa y garantías. El **utilizado** suma el saldo de capital de los
préstamos y el importe de las cartas fianza emitidas asignados a la línea; un
préstamo o una carta fianza que supere el disponible no se registra. Antes del
vencimiento, el responsable recibe un aviso.

## Bancarización

El TUO de la Ley 28194 obliga a pagar con medios de pago (depósito,
transferencia, cheque, tarjeta…) desde **S/ 2 000 o US$ 500** (DL 1529); sin
ellos no se deduce el gasto ni el crédito fiscal. Al confirmar un pago en
efectivo —medio de pago 008 o 009 de la tabla 1, o un diario de caja sin medio
de pago— desde ese monto, la app avisa en el pago o lo bloquea, según Ajustes.
El control mira el importe del pago: un pago parcial en efectivo de una factura
mayor no se detecta.

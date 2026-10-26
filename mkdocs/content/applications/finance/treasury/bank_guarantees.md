---
modulos: [al_l10n_pe_bank_guarantee]
---

# Cartas fianza

El módulo **Cartas fianza** (`al_l10n_pe_bank_guarantee`) controla las cartas
fianza que el banco emite a pedido de la empresa —para una licitación, un
contrato o un adelanto— y las que la empresa recibe de sus proveedores y
contratistas. Es parte de la aplicación [Tesorería](../treasury.md).

Una carta fianza no es deuda mientras no se ejecute, pero su vencimiento
importa: una emitida que vence sin renovarse puede costar el contrato, y en una
recibida el banco queda libre si no se le requiere dentro de los **15 días
siguientes al vencimiento** (art. 1898 del Código Civil).

## Configuración

- *Ajustes ‣ Perú ‣ Tesorería ‣ Aviso de vencimientos*: días de anticipación.
- *Cartas fianza en cuentas de orden* (opcional): diario y cuentas. Por defecto
  0113 / 0114 para las emitidas y 0129 / 0126 para las recibidas.

## Registrar una carta fianza

*Tesorería ‣ Financiamiento ‣ Cartas fianza*.

1. **Sentido**: emitida a nuestro pedido o recibida de un tercero.
2. Tipo (fiel cumplimiento, adelanto directo, adelanto de materiales, seriedad
   de oferta, pago, aduanera), banco emisor, beneficiario o afianzado, contrato
   o proceso, importe, emisión y vencimiento, número del banco y condiciones
   (solidaria, irrevocable, incondicional, de realización automática, sin
   beneficio de excusión).
3. En las emitidas: banco de la empresa, **comisión** (% por trimestre o
   fracción, con mínimo), cuenta (6391), ITF, línea de crédito y el fondo en
   garantía que el banco retiene, si lo hay
   ([depósitos y garantías](../accounting/term_deposits.md)).
4. **Registrar vigente**: se debita la comisión y, si están activadas, se
   registran las cuentas de orden.

## Durante su vigencia

- **Avisos**: el responsable recibe una actividad antes del vencimiento. En las
  recibidas vence el último día para requerir al banco.
- **Renovar**: nueva carta fianza enlazada (mismo número salvo que el banco
  emita otro), con su comisión.
- **Liberar**: devuelta al cumplirse la obligación; se extornan las cuentas de
  orden.
- **Ejecutar**: emitida, el banco paga al beneficiario y lo debita a la empresa
  (indique la contrapartida); recibida, la empresa cobra al banco (p. ej. contra
  el anticipo no devuelto del contratista).
- Las emitidas vigentes consumen la línea de crédito del banco.

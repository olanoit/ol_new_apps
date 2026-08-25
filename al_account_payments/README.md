# PE - Medios de pago SUNAT (AL)

Catálogo de medios de pago de SUNAT y datos de la operación bancaria en el
pago, para sustentar la bancarización y alimentar el comprobante
electrónico.

> **Depende de** `account`, `al_account_base` · **Licencia** OPL-1

---

## Qué hace

* **Catálogo `pe.catalog.payment`** con los medios de pago de SUNAT
  —depósito en cuenta, transferencia, cheque, efectivo…—, cada uno con:
  * su **código de facturador** (PSE), que es el que viaja al comprobante
    electrónico;
  * la marca de **válido para detracción**, que identifica los medios
    admitidos para el depósito del SPOT.
* **Campos en el pago** (`account.payment`): medio de pago y número de
  operación del banco.
* **Campos en el asistente de registro de pagos**, que los traslada a los
  pagos que crea. Sin esto habría que abrir cada pago después para
  completarlos.
* **Menú de mantenimiento** en Contabilidad → Configuración y en el menú
  Perú → Configuración.

## Por qué importa

El medio de pago no es un dato administrativo: es lo que permite sustentar
el uso de **medios de pago bancarizados** ante una fiscalización, y viaja
al comprobante electrónico. El número de operación es lo que después se
cruza con el extracto bancario.

## Notas de la migración

Viene del módulo equivalente de la versión 18, con dos cambios:

* El catálogo **ya no hereda** de un modelo `pe.catalog` genérico — ese
  modelo se eliminó de `al_account_base` en v19 al quitarle el código
  muerto.
* Se quitó una dependencia muerta que el módulo arrastraba sin usar.

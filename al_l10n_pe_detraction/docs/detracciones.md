[← Índice de la app Perú](../../al_l10n_pe_ple/docs/README.md)

# Detracciones SPOT (Sistema de Pago de Obligaciones Tributarias)

**Menú de configuración:** Perú ▸ Configuración ▸ **Detracciones (SPOT)** ·
**Operación:** pestaña **Detracción** de la factura · **Módulo:**
`al_l10n_pe_detraction`.

**Qué es:** mecanismo de SUNAT por el cual el comprador de bienes/servicios
del Anexo (catálogo 54) descuenta («detrae») un porcentaje del importe
total y lo deposita en la cuenta del proveedor en el **Banco de la
Nación**; el proveedor cobra el neto. Aplica en general a operaciones
mayores a **S/ 700** (S/ 400 en transporte de bienes; sin mínimo en oro,
minerales e inmuebles).

## Configuración inicial (una sola vez)

1. **Catálogo** — Perú ▸ Configuración ▸ Detracciones (SPOT): viene
   precargado con los códigos del catálogo 54, sus **porcentajes vigentes**
   y **montos mínimos** (editables; p. ej. actualizar la ½ UIT del Anexo 1
   cada año). Si SUNAT cambia un porcentaje: editarlo y pulsar
   **«Actualizar productos vinculados»**.
2. **Productos afectos** — en la ficha del producto (pestaña Contabilidad,
   junto a los campos SUNAT): elegir el **Tipo de detracción (SPOT)**. El
   código y el porcentaje nativos (los que usa la factura electrónica) se
   completan solos.
3. **Cuenta del Banco de la Nación** (solo ventas) — en el contacto de la
   compañía ▸ pestaña Contabilidad ▸ cuentas bancarias: agregar la cuenta
   de detracciones con banco **Banco de la Nación**. El XML UBL la incluye
   en el bloque «Detraccion».
4. **Diario del BN** (recomendado) — crear un diario de banco que
   represente la cuenta de detracciones, para registrar los cobros de
   detracción de las ventas.

## Flujo en ventas

1. Crear la factura con los productos afectos. Si el total (con IGV, en
   soles) supera el mínimo, aparece la pestaña **Detracción** con: tipo
   (código **dominante** = mayor % entre los productos), porcentaje,
   **monto redondeado a soles enteros** y neto a cobrar.
2. Al **publicar**, el tipo de operación EDI se fija en `1001` si no se
   eligió otro valor 100x; el XML electrónico sale con el bloque de
   detracción (cuenta BN, medio de pago 999) y la leyenda SPOT.
3. El cliente paga el **neto** por el canal normal y deposita la
   detracción en la cuenta del BN. Cuando llegue la constancia: botón
   **«Registrar depósito»** → diario del BN + nº y fecha de constancia.

## Flujo en compras

1. Registrar la factura del proveedor con los productos afectos: la
   pestaña **Detracción** calcula el monto a detraer.
2. Depositar la detracción en el BN (Págalo.pe / portal SUNAT) a nombre
   del proveedor y luego **«Registrar depósito»**: diario del banco
   propio, monto (editable), nº y fecha de la **constancia**. Se genera el
   pago parcial vinculado a la factura (el asiento contable nace al
   conciliar el extracto, flujo estándar v19) y queda pendiente solo el
   neto al proveedor.
3. Pagar el neto al proveedor con el flujo normal de pagos.

> El crédito fiscal del IGV de una operación sujeta a detracción solo se
> puede ejercer desde que el depósito está efectuado: la constancia
> registrada es la evidencia.

## Reportes

- **PLE 8.1** (Compras, EE) y **PLE 8.3** (Compras Simplificado, módulo
  PLE): la constancia registrada sale en los campos de detracción
  (32-33 y 24-25 respectivamente).
- Filtros en facturas: **«Con detracción»** y **«Detracción sin
  constancia»** (pendientes de depósito/registro).

## Errores comunes

| Situación | Causa / solución |
|---|---|
| No aparece la pestaña Detracción | El producto no tiene tipo SPOT, o el total no supera el mínimo del código. |
| XML sin bloque de detracción | Falta la cuenta del Banco de la Nación en la compañía, o el tipo de operación no es 100x. |
| % desactualizado en facturas nuevas | Editar el catálogo y «Actualizar productos vinculados»; las facturas en borrador recalculan al editar líneas. |
| 8.1/8.3 sin constancia | No se usó «Registrar depósito» (o no se llenaron los campos de constancia de la factura). |

## Datos de prueba

`tools/detraction_demo_data.py` crea el escenario completo «DEMO SPOT» y
valida 9 puntos del flujo (cálculo, XML, depósito y reportes) vía
`odoo-bin shell`.

[← Índice](README.md)

# Libro 9 — Registro de Consignaciones (9.1 / 9.2)

**Qué es:** libro mensual que controla los bienes entregados (9.1, rol
**consignador**) o recibidos (9.2, rol **consignatario**) en consignación,
en unidades físicas.

## Configuración por operación

Cada albarán de consignación se marca en **Inventario ▸ Transferencias** →
campo **Consignación PLE (Libro 9)** (visible junto al tipo de operación
SUNAT, solo compañías PE):

| Valor | Cuándo usarlo |
|---|---|
| 9.1 Entrega en consignación | Salida de mercadería hacia el consignatario. |
| 9.1 Devolución del consignatario | El consignatario devuelve mercadería. |
| 9.1 Venta de bienes consignados | El consignatario vendió: salida definitiva. |
| 9.2 Recepción en consignación | Ingreso de mercadería de un consignador. |
| 9.2 Devolución al consignador | Se devuelve mercadería recibida. |
| 9.2 Venta de bienes recibidos | Se vendió mercadería recibida en consignación. |

Reglas prácticas:
- El **contacto del albarán** es la contraparte (consignatario en 9.1,
  consignador en 9.2 — este último debe tener RUC).
- El **producto** debe tener «Tipo de existencia» (pestaña de inventario,
  tabla 5) y su unidad de medida el código SUNAT (tabla 6) — ambos campos
  vienen de la localización EE.
- Solo cuentan transferencias **hechas** dentro del mes.
- En las clases «venta», el sistema busca la factura publicada de la orden
  de venta ligada al albarán para llenar el comprobante (campos 11–14).

## Generación

Perú ▸ Libros PLE ▸ **Exportar PLE** → Ejercicio + **Mes** → marcar
**9.1** y/o **9.2** → **Generar**.

## Saldo inicial

La primera línea de cada producto/contraparte es el **saldo inicial**:
entregas − devoluciones − ventas de los meses anteriores (albaranes
marcados). Se emite con guía `0/0` y fecha del primer día del mes. Por eso
es importante marcar las operaciones de consignación **desde el inicio**
del uso del módulo.

## Qué revisar

- 9.1: cantidad entregada en positivo; devoluciones y ventas en negativo
  (columnas excluyentes entre sí).
- Si una guía de remisión electrónica existe (`l10n_pe_edi_stock`), su
  número alimenta la serie/número; si no, se usan los dígitos de la
  referencia del albarán.

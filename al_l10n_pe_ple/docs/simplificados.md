[← Índice](README.md)

# Formatos simplificados (5.2 / 5.4 / 8.3 / 14.2)

**Qué son:** versiones reducidas del Diario (5.2 + su plan contable 5.4),
del Registro de Compras (8.3) y del Registro de Ventas (14.2), para
contribuyentes autorizados a llevar **contabilidad simplificada**. Son
**excluyentes** con los formatos completos (5.1/5.3, 8.1, 14.1): una
empresa presenta unos u otros, nunca ambos.

## Habilitación (una sola vez)

**Ajustes ▸ Perú ▸ «Libros PLE simplificados»** → activar y guardar. Esto:

1. Muestra el grupo «Formatos simplificados» en el wizard Exportar PLE.
2. Autoriza su generación (sin la bandera el wizard los rechaza).

## Origen de los datos (sin captura adicional)

| Formato | Fuente |
|---|---|
| 5.2 | Todos los **asientos publicados** del mes (una línea por apunte). La glosa sale del campo Glosa del asiento/línea, o de la referencia. |
| 5.4 | Todas las **cuentas activas** del plan contable de la compañía. |
| 8.3 | **Facturas y NC de proveedor publicadas** del mes; el nº del comprobante se toma de la *Referencia del proveedor* de la factura. |
| 14.2 | **Facturas y NC de cliente publicadas** del mes. |

Los montos se desglosan así: base imponible gravada (documentos con IGV),
IGV/IPM, ICBPER (impuestos cuyo nombre contiene «ICBPER») y otros
conceptos (documentos sin IGV). Las notas de crédito salen en negativo y
sus campos 20–23 referencian el comprobante original. El tipo de cambio
(3 decimales) solo se emite en documentos en moneda extranjera.

## Generación

Perú ▸ Libros PLE ▸ **Exportar PLE** → Ejercicio + **Mes** → marcar los
formatos → **Generar** (ZIP si son varios).

## Qué revisar

- El 5.2 debe cuadrar débito=crédito por asiento; se genera con las mismas
  líneas que produciría el 5.1 completo (verificado contra el reporte EE).
- Documentos con operaciones mixtas (gravadas + exoneradas en la misma
  factura) se clasifican por si el documento lleva IGV: para esa casuística
  usar los formatos completos.
- En 8.3, completar siempre la **Referencia del proveedor** con el formato
  `SERIE-NÚMERO` (p. ej. `F001-00000123`).

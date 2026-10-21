---
modulos: [al_l10n_pe_edi_free]
---

# Operaciones gratuitas

Una **transferencia gratuita** es la entrega de un bien o servicio sin cobrarlo: un
premio, una donación, una bonificación con la compra, una muestra médica, un
artículo publicitario o una entrega a los trabajadores. El comprobante se
emite igual, pero con **precio 0** y el **valor referencial** del ítem (lo que
costaría en una venta normal).

Odoo 19 ya arma ese XML para los retiros gravados con el impuesto **18% Free
Group**. El módulo **Operaciones gratuitas en el CPE** (`al_l10n_pe_edi_free`)
completa el resto: las gratuitas **exoneradas o inafectas**, la **leyenda
1002**, la **forma de pago** y las **validaciones** de SUNAT al publicar.

## Conceptos

| Afectación (catálogo 07) | Caso | IGV | Impuesto en Odoo |
|---|---|---|---|
| 11 a 16 | Retiro gravado: premio, donación, retiro, publicidad, bonificación, entrega a trabajadores | 18 % sobre el valor referencial, que asume quien entrega (va al gasto) | **18% Free Group** |
| 21 | Exonerado – transferencia gratuita | No | **0% Gratuito exonerado/inafecto** |
| 31 a 37 | Inafecto – retiro por bonificación, retiro, muestras médicas, convenio colectivo, premio, publicidad o transferencia gratuita | No | **0% Gratuito exonerado/inafecto** |

- **Valor referencial**: el precio unitario de la línea. Se informa con el
  código de precio **02** y el precio cobrado va en 0.
- **Leyenda 1002**: «TRANSFERENCIA GRATUITA DE UN BIEN Y/O SERVICIO PRESTADO
  GRATUITAMENTE».
- **Asiento**: el ítem gratuito no genera ingreso ni cuenta por cobrar. En un
  retiro gravado, el IGV se abona a la 40111 y se carga al gasto (6411).

## Configuración

1. Instale **Operaciones gratuitas en el CPE**. Crea el impuesto **0%
   Gratuito exonerado/inafecto** en las compañías con el plan peruano.
2. Para que la afectación aparezca en las líneas de la factura, active la
   columna **Motivo de afectación EDI** en la lista de líneas.

## Emitir una factura gratuita

1. Cree la factura de cliente con sus productos y el **precio normal** de cada
   uno.
2. Haga clic en **Transferencia gratuita**. Lo gravado pasa a **18% Free
   Group** (afectación 11), lo exonerado a **0% Gratuito exonerado/inafecto**
   con la 21 y lo inafecto al mismo impuesto con la 37. La factura queda en 0.
3. Si corresponde, cambie la **afectación** de cada línea (por ejemplo, 15 –
   bonificación o 33 – muestras médicas).
4. Haga clic en **Confirmar**. Odoo pone la leyenda 1002, quita el plazo de
   pago (la factura sale **al contado**) y la envía a SUNAT.

Para regalar solo **algunos ítems** de una venta (bonificación con la compra),
no use el botón: ponga el impuesto gratuito solo en esas líneas. Se cobra lo
demás, con su plazo de pago.

### Ejemplo

Una distribuidora entrega a un cliente 1 polo promocional (valor S/ 100,
gravado) y 3 muestras médicas (S/ 10 cada una, inafectas):

| Ítem | Afectación | Valor referencial | IGV | A cobrar |
|---|---|---|---|---|
| Polo promocional | 11 – retiro por premio | 100,00 | 18,00 (lo asume la empresa) | 0,00 |
| Muestras médicas | 33 – muestras médicas | 30,00 | 0,00 | 0,00 |
| **Total** | | **130,00** | **18,00** | **0,00** |

El comprobante muestra «Op. gratuitas S/ 130,00» y total S/ 0,00. El asiento
carga S/ 18 al gasto y abona S/ 18 a la 40111.

## Validaciones al publicar

| Situación | Regla SUNAT | Qué hacer |
|---|---|---|
| Ítem gratuito con precio 0 | 2641 / 3224 | Escriba el valor referencial como precio unitario |
| Retiro gravado (11-16) sin IGV | 3111 | Use **18% Free Group** |
| Gratuita exonerada o inafecta (21, 31-37) con IGV | 3110 | Use **0% Gratuito exonerado/inafecto** |
| Ítem gratuito que se cobra (por ejemplo, con el **0% Gra** solo) | Totales | Use un grupo gratuito |
| Otra leyenda en una factura con gratuitas | Leyenda 1002 | Deje la leyenda vacía o en 1002 |
| Leyenda 1002 sin ítems gratuitos | 2416 | Odoo la quita sola |

## Casos especiales

| Situación | Qué pasa |
|---|---|
| Factura con ítems pagados y gratuitos | Se cobra lo pagado; el XML informa aparte el total gratuito (con [Anticipos y descuentos](down_payments_discounts.md)) |
| Afectación 37 | Odoo 19 no la trataba como gratuita y SUNAT rechazaba el ítem (3234); el módulo la incluye |
| Nota de crédito de una factura gratuita | Copia los impuestos y la leyenda de la original |
| Boletas del TPV | No cubiertas: se emiten desde el backend |

!!! info "Ver también"
    - [Facturación electrónica](../electronic_invoicing.md)
    - [Comprobante impreso](invoice_report.md)
    - [Registros SIRE](../sire.md) (columna de operaciones gratuitas)

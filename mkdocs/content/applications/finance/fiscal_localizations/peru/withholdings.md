---
modulos: [al_l10n_pe_retention]
---

# Retenciones del IGV

Las empresas que SUNAT designa **agentes de retención del IGV** se quedan con
el **3 % del importe total** de lo que pagan a ciertos proveedores, les
entregan un **comprobante de retención electrónico** (CRE, tipo 20) y declaran
y pagan lo retenido en el **PDT 626**. Cuando la empresa es proveedora de un
cliente agente, recibe pagos netos y registra el importe retenido como crédito
contra su IGV. Este módulo lleva todo al flujo normal de facturas y pagos:
decide si la factura está sujeta, propone el 3 % en cada pago, numera y envía
el CRE, registra las retenciones sufridas y prepara el resumen del 626. Lo usan
Tesorería, Contabilidad y Facturación electrónica.

Quedan fuera la retención en pagos con letras o por compensación, el descuento
de una nota de crédito posterior en la siguiente retención y el Régimen de
Percepciones. La reversión de un CRE aceptado la hace
[OSE Factory HKA](electronic_invoicing/ose_factory_hka.md).

## Conceptos

- **Régimen de Retenciones del IGV** (R.S. 037-2002/SUNAT): quién es agente, a
  qué operaciones se aplica, las excepciones, el momento de la retención (el
  pago) y el comprobante. La **R.S. 061-2005/SUNAT** flexibilizó el régimen
  (operaciones excluidas y monto mínimo) y la **R.S. 033-2014/SUNAT** fijó la
  tasa en 3 %.
- El **comprobante de retención electrónico** se emite en el Sistema de Emisión
  Electrónica (R.S. 274-2015/SUNAT).
- SUNAT designa o excluye agentes por resolución (la más reciente revisada:
  R.S. 000367-2025/SUNAT).
- Se retiene sobre el **importe total con IGV**. La retención no cambia el
  total de la factura: la deuda con el proveedor es el total y la retención se
  practica al pagar.

| Término | Significado | Dónde aparece en Odoo |
|---|---|---|
| Agente de retención | Empresa designada por SUNAT que debe retener | **Perú ‣ Configuración ‣ Ajustes ‣ Retenciones del IGV** |
| Operación sujeta | Factura gravada con IGV por más de S/ 700 a un proveedor no exceptuado | Factura de proveedor, **Sujeta a retención de IGV** |
| Excepciones | Proveedor agente de retención, buen contribuyente o agente de percepción; boletas; operaciones con detracción; sin IGV | Casillas del contacto (padrón SUNAT) y tipo de documento |
| Monto mínimo | No se retiene si los comprobantes pagados juntos suman S/ 700 o menos | Asistente de pago |
| CRE | Comprobante de Retención Electrónico, serie R001 | Pago: número de comprobante y botón **Enviar CRE a SUNAT** |
| Retención sufrida | Lo que un cliente agente retuvo; crédito contra el IGV | **Perú ‣ Retenciones IGV ‣ Retenciones sufridas** |
| PDT 626 | Declaración mensual de las retenciones efectuadas | **Perú ‣ Retenciones IGV ‣ Resumen 626** |

## Configuración

1. Vaya a **Perú ‣ Configuración ‣ Ajustes**, sección **Retenciones del
   IGV**, marque **Agente de retención del IGV** y revise la tasa (3 %) y el
   mínimo (S/ 700).
2. En **Contabilidad ‣ Configuración ‣ Impuestos**, prepare el impuesto de
   compras de -3 % con **Retención en el pago**, la cuenta 40114 «IGV –
   Retenciones por pagar» y la secuencia R001 en **Opciones avanzadas**; luego
   elíjalo en los ajustes.
3. Si el método de pago no tiene cuenta propia, elija la **cuenta transitoria
   (retenciones)** en los ajustes.
4. Para las retenciones sufridas, elija la **cuenta** (40114) y el **diario**
   en el mismo bloque. No hace falta ser agente para usarlas.
5. Las casillas **Agente de retención** y **Buen contribuyente** de los
   contactos las mantiene el padrón SUNAT de la
   [consulta de RUC y DNI](ruc_dni_lookup.md), que se actualiza cada día.
6. Para enviar el CRE, configure el operador y el certificado de la facturación
   electrónica (**Ajustes ‣ Contabilidad ‣ Facturación electrónica
   peruana**).

!!! warning "Importante"
    Si la compañía es agente sin impuesto de retención elegido, la factura no
    se publica («Falta configurar el impuesto de retención»). Una factura
    publicada antes de configurar no propone la retención: pásela a borrador y
    vuelva a publicarla.

## Retener al pagar a un proveedor

1. Registre y publique la factura del proveedor en **Contabilidad ‣
   Proveedores ‣ Facturas**. Si está sujeta, se marca **Sujeta a retención de
   IGV** y sus líneas llevan el impuesto **Retención IGV -3 %**, sin cambiar el
   total.
2. Haga clic en **Pagar**: el asistente propone la retención del 3 % sobre el
   importe pagado y el neto al banco. Varias facturas pequeñas pagadas juntas
   por más de S/ 700 se retienen sobre el total pagado; una factura en dólares
   se compara y retiene en soles al tipo de cambio del pago.
3. Al emitir el pago se asigna el número **R001-########** (grupo
   **Retención** del pago).

![Asistente de pago con la retención del 3 % propuesta](withholdings/register-payment-withholding.png)

### Ejemplo

Factura de un proveedor sin excepciones por un servicio de S/ 5 000 + IGV 18 %
S/ 900 = **S/ 5 900**. La factura no genera aún apunte de retención:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 6311 | Servicios de terceros | 5 000,00 | |
| 40111 | IGV — cuenta propia | 900,00 | |
| 4212 | Facturas por pagar | | 5 900,00 |
| **Totales** | | **5 900,00** | **5 900,00** |

Pago único: retención 5 900 × 3 % = **S/ 177,00**; neto S/ 5 723,00.

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 4212 | Facturas por pagar (proveedor) | 5 900,00 | |
| 1041 | Banco — neto pagado | | 5 723,00 |
| 40114 | IGV — retenciones por pagar (R001-00000001) | | 177,00 |
| **Totales** | | **5 900,00** | **5 900,00** |

Odoo añade dos líneas iguales a la cuenta de gasto (base y contrapartida) que
se anulan entre sí: el marco nativo de retenciones las usa para guardar la base
del cálculo.

Si se paga en dos partes, cada pago retiene el 3 % de su importe:

| Pago | Pagado | Retención | Neto |
|---|---|---|---|
| Primero | 3 000,00 | 90,00 | 2 910,00 |
| Segundo | 2 900,00 | 87,00 | 2 813,00 |
| **Total** | **5 900,00** | **177,00** | **5 723,00** |

Una factura de S/ 650 no retiene: no supera el mínimo. Las notas de crédito no
retienen.

## Enviar el CRE

1. En el pago, haga clic en **Enviar CRE a SUNAT**: se firma el XML y se
   recibe el CDR; el pago pasa a **Enviado**. El CRE impreso (PDF) sale desde el
   pago.
2. Si SUNAT lo rechaza, el error queda en el pago: corríjalo y reenvíe dentro
   del plazo.
3. Revise **Perú ‣ Retenciones IGV ‣ Retenciones efectuadas**: un CRE por pago,
   con el plazo de envío y el estado (amarillo: fuera de plazo; rojo:
   rechazado).

![Pago con el número del CRE y el botón de envío](withholdings/payment-cre.png)

!!! danger "Advertencia"
    El CRE debe enviarse dentro de los 7 días. Si vence el plazo, el pago
    muestra una alerta: evalúe emitir uno nuevo con el asesor tributario.

Cada factura del CRE lleva el número de pago a ese comprobante
(`cac:Payment/cbc:ID`): 1 en el primer pago parcial, 2 en el segundo, y así,
según los CRE anteriores de la misma factura (R.S. 274-2015/SUNAT).

Si el pago se registró por error, anúlelo y el CRE no se envía. Un CRE ya
aceptado necesita la reversión: use la de
[OSE Factory HKA](electronic_invoicing/ose_factory_hka.md) o hágala en el
portal del operador; este módulo solo lo marca **Anulado**.

## Registrar retenciones sufridas

Cuando un cliente agente paga el neto de sus facturas de venta, entrega su
comprobante de retención, que puede cubrir una o varias facturas:

1. Vaya a **Perú ‣ Retenciones IGV ‣ Retenciones sufridas** y haga clic en
   **Nuevo**.
2. Elija el cliente y escriba la **Serie**, el **Número** y la fecha del
   comprobante de retención.
3. En las líneas, agregue cada factura con el **Monto retenido** que indica el
   comprobante (al elegir la factura se propone el 3 % de su total).
4. Haga clic en **Registrar**: se crea un asiento con el IGV retenido por el
   total y un abono a la cuenta por cobrar de cada factura, ya conciliado.

La factura muestra lo retenido en la pestaña **Retenciones sufridas** de
**Facturación PE**.

![Retención sufrida registrada contra la factura de venta](withholdings/withholding-suffered.png)

Por ejemplo, un cliente agente paga una factura de S/ 3 540 y retiene
3 540 × 3 % = **S/ 106,20**:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 40114 | IGV — retenciones sufridas (R777-00000055) | 106,20 | |
| 1212 | Facturas por cobrar (cliente) | | 106,20 |
| **Totales** | | **106,20** | **106,20** |

Para corregir una retención sufrida mal registrada, haga clic en **Pasar a
borrador**: deshace el asiento y la conciliación.

## Reportes

- **Perú ‣ Retenciones IGV ‣ Comprobantes de proveedor**: facturas sujetas,
  con lo pendiente de pago.
- **Retenciones sufridas por factura**: el IGV que le retuvieron sus clientes,
  agrupado por periodo, cliente o comprobante (lista y tabla dinámica). Es el
  importe que se aplica contra el IGV del mes en el formulario 621.
- **Retenciones efectuadas**: un CRE por pago, con el plazo de envío y el
  estado.
- **Análisis de retenciones**: retenido por proveedor y mes.
- **Resumen 626**: TXT del mes con una línea por retención (soporte del
  PDT 626).
- **PLE 8.3**: marca de retención en el campo 26 del Registro de Compras
  Simplificado ([Libros electrónicos (PLE)](ple.md)).

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| Proveedor agente o buen contribuyente | No retiene | Si el padrón está desactualizado, corrija la casilla del contacto |
| El asistente no propone la retención | La factura se publicó antes de configurar | Pásela a borrador y vuelva a publicarla |
| CRE fuera de plazo | Alerta en el pago | Evalúe emitir uno nuevo con el asesor tributario |

!!! info "Ver también"
    - [R.S. 037-2002/SUNAT — Régimen de Retenciones del IGV](https://www.sunat.gob.pe/legislacion/superin/2002/037.htm)
    - [R.S. 061-2005/SUNAT — Flexibilización del régimen](https://www.sunat.gob.pe/legislacion/superin/2005/061.htm)
    - [R.S. 033-2014/SUNAT — Tasa del 3 %](https://www.sunat.gob.pe/legislacion/superin/2014/033-2014.pdf)
    - [R.S. 274-2015/SUNAT — Comprobante de retención electrónico](https://www.sunat.gob.pe/legislacion/superin/2015/274-2015.pdf)
    - [R.S. 000367-2025/SUNAT — Designación de agentes de retención](https://www.sunat.gob.pe/legislacion/superin/2025/000367-2025.pdf)
    - [SUNAT: régimen de retenciones](https://orientacion.sunat.gob.pe/07-regimen-de-retenciones-informacion-general)
    - [Consulta de RUC y DNI](ruc_dni_lookup.md)

# Análisis: retenciones del IGV en new-inveragro (Odoo 16) frente a la suite

Fecha: 11/10/2026. Alcance: régimen de retenciones del IGV (no retenciones
judiciales de planilla). Fuente v16: `/home/och/odoo/ce16/new/new-inveragro`
(`dv_l10n_pe_account_retentions`, `dv_l10n_pe_edi_retention`,
`dv_l10n_pe_sunat_0621_document_retention_txt`,
`dv_l10n_pe_sunat_connection_retention_agent`, `inveragro_pagos`,
`l10n_pe_edi_pse_factura`, `dv_account_letter`). Suite: `al_l10n_pe_retention`
v9, `l10n_pe_vat_sunat`, `al_ose_factory_hka`, `al_l10n_pe_ple`,
`al_l10n_pe_sire`, `al_l10n_pe_factoring`, `al_l10n_pe_invoice`.

## 1. Proceso en v16

**Lado agente (nosotros retenemos al pagar a un proveedor), `inveragro_pagos`:**

1. La compañía es agente (`l10n_pe_is_retention_agent`). En el pago a
   proveedores (formulario propio con líneas de facturas) se marca **Aplicar
   retención** y se elige una **serie de retención** (diario de ventas marcado
   `is_retention`, con su régimen del catálogo 23: 01 = 3 %, 02 = 6 %).
2. Una factura entra si es `in_invoice`, el proveedor no es agente y la
   factura **no tiene importes exonerados, inafectos ni detracción**.
3. Mínimo: si la suma a retener del pago (`amount_should_reten`) supera
   S/ 700, se retiene `importe pagado × tasa` en cada factura.
4. Al publicar el pago se crea el CRE como **`account.move` de venta tipo de
   documento 20** en la serie elegida: una línea por factura con el importe
   retenido en soles, el T.C. del pago y un correlativo de pago parcial
   (`retention_pay_count`). La cuenta es la **401141 buscada por código**.
   El CRE se concilia con el pago.
5. XML propio (`pe_ubl_retention`, UBL 2.0) firmado con el certificado de la
   compañía y enviado con `sendBill` usando las mismas credenciales y WSDL que
   las facturas.
6. Existe además una **retención manual** (`account.retention.manual`) que
   emite el CRE sin un pago de Odoo, y la «retención múltiple» (varios números
   de CRE en un pago).
7. Al pasar el pago a borrador o cancelarlo, el CRE se pasa a borrador o se
   cancela **sin enviar reversión a SUNAT**.

**Lado proveedor retenido (un cliente agente nos retiene):**

- `dv_l10n_pe_edi_retention`: la factura de venta a un cliente agente (si la
  compañía no es agente y el total supera S/ 700) se marca «sujeta a
  retención» y:
  - envía un cargo/descuento con código 62 en el XML;
  - descuenta la retención de la primera cuota (modifica
    **temporalmente el plazo de pago compartido** para partir la deuda);
  - muestra una tabla en el PDF.
- `l10n_pe_edi_pse_factura` (PSE Conflux): otra vía, con el tipo 3 % o 6 % en
  el contacto.
- `dv_l10n_pe_sunat_0621_document_retention_txt`: la retención recibida se
  registra como **pago del cliente** con el número del CRE en la referencia y
  la factura de origen. De ahí sale el **TXT del PDT 621**
  (`0621{RUC}{AAAAMM}R.txt`, 10 campos separados por `|`: RUC del agente,
  serie y número del CRE, fecha, monto, tipo, serie y número del comprobante,
  fecha y total).

**Padrón:** `dv_l10n_pe_sunat_connection_retention_agent` descarga
`AgenRet_TXT.zip` y guarda la lista de RUC en un parámetro del sistema. Al
crear un contacto lo marca como agente.

**Letras:** `dv_account_letter` solo redirige a la cuenta de retención la
línea por cobrar del CRE (documento 20).

## 2. Tabla comparativa

| Etapa | v16 | Suite | Diferencia | ¿Mejora? |
|---|---|---|---|---|
| Comprobantes comprendidos | `in_invoice` sin exonerado, inafecto ni detracción; proveedor no agente | Proveedor no agente, no buen contribuyente, no agente de percepción; tipos 01/08/12; con IGV; sin SPOT | v16 excluye la factura entera si tiene una línea exonerada y no mira buen contribuyente ni percepción | Ya cubierto mejor |
| Mínimo S/ 700 (art. 3) | Suma de lo que se retendría en el pago | Suma de los totales de los comprobantes pagados juntos (incluye parciales de facturas mayores de S/ 700) | La suite sigue el criterio SUNAT (pago y comprobantes) | Ya cubierto mejor |
| Tasa | Catálogo 23 (3 % / 6 %) por serie | 3 % configurable en la compañía | El 6 % no rige desde el 01/03/2014 | No aplica |
| Moneda extranjera (art. 7) | T.C. del pago (`tipo_cambio`) | T.C. venta oficial de la fecha del pago | Equivalente | Ya cubierto |
| Asiento | CRE como factura de venta y cuenta 401141 buscada por código | Impuesto nativo `is_withholding_tax_on_payment` en el pago; cuenta del impuesto | v16 depende del código de cuenta | Ya cubierto mejor |
| Numeración del CRE | Diario de serie `R…` | Secuencia `R001-…` con el xmlid oficial de Odoo 20 | — | Ya cubierto |
| N.º de pago parcial (`cac:Payment/cbc:ID`) | Calcula el correlativo pero lo deja **fijo en 1** | Pone la **posición de la factura** dentro del CRE | Ninguno informa el correlativo del pago a ese comprobante | **Media** (mejora 3) |
| XML, firma y envío | UBL 2.0 propio; `sendBill` con el WSDL de facturas; dirección del agente con la calle del proveedor | Modelo `account.edi.xml.ubl_pe_withholding`; IAP, SUNAT (servicio de retenciones), Digiflow o Factory HKA; CDR | v16 tiene errores de contenido y de servicio | Ya cubierto mejor |
| PDF del CRE | Sí | Sí, con el formato común A4 | — | Ya cubierto |
| Reversión o anulación del CRE | Cancela el documento **sin informar a SUNAT** | Resumen de reversiones (RR) solo con Factory HKA | Con IAP, SUNAT directo o Digiflow no hay RR | **Media** (mejora 4) |
| CRE sin pago de Odoo (manual, letras, compensaciones) | Retención manual | Solo desde un pago | Pendiente documentado en la suite | **Media** (mejora 5) |
| Notas de crédito (art. 2) | No las trata | No las trata (pendiente documentado) | Ninguno descuenta la NC de la siguiente retención al mismo proveedor | **Baja** (mejora 6) |
| Factura de venta a cliente agente: neto pendiente y cuotas | Resta la retención de las cuotas (con un truco frágil sobre el plazo de pago) | **Solo resta la detracción** (`al_l10n_pe_invoice`, PDF y XML) | Incumple la R.S. 193-2020 cuando el cliente es agente | **Alta** (mejora 1) |
| Factura de venta: retención en el XML (cargo/descuento código 62) | Sí | No | Código 62 del catálogo 53 sin confirmar en fuente oficial | **Baja**, verificar antes (mejora 7) |
| Retenciones sufridas: registro | Pago del cliente con el n.º de CRE y la factura de origen | `l10n_pe.retention.received`: una factura por registro, asiento 40114 conciliado | La suite no separa serie y número del CRE ni permite un CRE que cubra varias facturas | **Media** (mejora 2) |
| Retenciones sufridas: TXT del PDT 621 | Sí (`0621{RUC}{AAAAMM}R.txt`) | No | Útil para CRE físicos; el formulario virtual 621 precarga los CRE electrónicos | **Media**, verificar antes (mejora 2) |
| Retenciones efectuadas: declaración | — | Resumen TXT para el F.V. 626 | — | Ya cubierto |
| Padrón de agentes | Lista en un parámetro, comparada **por subcadena**; la tarea mensual no la refresca | Padrón en base de datos con sincronización diaria (7212 agentes en el servidor, 11/10/2026) | — | Ya cubierto mejor |
| PLE y SIRE | — | PLE 8.1 y 8.3 (marca y monto); SIRE con la retención en soles | — | Ya cubierto |
| Factoring | — | El neto pendiente estimado ya descuenta la retención | Contradice al comprobante impreso (mejora 1) | Ver mejora 1 |

## 3. Mejoras recomendadas

1. **Alta — Neto pendiente y cuotas de la factura de venta sin la retención.**
   Si el cliente es agente de retención, la compañía no lo es y la operación
   está sujeta (con IGV, sin SPOT y con total o comprobante por encima de
   S/ 700), el «Monto neto pendiente de pago» y las cuotas del XML
   (`cac:PaymentTerms`) y del PDF deben descontar el 3 %. Hacerlo en
   `al_l10n_pe_invoice`, en el mismo cálculo que hoy resta la detracción
   (`_l10n_pe_report_net_pending` y los nodos `FormaPago`), sin modificar el
   plazo de pago (el truco de v16). Reutilizar la regla de
   `al_l10n_pe_factoring` (`_l10n_pe_factoring_net_pending`) para que digan lo
   mismo. Pruebas con un cliente agente, en soles y en dólares.
   *Base:* R.S. 193-2020/SUNAT, numeral 2.1: «El monto neto pendiente de pago
   no incluye las retenciones del IGV, el monto del depósito […] SPOT […] y
   otras deducciones».
   *Esfuerzo:* 1–1,5 días.
2. **Media — Retenciones sufridas con el CRE del agente y, si sigue vigente,
   TXT del PDT 621.** Agregar al registro la serie, el número y la fecha del
   CRE del agente y permitir varias facturas por CRE (líneas). Exportar el TXT
   de 10 campos de v16 por periodo de la retención, no por la fecha de hoy.
   Antes, confirmar si el formulario virtual 621 todavía importa ese archivo o
   si basta la precarga de los CRE electrónicos (útil para CRE físicos).
   *Base:* R.S. 037-2002/SUNAT, art. 8 (comprobante de retención) y el
   formulario 621.
   *Esfuerzo:* 1–2 días.
3. **Media — Correlativo del pago parcial en el CRE.** `cac:Payment/cbc:ID`
   debe ser el número de pago a ese comprobante (1, 2, 3… según los CRE
   anteriores del mismo comprobante), no la posición en el CRE. Calcularlo con
   las líneas de retención publicadas de cada factura.
   *Base:* R.S. 274-2015/SUNAT (CRE electrónico) y la guía del XML de
   retención.
   *Esfuerzo:* 0,5 día.
4. **Media — Reversión del CRE con los demás operadores.** Extender el
   resumen de reversiones (RR) de `al_ose_factory_hka` al envío directo a SUNAT
   y a IAP/Digiflow, y bloquear la cancelación del pago si el CRE fue aceptado
   y no se revirtió.
   *Base:* R.S. 274-2015/SUNAT (reversión del comprobante de retención
   electrónico).
   *Esfuerzo:* 1–2 días.
5. **Media — CRE sin pago de Odoo.** Emitir el CRE desde letras,
   compensaciones o de forma manual, como la retención manual de v16, pero con
   el mismo desglose y XML del pago.
   *Base:* art. 7 (la retención se efectúa en el momento del pago, cualquiera
   que sea su forma).
   *Esfuerzo:* 2 días.
6. **Baja — Nota de crédito posterior.** Proponer el descuento de la nota de
   crédito en la siguiente retención al mismo proveedor.
   *Base:* art. 2 («podrá deducirse de la retención que corresponda a
   operaciones con el mismo proveedor»).
   *Esfuerzo:* 1 día.
7. **Baja — Retención en el XML de la factura de venta (cargo/descuento
   código 62).** Implementarla solo si el Anexo 8 vigente confirma el código y
   un OSE lo valida; la mejora 1 ya cumple la R.S. 193-2020.
   *Esfuerzo:* 0,5 día tras confirmar.

## 4. Lo que v16 hace mal (no copiar)

- `dv_l10n_pe_account_retentions`: `account_move.py`,
  `account_move_line.py` y `withholding_tax_table.py` no se importan (código
  muerto), y usan `company.withholding_journal_id`, que no existe.
- La cuenta de retención se busca por código `401141`, sin compañía.
- El plazo de pago compartido se reescribe y se restaura al publicar cada
  factura: es concurrente y frágil; además se crean plazos temporales
  archivados.
- `_compute_withholding_amount` escribe con `write()` dentro de un cómputo.
- La comparación con S/ 700 usa `amount_total_signed`, con signo.
- En el XML del CRE:
  - el número de pago va fijo en 1;
  - la calle y la ciudad del agente se toman del proveedor;
  - se envía por el servicio de facturas;
  - queda un `print(edi_str)`.
- Cancelar el pago cancela el CRE sin resumen de reversión.
- TXT del 621:
  - toma el periodo de hoy;
  - escribe el archivo en el directorio de trabajo del servidor;
  - pone importes sin dos decimales;
  - a `account_move.py` le falta `import re`.
- Padrón:
  - guarda la lista de RUC como texto y la compara por subcadena;
  - la tarea se ejecuta sobre un conjunto de contactos vacío y nunca vuelve a
    descargar la lista;
  - se marca al contacto al crearlo con una descarga síncrona.
- Tasa del 6 % (catálogo 23, código 02): no rige desde el 01/03/2014.

## 5. Fuentes

- [R.S. 037-2002/SUNAT, régimen de retenciones del IGV (texto vigente)](https://www.sunat.gob.pe/legislacion/superin/2002/037.htm):
  - art. 3, excepción de S/ 700;
  - art. 5, operaciones excluidas;
  - art. 7, momento y tipo de cambio;
  - art. 2, notas de crédito;
  - art. 8, comprobante de retención.
- [SUNAT, Preguntas frecuentes del régimen de retenciones](https://orientacion.sunat.gob.pe/node/1060): retención por cada pago parcial.
- [SUNAT, Sistema de retenciones (charla 2024)](https://charlas.sunat.gob.pe/sites/default/files/2024-06/SISTEMA%20DE%20RETENCIONES%202024x.pdf): condiciones conjuntas del mínimo y tasa del 3 % desde el 01/03/2014 (R.S. 033-2014/SUNAT).
- [R.S. 193-2020/SUNAT](https://www.sunat.gob.pe/legislacion/superin/2020/193-2020.pdf): forma de pago y neto pendiente (numeral 2.1).
- [R.S. 274-2015/SUNAT](https://www.sunat.gob.pe/legislacion/superin/2015/274-2015.pdf): emisión electrónica del comprobante de retención (PDF escaneado: el texto no se pudo leer).

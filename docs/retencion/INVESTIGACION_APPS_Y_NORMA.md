# Régimen de Retenciones del IGV: norma vigente y apps de Odoo

Investigación hecha el 07/10/2026 para contrastar el módulo `al_l10n_pe_retention`
(OL-ACCOUNTING, Odoo 19).

**Leyenda de fiabilidad**

- **[OFICIAL]**: texto leído directamente en sunat.gob.pe, orientacion.sunat.gob.pe o en el PDF
  firmado de la resolución.
- **[SECUNDARIA]**: fuente privada (estudio contable, blog, captura de terceros).
- **[NO VERIFICADO]**: inferencia propia o dato que no se pudo confirmar en una fuente oficial.

---

## 1. Apps similares en apps.odoo.com (v17, v18 y v19)

### 1.1 Método

Se hicieron búsquedas paginadas en `apps.odoo.com/apps/modules/browse?search=…&series=…`
para 17.0, 18.0 y 19.0 (y, para comparar, 14.0 a 16.0). Términos usados: `retencion`, `retenciones`,
`retención`, `retencion igv`, `retencion de igv`, `retenciones igv`, `comprobante de retencion`,
`certificado retencion`, `agente de retencion`, `retention`, `withholding`, `withholding peru`,
`retention igv`, `peru retention`, `l10n_pe_retention`, `l10n_pe_withholding`, `peru`, `peruvian`, `sunat`,
`igv`, `l10n_pe`, `spot`, `percepcion`, `detraccion`, y nombres de proveedores (`ganemo`, `pokutsoft`,
`operu`, `big consulting`, `develogers`). Después se descargó la ficha de los 90 módulos candidatos
(peruanos o de retención) y se buscaron en su descripción las palabras retención, withholding,
percepción, 626 y CRE.

### 1.2 Conclusión principal

**No hay en la tienda (v17, v18 ni v19) ningún módulo dedicado al régimen de retenciones del IGV
desde el lado del agente de retención**, es decir, uno que calcule la retención en el pago, emita
el CRE tipo 20 y prepare el 626. Lo que existe son:

1. Conectores de facturación electrónica que **enumeran** el tipo 20 (CRE) entre los documentos que
   soportan, sin describir la lógica del régimen (Pokutsoft y OPeru).
2. Un pack contable (Designweblp) que dice cubrir retenciones y percepciones emitidas y sufridas,
   aunque sin mencionar el CRE electrónico.
3. Módulos de Ganemo que solo traen catálogos o campos (SIRE, menú) relacionados con la retención.
4. Módulos genéricos de *withholding on payment* que no son de Perú.
5. **Odoo nativo (v18.4+ y v19)** cubre únicamente el lado del **proveedor**: el impuesto de venta
   `sale_tax_withholding_3` "3% Retención IGV" (-3 %, grupo `tax_group_igv_withholding`) para facturar
   a un cliente que es agente de retención. Una respuesta de Odoo en su foro lo deja claro: *"Esta
   funcionalidad no está relacionada al comprobante de retención a proveedores … Únicamente a la
   emisión de facturas a clientes con retención"*
   ([foro Odoo](https://www.odoo.com/forum/help-1/l10n-pe-retenciones-en-factura-de-cliente-289082)).
   El marco genérico `l10n_account_withholding_tax` (retención en el pago) sí existe en CE 19
   (`addons/l10n_account_withholding_tax`), pero no trae nada propio de Perú (CRE, mínimo de 700, excepciones).

### 1.3 Fichas

Los precios son los que mostraba la tienda el 07/10/2026 (en EUR). "Funcionalidades" resume
**solo lo que dice la descripción pública**: lo que no aparece se marca "no dice".

| # | Nombre técnico | Autor | Versiones | Precio | Lo que declara sobre retenciones |
|---|---|---|---|---|---|
| A | `l10n_pe_sunat_cpe_einvoice` ([v19](https://apps.odoo.com/apps/modules/19.0/l10n_pe_sunat_cpe_einvoice), [v18](https://apps.odoo.com/apps/modules/18.0/l10n_pe_sunat_cpe_einvoice)) | Pokutsoft | 18.0, 19.0 | 134,47 € | Entre los documentos que genera lista "Comprobante de Retencion (20) and Percepcion (40)". Envío SOAP a SEE-Del contribuyente u OSE, CDR, PDF con QR y resumen diario (RC). No describe cálculo, mínimo, excepciones, reversión ni 626. |
| B | `l10n_pe_edi_odoofact` ([v19](https://apps.odoo.com/apps/modules/19.0/l10n_pe_edi_odoofact)) | OPeru | 13.0 a 19.0 | Gratis (descarga) | "Comprobantes de Retención (20) y Percepción (40)", a través de **Nubefact** (PSE/OSE, cuenta obligatoria). PDF con QR. No describe la lógica del régimen. |
| C | `l10n_pe_accounting_pro` ([v18](https://apps.odoo.com/apps/modules/18.0/l10n_pe_accounting_pro)) | Designweblp | 18.0 | 172,48 € | "Retenciones y Percepciones de IGV: para Agentes de Retención (retiene 3 % al pagar a proveedores) y de Percepción (…) en ambas direcciones — emitidas y sufridas — con comprobantes numerados y asientos conciliados". No menciona CRE electrónico, envío, 626, mínimo de 700 ni excepciones. Depende de `pe_edi_sunat` (86,24 €, mismo autor), cuya ficha no menciona retenciones. |
| D | `l10n_pe_localization_menu` ([v19](https://apps.odoo.com/apps/modules/19.0/l10n_pe_localization_menu)) | Ganemo | 19.0 | 17,25 € | Solo un catálogo `account.spot.retention` ("SPOT Retentions") con CRUD en un menú. Sin lógica. |
| E | `l10n_pe_edocument` ([v19](https://apps.odoo.com/apps/modules/19.0/l10n_pe_edocument)) | Ganemo | 19.0 | 480,46 € | Facturación electrónica centrada en detracciones. Sus escenarios de prueba mencionan un cliente "Retention Agent" y una factura de más de 700 PEN con detracción ("potentially calculate Retention"). No dice emitir CRE. |
| F | `l10n_pe_sire_sunat` ([v19](https://apps.odoo.com/apps/modules/19.0/l10n_pe_sire_sunat)) | Ganemo | 19.0 | 689,21 € | Formato SIRE con campos `igv_withholding_indicator`, `retention_rate`, `tax_withheld` e `inv_retention_igv` en `account.move`. Solo informa, no gestiona el régimen. |
| G | `sunatfm_pe_edi` ([v19](https://apps.odoo.com/apps/modules/19.0/sunatfm_pe_edi)) | Freddy M. | 19.0 | 75,87 € (LGPL-3) | "Detracciones, retenciones, códigos QR y datos de pago" en la facturación electrónica. Por el contexto parece la retención en la factura de venta (lado proveedor) **[NO VERIFICADO]**. |
| H | `dvl_l10n_pe_account` ([v18](https://apps.odoo.com/apps/modules/18.0/dvl_l10n_pe_account)) | Develogers | 16.0, 17.0, 18.0 | 2.568,07 € (v18) | Pack de contabilidad peruana (27.892 líneas). La ficha no tiene texto funcional (solo imágenes y enlaces); que cubra retenciones queda **[NO VERIFICADO]**. |
| I | `withholding_on_payment` ([v17](https://apps.odoo.com/apps/modules/17.0/withholding_on_payment)) | Yunus Abdulaziz | 17.0 | 84,29 € | Genérico, no peruano: "Withholding Amount = Payment × Rate" al registrar el pago a proveedor. Sin comprobante ni mínimo. |
| J | Odoo nativo `l10n_pe` + `l10n_pe_edi` (EE) | Odoo S.A. | 18.4+, 19.0 | incluido | Lado proveedor: impuesto de venta -3 % "Retención IGV" en la factura al cliente agente y bloque de retención en el XML de la factura. **No** emite CRE. |

Otros resultados descartados por ser de otros países: `l10n_ec_*`, `l10n_ar_retenciones_gb`,
`l10n_do_withholding_certification`, `account_purchase_retentions` (Guatemala), `account_move_withholding` (Túnez),
`ke_withholding_vat_*` (Kenia), `es_certificado_retenciones` (España), entre otros. En 14.0 a 16.0
tampoco apareció un módulo peruano específico (solo los `dvl_l10n_pe_*` y el genérico `tax_withholdings`).

**No encontrados en la tienda:** Ganemo no publica un módulo de CRE; tampoco hay módulos de BIG
Consulting ni de "Odoo Perú" con retenciones en v17-v19. Pueden existir fuera de la tienda (repos
privados o de partners), pero eso queda **[NO VERIFICADO]**.

### 1.4 Tabla comparativa de funcionalidades

Leyenda: ✔ lo declara · ~ lo sugiere o lo hace en parte · ✗ no lo declara · ? la ficha no permite saberlo.

| Funcionalidad | A Pokutsoft | B OPeru | C Designweblp | E/F Ganemo | G FreddyM | H Develogers | J Nativo | **al_l10n_pe_retention** (según su manifest y README) |
|---|---|---|---|---|---|---|---|---|
| Retención calculada en el pago | ✗ | ✗ | ✔ (3 % al pagar) | ✗ | ? | ? | ✗ (en la factura, lado proveedor) | ✔ |
| CRE electrónico tipo 20 (XML UBL 2.0 firmado) | ✔ (lo lista) | ✔ (vía Nubefact) | ✗ | ✗ | ? | ? | ✗ | ✔ (`account_payment.py` arma el XML) |
| Envío a SUNAT / OSE y CDR | ✔ | ✔ (Nubefact) | ✗ | ✗ | ? | ? | ✗ | ✔ (servicio de retenciones y percepciones) |
| PDF del CRE | ✔ (genérico) | ✔ | ? | ✗ | ? | ? | ✗ | ✔ (`reports/retention_report.xml`) |
| Resumen diario de reversiones / reversión | ✗ | ✗ | ✗ | ✗ | ✗ | ? | ✗ | ? (a revisar) |
| Retenciones sufridas (lado proveedor) | ✗ | ✗ | ✔ | ~ (campo SIRE) | ~ | ? | ✔ (impuesto -3 %) | ✔ (`retention_received.py`) |
| PDT 626 / F.V. 626 | ✗ | ✗ | ✗ | ✗ | ✗ | ? | ✗ | ~ (resumen mensual "soporte del F.V. 626") |
| Registro del Régimen de Retenciones | ✗ | ✗ | ~ (comprobantes numerados) | ✗ | ✗ | ? | ✗ | ? |
| Reportes | ✗ | ✗ | ✔ | ~ | ✔ | ? | ✗ | ✔ |
| Tasa 3 % configurable | ? | ? | ✔ | ✗ | ? | ? | ✔ (impuesto) | ✔ (Ajustes) |
| Mínimo de S/ 700 | ✗ | ✗ | ✗ | ~ (escenario de prueba) | ✗ | ? | ✗ | ✔ |
| Excepciones (buen contribuyente, agente, SPOT, boletas) | ✗ | ✗ | ✗ | ✗ | ✗ | ? | ✗ | ✔ (parcial, ver §3) |
| Multimoneda (T.C. venta SBS a la fecha de pago) | ? | ? | ? | ~ (escenario de detracción en USD) | ? | ? | ✗ | ~ (pone `cac:ExchangeRate` con la fecha del pago; falta revisar el tipo de T.C.) |
| Pago parcial | ✗ | ✗ | ? | ✗ | ✗ | ? | ✗ | ? |

**Lectura:** el mercado no ofrece un equivalente completo. La única competencia funcional
declarada es C (Designweblp, v18, sin CRE electrónico); A y B solo resuelven el transporte del XML.

---

## 2. Norma vigente

### 2.1 Base legal

| Norma | Contenido | Fuente |
|---|---|---|
| R.S. 037-2002/SUNAT (19/04/2002) y modificatorias (050-2002, 135-2002, 126-2004, 263-2004, 061-2005…) | Régimen de Retenciones del IGV | [OFICIAL] [texto concordado](https://www.sunat.gob.pe/legislacion/superin/2002/037.htm) · [lista de normas](https://orientacion.sunat.gob.pe/03-normas-legales-regimen-de-retenciones) |
| R.S. 033-2014/SUNAT (01/02/2014) | Sustituye el art. 6: tasa **3 %** | [OFICIAL] [PDF](https://www.sunat.gob.pe/legislacion/superin/2014/033-2014.pdf) |
| R.S. 274-2015/SUNAT | Emisión electrónica del CRE y del CPE; reversión; añade el Título IV a la R.S. 097-2012 (SEE-Del contribuyente) | [OFICIAL] [PDF](https://www.sunat.gob.pe/legislacion/superin/2015/274-2015.pdf) |
| R.S. 285-2015/SUNAT | Formularios virtuales opcionales para declarar retenciones y percepciones en SUNAT Virtual (desde 01/01/2016) | [SECUNDARIA] [resumen SNI](https://sni.org.pe/aprueban-formularios-virtuales-para-la-declaracion-y-pago-de-las-retenciones-y-percepciones-del-igv-a-traves-de-sunat-virtual/) |
| R.S. 117-2017/SUNAT | SEE-OSE: permite emitir el CRE vía OSE; Anexo 15 del CRE actualizado (Anexo XIII) | [OFICIAL] [PDF](https://www.sunat.gob.pe/legislacion/superin/2017/117-2017.pdf) · [Anexo 15 CRE](https://www.sunat.gob.pe/legislacion/superin/2017/anexoXIII-117-2017.pdf) |
| R.S. 193-2020/SUNAT | Factura al crédito: el "monto neto pendiente de pago" **no incluye** las retenciones del IGV (lado proveedor) | [OFICIAL] [PDF](https://www.sunat.gob.pe/legislacion/superin/2020/193-2020.pdf) |
| R.S. 000367-2025/SUNAT | Última actualización del padrón de agentes (designa y excluye), vigente desde el **01/02/2026** | [OFICIAL] [PDF](https://www.sunat.gob.pe/legislacion/superin/2025/000367-2025.pdf) |

En 2026 no hay cambios al régimen de retenciones del IGV propiamente dicho. La R.S. 000047-2026/SUNAT
regula el IGV **retenido en liquidaciones de compra**, que es un mecanismo distinto y excluido de
este régimen (art. 2 de la R.S. 037-2002), y lo declara en el 617
([PDF](https://www.sunat.gob.pe/legislacion/superin/2026/000047-2026.pdf)).

### 2.2 Tasa

- **3 %** del importe de la operación, por la R.S. 033-2014 vigente desde el 01/03/2014. Se aplica a
  operaciones **cuyo nacimiento de la obligación tributaria del IGV se produjo desde esa fecha**; antes
  regía el 6 % [OFICIAL] ([033-2014](https://www.sunat.gob.pe/legislacion/superin/2014/033-2014.pdf),
  [orientación 7.3](https://orientacion.sunat.gob.pe/73-importe-de-la-operacion-y-tasa-de-retencion)).
- No se encontró ninguna resolución posterior que cambie la tasa (búsqueda hasta 10/2026). El
  texto concordado del art. 6 en sunat.gob.pe todavía muestra el 6 % porque no está actualizado; manda el PDF de la 033-2014.
- El código del régimen en el CRE (catálogo 23) es "01" y en la representación impresa se lee "TASA 3%"
  [OFICIAL] (Anexo 15, campo 9).

### 2.3 Base: importe de la operación

- "Importe de la operación" es la **suma total que el adquirente queda obligado a pagar, con los tributos
  incluidos (IGV incluido)**. La base es el precio de venta, no el valor de venta [OFICIAL] (art. 1 e;
  [FAQ 17](https://orientacion.sunat.gob.pe/06-preguntas-frecuentes-regimen-de-retenciones)).
- El recargo al consumo forma parte del importe (Informe 209-2008) [OFICIAL]
  ([consultas](https://orientacion.sunat.gob.pe/01-consultas-sunat-regimen-de-retenciones)).
- **Pagos parciales:** la tasa se aplica **sobre el importe de cada pago** [OFICIAL] (art. 7).
- El ejemplo oficial en dólares (antigua FAQ de SUNAT) muestra que "el pago" es la **parte del comprobante
  que se cancela, retención incluida**. Una factura de US$ 11.800 se cancela con un pago parcial
  de US$ 5.000: la retención es 6 % × (5.000 × 3,455) = S/ 1.036,50 y el cheque es S/ 16.238,50 = 17.275 − 1.036,50.
  Luego el saldo de US$ 6.800 × 3,50 da una retención de S/ 1.428 y un cheque de S/ 22.372
  [OFICIAL] ([FAQ antigua](https://www.sunat.gob.pe/orientacion/regimenEspIGV/agentesRetencion/faqAgentesRetencion.htm)).
  En la práctica: retención = 3 % × importe del comprobante que se cancela (bruto) y desembolso = 97 %.
- En el CRE, el campo 20 es el "importe de pago en moneda original, **no incluye la retención**", el campo 22
  la retención en PEN y el campo 23 el neto pagado en PEN deducida la retención. El total pagado
  (campo 11) es la suma de los campos 23 [OFICIAL] (Anexo 15).
- En el F.V. 626, la base imponible (casilla 502) es el importe pagado sin la retención más la retención
  [OFICIAL] ([ayuda F.V. 626](https://www.sunat.gob.pe/operacLinea/ayudas/Ayuda_FV_626_Agente_retencion.pdf)).

### 2.4 Monto mínimo de S/ 700

- **Art. 3:** "Se exceptúa de la obligación de retener cuando el pago efectuado es igual o inferior a
  S/ 700,00 **y** el monto de los comprobantes involucrados no supera dicho importe" [OFICIAL].
  - Es decir, **se retiene si se cumple cualquiera de las dos condiciones**: (1) el pago supera 700, o
    (2) el comprobante, o la **suma de los comprobantes involucrados** en ese pago, supera 700
    (Informe 267-2002) [OFICIAL] ([informe](https://www.sunat.gob.pe/legislacion/oficios/2002/oficios/i2672002.htm)).
  - El "monto de los comprobantes" se toma **ajustado por las notas de crédito y débito** que correspondan
    (FAQ 9) [OFICIAL].
  - **Los pagos anteriores al mismo proveedor en el período no cuentan** para la excepción (Informe 267-2002) [OFICIAL].
  - **Solo se suman los comprobantes que entran en el régimen.** Si con un mismo pago se cancela una
    operación incluida y otra que no lo está, la excepción se evalúa solo con la incluida
    (Informe 260-2002) [OFICIAL] ([informe](https://www.sunat.gob.pe/legislacion/oficios/2002/oficios/i2602002.htm)).
  - Varios comprobantes de menos de 700 cada uno que, sumados, superan 700 en un mismo pago **se retienen**.
    Según la FAQ antigua, también se retiene cuando una **misma operación** de más de 700 se documentó
    en varios comprobantes menores aunque se paguen por separado (ejemplo 3: tres facturas de S/ 600 por una
    venta de S/ 1.800; "sí se retiene en cada pago") [OFICIAL]. Este último caso exige que el usuario
    vincule los comprobantes: no se deduce de los datos de forma automática **[NO VERIFICADO cómo
    automatizarlo]**.
- La comparación se hace en **soles**. Que una operación en moneda extranjera se convierta para la
  comparación con el mismo T.C. del cálculo (venta SBS a la fecha de pago) es una inferencia **[NO VERIFICADO]**.

### 2.5 Oportunidad de la retención

- **En el momento del pago, total o parcial**, sea cual sea la fecha de la operación (art. 7) [OFICIAL].
- Qué cuenta como pago (art. 1 f y FAQ 3-6) [OFICIAL]:
  - efectivo: la entrega o puesta a disposición;
  - cheque a la vista: la puesta a disposición (Informe 267-2002);
  - **cheque diferido**: la fecha desde la que puede cobrarse (Informe 372-2002);
  - **canje por letra de cambio**: el **vencimiento o el cobro, lo que ocurra primero**; si la letra se renueva,
    el vencimiento de la última (Informe 372-2002, [texto](https://www.sunat.gob.pe/legislacion/oficios/2002/oficios/i3722002.htm));
  - **compensación de acreencias**: la fecha en que se compensa;
  - pago en especie: la entrega o puesta a disposición de los bienes.
- Si se paga a un tercero, igual hay que emitir y entregar el CRE al proveedor (art. 7) [OFICIAL].
- Retiro de bienes (sin pago): no se retiene (FAQ 16) [OFICIAL].
- Los pagos con **tarjeta de crédito** o el **factoring** no tienen una regla específica en el
  régimen de retenciones del IGV; la exclusión por tarjeta que suele citarse es del régimen de **percepciones**
  **[NO VERIFICADO]**.

### 2.6 Moneda extranjera

- Se convierte a soles con el **tipo de cambio promedio ponderado venta publicado por la SBS en la fecha
  de pago**. Los días sin publicación se usa **el último publicado** [OFICIAL] (art. 7, tercer párrafo; orientación 7.3; FAQ 8).
- Duda práctica: la SBS publica cada día el T.C. de cierre del día hábil anterior, y la tabla de SUNAT lo
  muestra con la fecha de publicación. Lo normal es tomar el T.C. venta que SUNAT o SBS muestran **para la fecha
  del pago** **[NO VERIFICADO el desfase exacto; conviene alinearlo con `al_l10n_pe_currency`]**.

### 2.7 Operaciones excluidas o fuera del régimen

Art. 2 y art. 5 de la R.S. 037-2002 (sustituido por la 061-2005) [OFICIAL]
([orientación 7.2](https://orientacion.sunat.gob.pe/72-aplicacion-del-regimen-y-operaciones-excluidas)):

| # | Supuesto | Base |
|---|---|---|
| 1 | Operaciones **exoneradas o inafectas** (solo entran las gravadas) | art. 2 |
| 2 | Proveedor **buen contribuyente** (D.Leg. 912), verificado **al pagar**. Si lo excluyen, se le retiene desde el 1.er día del mes siguiente a la notificación | art. 5 a) |
| 3 | Proveedor **agente de retención**, verificado al pagar | art. 5 b) |
| 4 | Documentos del num. 6.1 del art. 4 del RCP (luz, agua, boletos de aviación, documentos de bancos, etc.) | art. 5 c) |
| 5 | **Boletas, tickets o cintas sin derecho a crédito fiscal** | art. 5 d) |
| 6 | Operaciones sin obligación de emitir comprobante (art. 7 RCP) | art. 5 e) |
| 7 | Operaciones con **detracción (SPOT)** | art. 5 f); FAQ 15 |
| 8 | Unidades ejecutoras del sector público que pagan por encargo a un tercero | art. 5 g) |
| 9 | Proveedor **agente de percepción** del IGV, verificado al pagar | art. 5 h); Informe 33-2014 |
| 10 | **Liquidaciones de compra** y pólizas de adjudicación | art. 2 |
| 11 | Pago ≤ 700 y comprobantes ≤ 700 | art. 3 |
| 12 | Operaciones de antes del 01/06/2002 (Informe 267-2002); bienes de la Ley 27400 (Informe 201-2003) | consultas |

- **Recibos por honorarios:** no llevan IGV (renta de 4.ª categoría), así que no hay operación gravada.
  Los servicios profesionales entran solo si son de 3.ª categoría, es decir, con factura (Informe 285-2003) [OFICIAL].
  El CRE solo admite como documento relacionado los tipos **01, 07, 08, 12 y 20** (Anexo 15, campo 13) [OFICIAL]:
  ni boleta (03), ni recibo por honorarios (02), ni liquidación de compra (04).
- El ticket (12) sí cabe cuando da derecho a crédito fiscal [OFICIAL] (FAQ antigua, nota a; Anexo 15).
- El proveedor sujeto a retención no puede mezclar operaciones gravadas y no gravadas en un mismo comprobante
  ([orientación 7.6](https://orientacion.sunat.gob.pe/76-comprobante-de-pago-y-notas-de-credito-y-debito)) [OFICIAL].

### 2.8 Notas de crédito y de débito

- **Nota de débito** [OFICIAL] (art. 2; orientación 7.6; FAQ 10):
  - emitida **antes** del pago: se retiene sobre el total de la operación (comprobante + ND) si supera 700;
  - emitida **después** del pago: se retiene **solo sobre la ND**, aunque el comprobante original no se haya
    retenido por no pasar de 700, siempre que el total supere 700;
  - si el total sigue ≤ 700, no se retiene.
- **Nota de crédito** [OFICIAL] (art. 2; FAQ 11-12):
  - emitida **antes** del pago: reduce el importe de la operación (750 − 60 = 690, así que no se retiene);
  - emitida **después** de retener: **no** cambia ni devuelve lo retenido, pero esa retención puede
    **deducirse de retenciones futuras al mismo proveedor** (ejemplo: S/ 102 retenidos sobre una factura
    anulada se descuentan de la retención de la siguiente factura).
- En el CRE, una NC (07) se informa solo si disminuye el importe total de un comprobante relacionado, y sin
  datos de pago ni de retención (Anexo 15, campo 13) [OFICIAL].

### 2.9 Comprobante de retención electrónico (CRE, tipo 20)

- **Obligatorio en electrónico.** La R.S. 274-2015 designó emisores electrónicos a todos los agentes de
  retención (y a los que se designen después, desde que adquieren esa calidad). La orientación SUNAT indica
  "a partir del 01/01/2018 su emisión es obligatoriamente electrónica"
  ([orientación 7.5](https://orientacion.sunat.gob.pe/75-comprobante-de-retencion)) [OFICIAL]. El impreso
  queda solo para contingencias, con resumen diario (num. 4.6 del art. 4 de la R.S. 300-2014) [OFICIAL].
- **Sistemas de emisión:** SEE-SOL (serie **E001**), SEE-Del contribuyente (serie **R###**, numeración desde 1
  e independiente de la impresa) y **SEE-OSE** (art. 3.2 de la R.S. 117-2017) [OFICIAL].
- **Cuándo se emite:** "al momento de efectuar la retención", o sea en la fecha de pago (art. 3 de la R.S. 274-2015;
  art. 8 de la R.S. 037-2002; Informe 267-2002). Hay dos salvedades [OFICIAL]:
  - **un solo CRE por proveedor** para las retenciones de un período, si hay acuerdo y se emite y entrega
    **dentro del mismo mes** de las retenciones, indicando la fecha de cada una (art. 8 num. 5);
  - un CRE que **reemplaza a otro revertido**.
  
  Solo en estos dos casos la fecha de pago puede diferir de la fecha de emisión (art. 21 num. 1.3, versión SEE-SOL).
- **Entrega:** en SEE-Del contribuyente, cuando el CRE se pone a disposición del proveedor por el medio
  electrónico que el emisor elija (art. 4 de la R.S. 274-2015). El emisor debe ofrecer al proveedor una
  consulta web autenticada durante **un año** (art. 38.3 de la R.S. 097-2012) [OFICIAL].
- **Plazo de envío a SUNAT u OSE: hasta 7 días calendario** contados desde el día siguiente a la fecha de emisión.
  Lo enviado después **no tiene la calidad de CRE**, aunque se haya entregado al proveedor
  (art. 41 de la R.S. 097-2012, incorporado por la R.S. 274-2015; art. 36 de la R.S. 117-2017 para OSE) [OFICIAL].
  No se encontró una reducción posterior como la que hubo para facturas (3 días), aunque la búsqueda no fue exhaustiva **[NO VERIFICADO]**.
- **CDR:** aceptada o rechazada (art. 42 de la R.S. 097-2012) [OFICIAL].
- **Contenido mínimo** (Anexo 15, versión de la R.S. 117-2017) [OFICIAL]:
  - fecha de emisión y firma digital;
  - emisor: razón social, nombre comercial (opcional) y RUC;
  - serie y número (R###, hasta 8 dígitos);
  - proveedor: tipo de documento 6 (RUC) y razón social;
  - código del régimen (cat. 23, "01") y tasa (3,00);
  - importe total pagado (suma de los netos) y total retenido, **siempre en PEN**;
  - **por cada comprobante relacionado**: tipo (01/07/08/12/20), serie y número, fecha de emisión, moneda e importe
    total en moneda original, **fecha de pago**, **número de pago** (correlativo por comprobante para los pagos
    parciales; 1 si es pago único; no se repite), importe pagado en moneda original **sin la retención**, moneda
    del pago (la misma del comprobante), **retención en PEN** y **neto pagado en PEN**, y moneda de referencia del T.C.
  - El detalle del bloque de tipo de cambio (factor y fecha) está en la guía XML de SUNAT, no en el anexo
    leído **[NO VERIFICADO aquí]**.
- **Reversión** (art. 7 de la R.S. 274-2015) [OFICIAL]:
  - procede incluso si el CRE ya se entregó, en tres supuestos: (a) se emitió a un sujeto distinto del
    proveedor; (b) la operación no está en el régimen o está excluida; (c) hubo errores en los datos;
  - en SEE-Del contribuyente u OSE: se comunica al proveedor y se envía el **resumen diario de reversiones**
    **hasta 7 días calendario** después del día siguiente a esa comunicación. Cada resumen cubre un solo día
    y el último enviado para un día sustituye al anterior (art. 43 de la R.S. 097-2012; art. 38 de la R.S. 117-2017);
  - efecto: el CRE queda inhabilitado y **su número no puede reutilizarse**. El CRE de reemplazo cita el revertido como tipo 20.

### 2.10 Declaración del agente: PDT 626 y Formulario Virtual 626

- El agente declara y paga el total de retenciones del período en el **PDT Agentes de Retención, F.V. 626**,
  **aunque no haya retenido nada**, según el cronograma mensual. No puede compensarlo con el saldo a favor del
  exportador (art. 9) [OFICIAL].
- **Desde el período 01/2016** existe el **Formulario Virtual 626 en SUNAT Virtual**, que la R.S. 285-2015
  aprobó como opcional (el PDT 626 sigue siendo alternativa) [SECUNDARIA]. Según la ayuda oficial [OFICIAL]
  ([PDF](https://www.sunat.gob.pe/operacLinea/ayudas/Ayuda_FV_626_Agente_retencion.pdf)):
  - **no se registra el detalle**: el formulario **calcula solo** la base (casilla 502) y la retención (casilla 401)
    con los **CRE ya informados al SEE** y los resúmenes de impresos;
  - si un monto no cuadra, se corrige el CRE (reversión y reemplazo) y se vuelve a cargar;
  - las casillas son 402 (pagos previos), 403 (por pagar), 404 (interés), 405 (total) y 410 (importe a pagar).
  
  **Consecuencia para el módulo:** lo que declara SUNAT sale de los CRE aceptados, así que lo importante es que
  esos CRE sean correctos; un resumen interno sirve para conciliar.
- **Formato TXT de importación del PDT 626** (el aplicativo descargable; vigencia para períodos recientes
  **[NO VERIFICADO]**) [SECUNDARIA: captura de la ayuda del propio PDT publicada por
  [sunatin.pe](https://sunatin.pe/pdt-0626-importar-retenciones-estructuras/)]:
  - nombre del archivo: `0626` + RUC del agente + período `AAAAMM` + `.TXT` (ejemplo para el RUC 20100000092
    y el período 201406: `062620100000092201406.TXT`);
  - separador `|`, una línea por comprobante de pago:

  | # | Campo | Formato |
  |---|---|---|
  | 1 | RUC del proveedor | 11 |
  | 2 | Razón social (persona jurídica) | hasta 40 |
  | 3 | Apellido paterno (persona natural) | hasta 20 |
  | 4 | Apellido materno | hasta 20 |
  | 5 | Nombres | hasta 20 |
  | 6 | Serie del comprobante de retención | hasta 4 |
  | 7 | Número del comprobante de retención | hasta 8 |
  | 8 | Fecha de emisión del CR | dd/mm/aaaa |
  | 9 | Monto de pago del CR | 12 enteros, 2 decimales, sin comas |
  | 10 | Tipo de comprobante de pago | 01 factura, 07 NC, 08 ND, 12 ticket, 99 otros |
  | 11 | Serie del comprobante de pago | hasta 4 |
  | 12 | Número del comprobante de pago | hasta 8 (hasta 15 si es 99) |
  | 13 | Fecha de emisión del CP | dd/mm/aaaa |
  | 14 | Valor total del comprobante de pago | 12 enteros, 2 decimales |

  Ejemplo de la ayuda: `20111111112|EL PROVEEDOR S.A ||||0004|23400980|11/05/2014|200000|01|0001 |52334455|11/05/2014|199300.79|`

### 2.11 Registro del Régimen de Retenciones

- El art. 13 a) **exigía** al agente una cuenta "IGV – Retenciones por pagar" y un **Registro del Régimen de
  Retenciones** por proveedor, con fecha, documento, tipo de transacción (compra, ajuste, pago, compensación,
  canje por letras…), debe/haber y saldo. Se puede llevar consolidado por mes y proveedor, con un atraso
  máximo de 10 días hábiles y legalizado [OFICIAL].
- **Con el CRE desaparece esa obligación:** "Con la utilización del CRE se elimina la obligación de llevar el
  Registro de Régimen de Retenciones" ([orientación 7.5](https://orientacion.sunat.gob.pe/75-comprobante-de-retencion))
  [OFICIAL, aunque no se localizó el artículo exacto que lo dispone **[NO VERIFICADO]**].
- **No forma parte del PLE.** El "Libro de Retenciones" del PLE (formato 4) es el de los incisos e) y f) del art. 34
  de la LIR (rentas de 4.ª categoría), no el del IGV **[NO VERIFICADO contra la tabla PLE vigente]**.
- La columna del Registro de Compras que marca los comprobantes sujetos a retención es **opcional** ("podrá",
  art. 12 modificado por la 050-2002) [OFICIAL].

### 2.12 Proveedor que sufre la retención

- Está **obligado a aceptarla** (art. 2) y abre la subcuenta **"IGV Retenido"** dentro de la cuenta del IGV
  (art. 13 b) [OFICIAL]. En el PCGE de Odoo se usa la **40114** "IGV – Régimen de retenciones"; que esa
  subcuenta concreta sea la del proveedor es práctica contable **[NO VERIFICADO como exigencia]**.
- **Deduce** del IGV a pagar las retenciones recibidas **hasta el último día del período** que declara (PDT 621);
  el exceso se arrastra y no se compensa con otras deudas (art. 11) [OFICIAL]. Puede aplicarlas en ese período o en
  uno posterior (Informe 017-2003) y aplicar solo una parte (Informe 78-2011) [OFICIAL].
- Puede pedir la **devolución** si mantuvo un saldo sin aplicar durante **3 períodos consecutivos**
  (R.S. 061-2005) [OFICIAL].
- En su factura electrónica al crédito, el **monto neto pendiente de pago excluye la retención**
  (R.S. 193-2020) [OFICIAL]. En Odoo nativo esto se resuelve con el impuesto -3 % de venta.

---

## 3. Comprobaciones que debería cumplir un módulo correcto

Ordenadas por prioridad: P1 son errores de cálculo o legales; P2, cumplimiento formal; P3, conveniencia.
"Segura" significa que hay fuente oficial; "dudosa", que no está confirmado.

| P | Comprobación | Fiabilidad | Fuente |
|---|---|---|---|
| P1 | Solo retiene si **la compañía es agente de retención en la fecha de pago**; respeta el inicio y la exclusión según la resolución de designación (p. ej. 367-2025, desde 01/02/2026). | Segura | art. 4; R.S. 367-2025 |
| P1 | **Tasa 3 %** sobre el **importe con IGV** (precio de venta), no sobre la base imponible. | Segura | arts. 1 e y 6; R.S. 033-2014 |
| P1 | La retención se genera **en el pago, no en la factura**; si el pago es parcial, sobre **cada pago**. | Segura | art. 7 |
| P1 | Base del pago = **parte del comprobante que se cancela, retención incluida**: retención = 3 % × importe cancelado y desembolso = 97 %. En el CRE, "importe pagado" va **sin** la retención y el neto en PEN **deducida** la retención. | Segura | FAQ antigua (ejemplo en US$); Anexo 15, campos 20-23 |
| P1 | **Mínimo de 700:** se exceptúa solo si **el pago ≤ 700 y además** la suma de los comprobantes involucrados (ajustada por NC y ND) ≤ 700. Basta que una de las dos supere 700 para retener. | Segura | art. 3; Informe 267-2002; FAQ 9 |
| P1 | Para el mínimo **se suman todos los comprobantes del mismo pago** que entran en el régimen y **se excluyen** los que no entran (exonerados, boletas, SPOT, etc.). Los pagos anteriores del período no cuentan. | Segura | Informes 260-2002 y 267-2002 |
| P1 | Un comprobante de más de 700 pagado en partes menores **se retiene en cada parte**. | Segura | FAQ 7, ejemplos 1-2 |
| P1 | **Moneda extranjera:** convertir al **T.C. promedio ponderado venta SBS** de la **fecha de pago** (si no hay, el último publicado). **No** usar el T.C. de la factura, de compra ni el contable del pago si este es distinto. | Segura (la regla) / dudosa (el desfase de la fecha de publicación) | art. 7; orientación 7.3 |
| P1 | Excepciones verificadas **en la fecha de pago**: buen contribuyente, agente de retención y **agente de percepción** del proveedor (padrones SUNAT). Un proveedor excluido de buenos contribuyentes se retiene desde el 1.er día del mes siguiente a la notificación. | Segura | art. 5 a, b, h |
| P1 | No retener: operaciones **exoneradas o inafectas**, con **detracción (SPOT)**, **boletas o tickets sin crédito fiscal**, documentos del num. 6.1 del art. 4 del RCP (luz, agua, aviación, bancos), **liquidaciones de compra**, **recibos por honorarios** y operaciones sin obligación de comprobante. | Segura | arts. 2 y 5; Informe 285-2003 |
| P1 | **Nota de crédito** antes del pago: reduce la base y el mínimo. Después de retener: **no** se devuelve, pero se puede descontar de la siguiente retención al **mismo proveedor**. | Segura | art. 2; FAQ 11-12 |
| P1 | **Nota de débito** después del pago: se retiene sobre la ND aunque el original (≤ 700) no se retuviera, si el total supera 700. | Segura | art. 2; orientación 7.6 |
| P1 | **Canje por letra:** no se retiene al canjear, sino al **vencer o cobrar la letra**, lo que ocurra primero; si se renueva, en la última. Ojo con la integración con `al_l10n_pe_account_letter`. | Segura | Informe 372-2002; FAQ 5-6 |
| P1 | **Compensación** de acreencias (cruzar la factura del proveedor con una del cliente) = pago en la fecha de compensación, así que hay retención y CRE. | Segura | art. 1 f |
| P1 | Cheque diferido: la fecha de pago es la de cobro posible; cheque a la vista: la puesta a disposición. | Segura | Informes 267 y 372-2002 |
| P2 | **CRE tipo 20 en la fecha de pago**, salvo el CRE mensual consolidado por proveedor (emitido dentro del mismo mes y con la fecha de cada retención) o el de reemplazo de un revertido. | Segura | art. 8 num. 5; R.S. 274-2015 arts. 3-4 |
| P2 | Serie **R###** (SEE-Del contribuyente u OSE), correlativo desde 1 sin reutilizar números revertidos; régimen "01" y tasa 3,00; importes totales en **PEN**; documentos relacionados solo 01/07/08/12/20; **número de pago** correlativo por comprobante. | Segura | Anexo 15 (R.S. 117-2017) |
| P2 | **Envío a SUNAT u OSE en 7 días calendario** desde el día siguiente a la emisión; fuera de plazo deja de ser CRE. Conviene alertar o bloquear. | Segura | art. 41 de la R.S. 097-2012; art. 36 de la R.S. 117-2017 |
| P2 | **Reversión** solo por los tres motivos (sujeto distinto, operación fuera del régimen o excluida, error de datos) y **resumen diario de reversiones** en 7 días, uno por día. La reversión **no** se resuelve anulando el pago en silencio. | Segura | art. 7 de la R.S. 274-2015; art. 43 de la R.S. 097-2012 |
| P2 | Contabilidad del agente: pasivo **"IGV – Retenciones por pagar"** que se cancela con el pago a SUNAT. La cuenta concreta del PCGE (40114 o subcuenta) es práctica. | Segura (que exista la cuenta) / dudosa (el código) | art. 13 a |
| P2 | Resumen mensual que **cuadre con los CRE aceptados**, porque el F.V. 626 toma base = pagado sin retención + retenido, y retenido = suma de CRE. Debe incluir los períodos sin retenciones (el 626 se presenta igual). | Segura | art. 9; ayuda F.V. 626 |
| P2 | Lado proveedor: registrar la retención sufrida (CRE recibido) en "IGV Retenido" y aplicarla hasta el último día del período. Factura al crédito con neto pendiente sin la retención. | Segura | arts. 10, 11 y 13 b; R.S. 193-2020 |
| P2 | Operaciones de **antes del 01/03/2014** al 6 % (irrelevante en la práctica). | Segura | R.S. 033-2014 |
| P3 | Exportar el **TXT del PDT 626** (`0626RUCAAAAMM.txt`, separador `|`, 14 campos) para quien siga usando el PDT. | Dudosa (fuente secundaria; vigencia del PDT no confirmada) | §2.10 |
| P3 | Registro del Régimen de Retenciones: no es obligatorio con CRE; ofrecerlo solo como reporte por proveedor. | Segura (orientación) / dudosa (artículo exacto) | orientación 7.5 |
| P3 | Operación "partida" en varios comprobantes de menos de 700 pagados por separado: permitir marcarlos como **una sola operación** para retener. | Segura (criterio) / dudosa (cómo detectarlo) | FAQ antigua, ejemplo 3 |
| P3 | Pagos con tarjeta o factoring: no hay exclusión expresa, así que tratarlos como pago. | Dudosa | sin fuente oficial |

### 3.1 Indicios rápidos sobre `al_l10n_pe_retention` (sin auditar)

Solo para orientar la revisión; salen de un `grep` sobre `models/` y `wizards/`, no de pruebas:

- El README y el manifest cubren el mínimo de 700, agente-agente, buen contribuyente, boletas y SPOT. **No aparece
  la exclusión por agente de percepción** (art. 5 h), ni las de exonerado o inafecto, el num. 6.1 del RCP ni la
  liquidación de compra. Revisar `models/account_move.py`.
- El XML del CRE pone `cac:ExchangeRate` con `cbc:Date = fecha del pago`: correcto. Falta confirmar que la tasa
  usada sea la **venta** SBS y no la tasa contable de la compañía.
- No se encontraron referencias a **reversión** ni a **resumen diario de reversiones**, ni al tratamiento de
  **letras** o **compensaciones** como momento de pago.
- Ya existe un asistente de resumen mensual ("soporte del F.V. 626").

---

## 4. Fuentes consultadas

**Oficiales (SUNAT)**

- R.S. 037-2002 concordada: https://www.sunat.gob.pe/legislacion/superin/2002/037.htm
- R.S. 033-2014: https://www.sunat.gob.pe/legislacion/superin/2014/033-2014.pdf
- R.S. 274-2015: https://www.sunat.gob.pe/legislacion/superin/2015/274-2015.pdf
- R.S. 117-2017 y su Anexo XIII (Anexo 15 CRE): https://www.sunat.gob.pe/legislacion/superin/2017/117-2017.pdf ·
  https://www.sunat.gob.pe/legislacion/superin/2017/anexoXIII-117-2017.pdf
- R.S. 193-2020: https://www.sunat.gob.pe/legislacion/superin/2020/193-2020.pdf
- R.S. 000367-2025: https://www.sunat.gob.pe/legislacion/superin/2025/000367-2025.pdf
- R.S. 000047-2026: https://www.sunat.gob.pe/legislacion/superin/2026/000047-2026.pdf
- Orientación SUNAT: [7.1](https://orientacion.sunat.gob.pe/71-regimen-de-retenciones-del-igv),
  [7.2](https://orientacion.sunat.gob.pe/72-aplicacion-del-regimen-y-operaciones-excluidas),
  [7.3](https://orientacion.sunat.gob.pe/73-importe-de-la-operacion-y-tasa-de-retencion),
  [7.5](https://orientacion.sunat.gob.pe/75-comprobante-de-retencion),
  [7.6](https://orientacion.sunat.gob.pe/76-comprobante-de-pago-y-notas-de-credito-y-debito),
  [FAQ](https://orientacion.sunat.gob.pe/06-preguntas-frecuentes-regimen-de-retenciones),
  [Informes](https://orientacion.sunat.gob.pe/01-consultas-sunat-regimen-de-retenciones),
  [Normas](https://orientacion.sunat.gob.pe/03-normas-legales-regimen-de-retenciones)
- FAQ antigua con casos prácticos: https://www.sunat.gob.pe/orientacion/regimenEspIGV/agentesRetencion/faqAgentesRetencion.htm
- Informes 260-2002, 267-2002 y 372-2002:
  https://www.sunat.gob.pe/legislacion/oficios/2002/oficios/i2602002.htm ·
  https://www.sunat.gob.pe/legislacion/oficios/2002/oficios/i2672002.htm ·
  https://www.sunat.gob.pe/legislacion/oficios/2002/oficios/i3722002.htm
- Ayuda del F.V. 626: https://www.sunat.gob.pe/operacLinea/ayudas/Ayuda_FV_626_Agente_retencion.pdf

**Secundarias**

- R.S. 285-2015 (resumen): https://sni.org.pe/aprueban-formularios-virtuales-para-la-declaracion-y-pago-de-las-retenciones-y-percepciones-del-igv-a-traves-de-sunat-virtual/
- Estructura del TXT del PDT 626 (captura de la ayuda del PDT): https://sunatin.pe/pdt-0626-importar-retenciones-estructuras/
- Foro de Odoo, retención en la factura nativa: https://www.odoo.com/forum/help-1/l10n-pe-retenciones-en-factura-de-cliente-289082
- Fichas de apps.odoo.com citadas en §1.3.

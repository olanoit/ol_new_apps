# Letras de cambio en Perú: requisitos para un módulo de Odoo 19

Investigación del 07/10/2026. Cubre el marco legal, el tributario, el contable (PCGE), la práctica bancaria
y los módulos de Odoo Apps, y termina con una lista de verificación para auditar un módulo de letras.

## Convenciones

- **[V]**: verificado en la fuente oficial citada. La copia local está en `docs/letras/oficial/` y se indica
  el archivo.
- **[no verificado]**: dato de práctica de mercado, doctrina, memoria o fuente no oficial. Hay que
  contrastarlo antes de usarlo como regla del módulo.
- **[inferencia]**: conclusión propia a partir de normas verificadas. No es criterio publicado por la
  autoridad.

### Fuentes oficiales descargadas (`docs/letras/oficial/`)

| Archivo | Norma | Origen |
|---|---|---|
| `Ley_27287_Titulos_Valores_ElPeruano_2000.pdf` | Ley 27287, Ley de Títulos Valores (LTV), *El Peruano* 19/06/2000, **texto original** | leyes.congreso.gob.pe |
| `PCGE_2019.pdf` / `.txt` | Plan Contable General Empresarial 2019 | cdn.www.gob.pe (MEF) |
| `Resolucion_CNC002_2019EF30.pdf` / `.txt` | Res. CNC 002-2019-EF/30: aprueba el PCGE 2019, obligatorio desde el 01/01/2020 y deroga el PCGE 2010 | mef.gob.pe |
| `SUNAT_TUO_ITF_DS150-2007-EF.pdf` / `.txt` | TUO de la Ley 28194 (medios de pago e ITF), D.S. 150-2007-EF, texto concordado por SUNAT | sunat.gob.pe |
| `Ley_28194_ITF_texto_original_2004.pdf` | Ley 28194, texto original | leyes.congreso.gob.pe |
| `Ley_29623_factura_negociable_texto_original.pdf` | Ley 29623, factura negociable, texto original (escaneado, sin capa de texto) | leyes.congreso.gob.pe |
| `SBS_Res_4358-2015_Reglamento_Factoring_Descuento.pdf` / `.txt` | Res. SBS 4358-2015, Reglamento de Factoring, Descuento y Empresas de Factoring | busquedas.elperuano.pe |
| `SUNAT_RCP_capituloI.pdf` / `.txt` | Reglamento de Comprobantes de Pago (RCP), cap. I (art. 2) | sunat.gob.pe |
| `SUNAT_RCP_capituloIII.pdf` / `.txt` | RCP, cap. III (art. 10: notas de crédito y de débito) | sunat.gob.pe |
| `SUNAT_PLE_Anexo3_Tablas_RS169-2015.pdf` / `.txt` | Anexo 3 del PLE (tablas 1, 10, etc.), R.S. 169-2015/SUNAT | sunat.gob.pe |
| `SUNAT_Informe_372-2002_retencion_letras.txt` | Informe 372-2002-SUNAT/K00000 | sunat.gob.pe |
| `SUNAT_Informe_112-2003_retencion_letras_descuento.txt` | Informe 112-2003-SUNAT/2B0000 | sunat.gob.pe |
| `SUNAT_Informe_153-2005_ITF_descuento_letras.txt` | Informe 153-2005-SUNAT/2B0000 | sunat.gob.pe |
| `SUNAT_Informe_103-2007_intereses_compensatorios_IGV.txt` | Informe 103-2007-SUNAT/2B0000 | sunat.gob.pe |
| `SUNAT_Informe_334-2003_nota_debito_recupero.txt` | Informe 334-2003-SUNAT/2B0000 | sunat.gob.pe |
| `SUNAT_FAQ_agentes_retencion.txt` | Preguntas frecuentes de SUNAT sobre agentes de retención (preguntas 11 y 15 a 17) | sunat.gob.pe |

Notas sobre las fuentes:

- El PDF de la Ley 27287 usa fuentes sin mapa Unicode, así que `pdftotext` devuelve texto ilegible. Los
  artículos citados aquí se leyeron sobre la imagen renderizada de cada página (págs. 188150 a 188166 de
  *El Peruano*).
- Ese texto es el **original del 2000**. La ley tiene modificaciones posteriores; entre ellas, una ley que
  modificó el art. 10 y el D. Leg. 1492 (2020) **[no verificado]**. Antes de cerrar requisitos hay que
  contrastar los artículos citados con el texto consolidado del SPIJ (spij.minjus.gob.pe), que no fue
  posible descargar.
- La estructura oficial del PLE (`docs/ple/oficial/Estructura del PLE.xls`, publicada por SUNAT) ya estaba en el
  repositorio. Se usa en el §2.7.

---

## 1. Marco legal: Ley de Títulos Valores N.° 27287

### 1.1 Reglas generales aplicables a la letra

| Tema | Regla | Cita |
|---|---|---|
| Título valor | Los valores materializados con los requisitos formales esenciales de su clase son títulos valores. Si falta un requisito esencial, el documento no es título valor, pero queda a salvo el acto causal. | Art. 1.1 y 1.2 [V] |
| Letra desmaterializada | Los valores desmaterializados requieren anotación en cuenta y registro ante una Institución de Compensación y Liquidación de Valores (ICLV; en la práctica, CAVALI). | Art. 2.1 [V] |
| Literalidad | El texto del documento determina los derechos. | Art. 4.1 [V] |
| Importe | Si el importe escrito en letras y el escrito en números no coinciden, **prevalece la suma menor**. Sin unidad monetaria se entiende moneda nacional. | Art. 5.2 y 5.3 [V] |
| Firmas | Se admiten medios gráficos, mecánicos o electrónicos de seguridad. Si hay acuerdo previo, la firma autógrafa puede sustituirse por una firma impresa o digitalizada. Todo firmante debe consignar su nombre y su documento oficial de identidad; si firma por una persona jurídica, también el nombre del representante. | Art. 6.1, 6.2 y 6.4 [V] |
| Título emitido incompleto | Debe completarse conforme a los acuerdos antes de presentarse a cobro. | Art. 10 [V, texto original; la ley lo modificó después] |
| Solidaridad | Los que emiten, giran, aceptan, endosan o garantizan quedan obligados solidariamente frente al tenedor. | Art. 11.1 [V] |
| Devolución | El tenedor que cobra devuelve el título. Si el último tenedor es un banco, puede sustituirlo por microformas. | Art. 17.1 y 17.3 [V] |
| Mérito ejecutivo | Los títulos valores tienen mérito ejecutivo si reúnen los requisitos formales. | Art. 18.1 [V] |

### 1.2 Requisitos formales de la letra (arts. 119 y 120)

Según el art. 119.1 **[V]**, la letra de cambio debe contener:

| Inc. | Requisito | Campo del módulo |
|---|---|---|
| a | La denominación «Letra de Cambio» | Título fijo del formato |
| b | Lugar y fecha de giro | Ciudad y fecha de emisión |
| c | Orden incondicional de pagar una cantidad determinada de dinero, o determinable conforme a sistemas de actualización o reajuste de capital legalmente admitidos | Moneda e importe, en números y en letras |
| d | Nombre y número del documento oficial de identidad de la persona a cuyo cargo se gira (girado o aceptante) | Cliente con RUC o DNI |
| e | Nombre de la persona a quien o a la orden de quien debe hacerse el pago | Beneficiario (normalmente la empresa) |
| f | Nombre, número del documento oficial de identidad y firma de quien gira la letra | Girador con RUC y firma |
| g | Indicación del vencimiento | Fecha de vencimiento |
| h | Lugar de pago y, en los casos del art. 53, la forma de pago | Lugar o cuenta bancaria de pago |

- Art. 119.2 **[V]**: estos requisitos pueden constar en el orden, lugar, forma, modo o recuadros que
  determine libremente el girador o los obligados. **No hay formato oficial obligatorio** **[inferencia]**.
- Art. 120 **[V]** suple algunos datos que faltan:
  - sin lugar de giro, se toma el domicilio del girador;
  - sin lugar de pago, se toma el lugar junto al nombre del girado o, en su defecto, su domicilio real;
  - con varios lugares de pago, el tenedor elige;
  - si hay cargo en cuenta (art. 53), no hace falta lugar de pago;
  - una letra girada a la orden del propio girador puede usar la cláusula «de mí mismo».
- Art. 122 **[V]**: la letra puede girarse a la orden del propio girador o de un tercero, a cargo de un
  tercero, a cargo del propio girador (que entonces vuelve a firmar como aceptante) o por cuenta de un
  tercero.
- Art. 123 **[V]**: el girador responde de la aceptación y del pago. Toda cláusula que lo libere se tiene por
  no puesta.

### 1.3 Vencimiento

- Art. 121.1 **[V]**: la letra solo puede girarse a fecha fija, a la vista, a cierto plazo desde la
  aceptación o a cierto plazo desde su giro.
- Art. 121.2 **[V]**: una letra con otro tipo de vencimiento **o con vencimientos sucesivos** no produce
  efectos cambiarios.
  → **Requisito del módulo [inferencia]**: un canje en cuotas debe generar **una letra por cuota**, cada una
  con un único vencimiento. Una letra con calendario de cuotas no es válida.
- Art. 121.3 **[V]**: si se indican dos formas de vencimiento y una es fecha fija, prevalece la fecha fija.
- Art. 121.5 **[V]**: sin vencimiento, la letra es pagadera a la vista.
- Art. 143 **[V]**: la letra a fecha fija vence el día señalado.
- Art. 144.2 **[V]**: «medio mes» equivale a 15 días.
- Art. 144.4 **[V]**: en el cómputo de días no se excluyen los inhábiles. Pero si el vencimiento cae en un día
  inhábil, la aceptación o el pago se trasladan al primer día hábil siguiente, mientras que el plazo de
  protesto se cuenta desde el vencimiento que figura en el documento.
- Arts. 141 y 142 **[V]**:
  - la letra a la vista vence el día de su presentación, que debe hacerse dentro de un año desde el giro
    salvo otro plazo (art. 141.5);
  - la letra a cierto plazo desde la aceptación cuenta el plazo desde la fecha de aceptación o del protesto.

### 1.4 Aceptación

- Art. 127.1 **[V]**: con la aceptación, el girado se obliga a pagar al vencimiento y pasa a ser el
  **obligado principal**.
- Art. 128.1 **[V]**: la aceptación debe constar en el **anverso** con la cláusula «aceptada» y la firma del
  girado; la sola firma ya vale como aceptación.
  → El formato impreso necesita un recuadro «ACEPTADA» con fecha, nombre, documento de identidad y firma.
- Art. 128.2 **[V]**: en las letras a cierto plazo desde la aceptación, esta debe estar fechada.
- Art. 129 **[V]**: la aceptación es pura y simple. Puede limitarse a una parte del importe, y entonces cabe
  el protesto por el resto. Cualquier otra modificación equivale a negativa.
- Art. 134.1 **[V]**: la letra a cierto plazo desde la aceptación debe presentarse a aceptación dentro del año
  desde el giro.
- Art. 136 **[V]**: el girado debe aceptar o rechazar al presentársele la letra. Toda demora faculta al
  tenedor a protestarla.
- Art. 139 **[V]**: la **reaceptación** renueva la obligación con el mismo monto, plazo y lugar de pago, salvo
  pacto distinto. Consta en el anverso o en una hoja adherida y libera a los firmantes anteriores que no
  vuelvan a intervenir.
- Art. 140 **[V]**: la reaceptación solo procede antes de que prescriba la acción cambiaria directa, siempre
  que la letra no se haya protestado.
- Art. 147 **[V]**: protesto por falta de aceptación.
  - Si la falta de aceptación es total, ya no hace falta presentar la letra al pago ni protestarla por falta
    de pago (147.2).
  - La cláusula «sin protesto» **no** rige para el protesto por falta de aceptación (147.4 y 81.3).

### 1.5 Endoso, cobranza y garantía

- Art. 125 **[V]**:
  - toda letra es transmisible por endoso aunque no diga «a la orden»;
  - el endoso puede hacerse a favor del girado, del girador o de otro obligado.
- Art. 126 **[V]**: salvo cláusula en contrario, el endosante responde de la aceptación y del pago.
- Art. 41 **[V]**: el **endoso en procuración** (o «al cobro») no transfiere la propiedad; el endosatario
  representa al endosante. Es la base jurídica de la **cobranza bancaria** **[inferencia]**.
- Art. 42 **[V]**: el **endoso en garantía** («en garantía», «en prenda») da al endosatario todos los derechos
  de acreedor garantizado. Es la base de la **cobranza en garantía** **[inferencia]**.
- Art. 43 **[V]**: la cláusula «no negociable» o «intransferible» limita la transmisión a la cesión de
  derechos.
- Art. 44 **[V]**: el endoso posterior al vencimiento, pero anterior al protesto o a su plazo, produce los
  efectos de un endoso normal.
- **Descuento**: la letra se transfiere en propiedad al banco descontante.
  - Res. SBS 4358-2015, art. 11 **[V]**: «El descuento es la operación mediante la cual el Descontante
    entrega una suma de dinero a una persona denominada Cliente, por la transferencia de determinados
    instrumentos de contenido crediticio. El Descontante asume el riesgo crediticio del Cliente, y este a su
    vez el riesgo crediticio del Deudor de los instrumentos transferidos.»
  - Es decir, el descuento es **con recurso** contra el cliente. En el factoring, en cambio, el factor asume
    el riesgo del deudor (art. 2 **[V]**).

### 1.6 Pago, moneda e intereses

- Art. 53 **[V]**: puede pactarse el pago con cargo en una cuenta de una empresa del sistema financiero,
  indicando el banco y, en su caso, el número o código de cuenta.
- Art. 64 **[V]**: el tenedor no está obligado a recibir el pago antes del vencimiento. Quien paga antes lo
  hace por su cuenta y riesgo.
- Art. 65.1 **[V]**: **el tenedor no puede rehusar un pago parcial**, y el pago parcial debe anotarse en el
  título (65.2).
  → El módulo debe admitir cobros parciales de una letra.
- Art. 50 **[V]**: puede pactarse el pago efectivo en moneda extranjera. Sin esa cláusula rige el art. 68.
- Art. 68.1 **[V]**: el título en moneda extranjera puede pagarse en esa moneda o en moneda nacional al
  **tipo de cambio venta** publicado el día del vencimiento o, en su defecto, el último publicado.
- Art. 68.2 **[V]**: si se paga después del vencimiento, el tenedor elige entre el tipo de cambio del día de
  pago y el del vencimiento.
- **Art. 146 [V]**: «En la Letra de Cambio no procede acordar intereses para el período anterior al de su
  vencimiento. Sólo a falta de pago y a partir del día siguiente a su vencimiento, generará los intereses
  compensatorios y moratorios que se hubieren acordado conforme al Artículo 51º o, en su defecto, el interés
  legal».
  → **Requisito del módulo [inferencia]**: el interés de financiamiento hasta el vencimiento **no puede ser
  una cláusula de la letra**; debe ir dentro de su importe nominal. Las tasas compensatoria y moratoria del
  formato solo rigen desde el día siguiente al vencimiento.
- Art. 51.1 **[V]**: pueden pactarse tasas de interés compensatorio y moratorio, reajustes y comisiones para
  el periodo de mora. Si no se pactan, rige el interés legal.

### 1.7 Prórroga, renovación y refinanciación

- **Cláusula de prórroga** (art. 49 **[V]**):
  - el vencimiento puede prorrogarse, incluso después de vencido, si el obligado lo consintió en el mismo
    título, la acción no se extinguió y el título no fue protestado (49.1);
  - la prórroga surte efecto con la sola anotación del nuevo vencimiento firmada por el tenedor (49.2);
  - la prescripción se reinicia desde cada nuevo vencimiento (49.3);
  - el obligado puede revocar la cláusula por carta notarial (49.5);
  - solo puede prorrogarse por el mismo importe o uno menor, más reajustes, intereses y comisiones, y el
    tenedor debe comunicar el nuevo vencimiento a los obligados (49.6).
- **Renovación**: según el glosario del art. 279, inc. 11, de la LTV, citado por SUNAT, es «la ampliación del
  plazo de vencimiento de un título valor, en mérito a nueva y expresa intervención del obligado u obligados
  que asumirán desde entonces las obligaciones respectivas, quedando liberados de toda obligación quienes no
  intervengan en la renovación».
  - Fuente: Informe SUNAT 372-2002 **[V, a través de SUNAT]**. El art. 279 no se leyó en la imagen de *El
    Peruano*.
  - En la práctica, la renovación se instrumenta así: la letra original se anula o se devuelve, el deudor
    amortiza una parte y se gira una letra nueva por el saldo más intereses y gastos **[no verificado]**.
- **Prescripción en prórrogas y renovaciones** (art. 97 **[V]**): el plazo corre desde el último
  vencimiento. En las renovaciones acordadas en el título, corre desde el nuevo vencimiento, pero respecto de
  quienes no intervinieron en la renovación la prescripción tiene efecto desde la fecha de renovación.
- **Refinanciación** (canjear una o varias letras por un nuevo grupo de letras): no tiene una figura propia en
  la LTV **[inferencia]**. Se trata como una renovación múltiple, y el módulo debe enlazar las letras
  originales con las nuevas.

### 1.8 Protesto

- Arts. 70 y 71 **[V]**:
  - en los títulos sujetos a protesto, el incumplimiento se acredita con el protesto o con su formalidad
    sustitutoria, y es requisito para las acciones cambiarias (70.2);
  - el protesto contra el obligado principal (aceptante) es facultativo frente a los obligados solidarios
    (71.4).
- **Plazos** (art. 72.1 **[V]**):
  - falta de aceptación: dentro del plazo de presentación y hasta 8 días después;
  - falta de pago de una letra **a la vista**: hasta 8 días después del vencimiento del plazo de presentación
    (inc. c);
  - demás títulos sujetos a protesto, como la **letra a fecha fija**: **dentro de los 15 días siguientes** a
    la fecha en que debió cumplirse la obligación (inc. e) **[inferencia sobre qué inciso aplica]**;
  - en los casos b) y e), el título se entrega al fedatario (notario o juez de paz) dentro de los
    **primeros 8 días** de esos 15 (72.2).
- Art. 73.1 **[V]**: el protesto se hace en el lugar designado para el pago.
- Art. 80 **[V]**: los gastos de protesto son de cargo del obligado principal, salvo en los títulos con
  cláusula «sin protesto».
- **Cláusula «sin protesto»** (art. 52 y art. 81 **[V]**):
  - libera al tenedor de protestar; la acción cambiaria se ejerce por el solo mérito del vencimiento
    (81.1);
  - el tenedor puede igual protestar, pero a su costo (81.2);
  - no rige para el protesto por falta de aceptación (81.3).
  → El formato debe ofrecer la cláusula «sin protesto»; es la práctica habitual de los bancos **[no
  verificado]**.
- Art. 82 **[V]**: si la letra se paga con cargo en cuenta (art. 53), la constancia que deja el banco de la
  falta de pago **sustituye al protesto**.
- **Publicidad** (arts. 85 y 89 **[V]**):
  - los fedatarios informan los protestos a la Cámara de Comercio provincial, que los remite a la Cámara de
    Comercio de Lima para el **Registro Nacional de Protestos y Moras**;
  - el registro dura 5 años, o 3 si el título se pagó;
  - quien paga un título protestado puede pedir la **«regularización de protesto»** (89.1).
- Art. 87 **[V]**: en los títulos no sujetos a protesto, el incumplimiento puede comunicarse a la Cámara de
  Comercio, y esa comunicación es necesaria para ciertas acciones.

### 1.9 Acciones cambiarias, extinción de la factura y prescripción

- Art. 90 **[V]**:
  - **acción directa** contra el aceptante y sus garantes;
  - **acción de regreso** contra el girador, los endosantes y sus garantes;
  - **acción de ulterior regreso** de quien pagó en vía de regreso.
- Art. 92.1 **[V]**: el tenedor puede reclamar:
  - el importe;
  - los intereses compensatorios y moratorios pactados o, si no se pactaron, el interés legal;
  - los **gastos de protesto** y de la cobranza frustrada.
- Art. 94.3 **[V]**: «Subsiste la acción causal correspondiente a la relación jurídica que dio origen a la
  emisión y/o transmisión del título valor no pagado a su vencimiento, a menos que se pruebe que hubo
  novación».
- **Código Civil, art. 1233**, citado por SUNAT en el Informe 153-2005 **[V, a través de SUNAT]**: «la entrega
  de títulos valores que constituyen órdenes o promesas de pago, sólo extinguirá la obligación primitiva
  cuando hubiesen sido pagados o cuando por culpa del acreedor se hubiesen perjudicado, salvo pacto en
  contrario. Entre tanto la acción derivada de la obligación primitiva quedará en suspenso».
  → **Consecuencia para el módulo [inferencia]**:
  - el canje **no paga** la factura: solo reclasifica la deuda;
  - si la letra se protesta o se anula, la deuda causal (la factura) «revive»;
  - la trazabilidad factura ↔ letra es obligatoria.
- **Prescripción** (art. 96.1 **[V]**):
  - **3 años** desde el vencimiento para la acción directa contra el aceptante y sus garantes;
  - **1 año** desde el vencimiento para la acción de regreso;
  - **6 meses** desde el pago para la acción de ulterior regreso;
  - estos plazos son perentorios y no admiten interrupción ni suspensión (96.3).
- Art. 99 **[V]**: la acción de enriquecimiento sin causa prescribe a los 2 años de extinguida la acción
  cambiaria.
- Art. 100 **[V]**: la acción causal prescribe según las reglas de su propia relación jurídica.

### 1.10 Letra electrónica y factura negociable

- **Letra electrónica**: no se encontró una ley específica de «letra de cambio electrónica» **[no
  verificado]**.
  - La vía legal disponible es la **desmaterialización** por anotación en cuenta en una ICLV (art. 2 **[V]**)
    y la firma digitalizada o electrónica pactada (art. 6.2 **[V]**).
  - No se pudo localizar la «Ley 30997» que menciona el encargo: no hay registro en el archivo del Congreso
    para ese número con este tema. **No se debe citar.**
- **Factura negociable**:
  - normas: Ley 29623 (Ley que promueve el financiamiento a través de la factura comercial), modificada por
    el D. Leg. 1178 y la Ley 30308; reglamento aprobado por el D.S. 208-2015-EF **[V solo como base legal
    citada en una directiva oficial del MINAM; textos no descargados]**;
  - según el art. 7 de la Ley 29623, citado en esa directiva, el adquirente tiene **8 días** para dar
    conformidad o disconformidad desde que se le notifica la anotación en cuenta. Si no responde, se presume
    la conformidad irrevocable **[no verificado en la ley]**.
  - Diferencias con la letra **[inferencia]**:
    - la factura negociable nace del propio comprobante de pago: es una copia o una anotación en cuenta en
      CAVALI;
    - la letra es un título **independiente** que sustituye en la práctica a la factura en la cartera;
    - para la factura negociable de una factura electrónica no hay canje ni asiento de reclasificación a la
      cuenta 123. Se registra como una factura en descuento (1214) o en factoring.
  - Un módulo de letras **no** debe tratar la factura negociable como una letra.

---

## 2. Tratamiento tributario (SUNAT)

### 2.1 La letra no es comprobante de pago y el canje no altera el IGV

- RCP, art. 2 **[V]**: «Sólo se consideran comprobantes de pago» las facturas, los recibos por honorarios,
  las boletas, las liquidaciones de compra, los tickets y los demás documentos autorizados. **La letra de
  cambio no está en la lista.**
- Consecuencias **[inferencia]**:
  - el canje **no** genera un comprobante ni una nota de crédito;
  - no modifica la base imponible ni el nacimiento de la obligación del IGV, que ya nació con la venta y la
    factura;
  - no se anula ni se rectifica la factura.
- No se encontró un pronunciamiento de SUNAT que exija emitir comprobantes por el canje **[no verificado]**.
- La transferencia (endoso o descuento) de la letra no es venta gravada: los títulos de crédito no son
  «bienes muebles» para el IGV (TUO de la Ley del IGV, art. 3 inc. b) **[no verificado: no se pudo descargar
  el TUO del IGV]**.
- **Factura electrónica al crédito**: desde 2021 la factura electrónica al crédito informa la «forma de pago»,
  las cuotas y sus vencimientos.
  - Fuente: directiva del MINAM que cita la plataforma de conformidad de SUNAT para facturas al crédito
    emitidas desde el 17/12/2021 **[no verificado en la R.S. de SUNAT]**.
  - Si el canje cambia las fechas pactadas, hay que confirmar si las cuotas declaradas en el CPE deben
    coincidir con las letras **[no verificado]**. Para el módulo, se recomienda advertir de la discrepancia
    y no bloquear.

### 2.2 Intereses y gastos de la letra, la renovación y la refinanciación

- **Intereses de financiación**: TUO de la Ley del IGV, art. 14, primer párrafo, transcrito por SUNAT en el
  Informe 103-2007 **[V, a través de SUNAT]**:

  > «se entiende por valor de venta del bien […] la suma total que queda obligado a pagar el adquirente […].
  > Se entenderá que esa suma está integrada por el valor total consignado en el comprobante de pago […],
  > incluyendo los cargos que se efectúen por separado de aquél y aún cuando se originen en […] intereses
  > devengados por el precio no pagado o en gastos de financiación de la operación.»

  - Consecuencia: los **intereses compensatorios** que el vendedor cobra por financiar el precio (canje con
    intereses, renovación con intereses) **forman parte de la base imponible**. Están gravados si la venta
    está gravada y exonerados o inafectos si la venta lo está (Informes 103-2007 y 274-2003 **[V]**).
- **Intereses moratorios**: la RTF 214-5-2000, de observancia obligatoria y citada en el Informe 103-2007
  **[V, a través de SUNAT]**, establece que el art. 14 se refiere solo a los compensatorios y que los
  moratorios no están incluidos. **Los intereses moratorios no están gravados con IGV.**
- **Documento que se emite**:
  - RCP, art. 10, num. 2.1 a) **[V]**: «Las notas de débito se emitirán para recuperar costos y gastos
    incurridos por el vendedor con posterioridad a la emisión de la factura o boleta de venta, como intereses
    por mora y otros».
  - La R.S. 156-2013/SUNAT, segunda disposición complementaria final, citada en el mismo artículo **[V]**,
    precisa que la nota de débito comprende las circunstancias que **aumentan el valor de la operación**.
  - Informe 334-2003 **[V]**: la nota de débito se anota en el **mes en que se emite** y afecta el IGV de ese
    mes.
  - → **Regla del módulo [inferencia]**: si el canje o la renovación incluyen intereses compensatorios o
    gastos que se trasladan al cliente, se emite una **nota de débito electrónica** referida a la factura
    canjeada. La nota lleva IGV si la operación original está gravada, y la letra se gira por el total
    (factura + nota de débito − retención o detracción, si corresponden).
  - Si se cobran intereses moratorios, se puede emitir una nota de débito sin IGV o un documento que no sea
    comprobante **[no verificado; práctica dividida]**.
  - Catálogo 10 de SUNAT (tipo de nota de débito): «01 Intereses por mora», «02 Aumento en el valor», «03
    Penalidades/otros conceptos» **[no verificado: no se descargó el catálogo; contrastar con
    `l10n_pe_edi`]**.
- **Gastos de protesto y portes bancarios** que se recuperan del cliente: se pueden reclamar cambiariamente
  (LTV, art. 92.1 c) **[V]**. Si se facturan al cliente, la vía es la nota de débito (RCP 10.2.1). Que estén o
  no gravados depende de si son un reembolso o un mayor valor de la venta **[no verificado]**.
- **Comprador**: si el vendedor aplica IGV sobre intereses de una venta exonerada, el comprador **no** puede
  usar ese crédito fiscal (Informe 103-2007 **[V]**).

### 2.3 ITF en el descuento, la cobranza y el cobro

- Alícuota: **0,005 %** (TUO de la Ley 28194, art. 10 **[V]**).
- Operaciones gravadas, art. 9 **[V]**:
  - a) la acreditación o el débito en cuentas del sistema financiero, excepto entre cuentas del mismo
    titular;
  - b) los pagos a una empresa del sistema financiero sin usar cuentas;
  - d) la entrega al mandante del dinero recaudado o cobrado en su nombre sin usar cuentas, que es el caso de
    la **cobranza**.
- **Descuento de letras** (Informe 153-2005 **[V]**):
  - el abono del **importe neto** al cliente está gravado con el ITF (art. 9 inc. a) sobre el valor de la
    operación;
  - el pago de intereses al banco «se materializará con el cumplimiento de la prestación a cargo del
    deudor»: el ITF nace cuando el aceptante paga la letra al banco, y la base imponible es el monto total
    pagado, intereses incluidos;
  - las comisiones son pagos a la entidad financiera gravados por el art. 9 inc. b).
- **Registro contable del ITF**: 6412 «Impuesto a las transacciones financieras» (PCGE 2019 **[V]**).

### 2.4 Medios de pago (bancarización)

- Monto mínimo: **S/ 2 000 o US$ 500** (TUO de la Ley 28194, art. 4, según el D. Leg. 1529, vigente desde el
  01/04/2022 **[V]**). Para sujetos con los dos niveles de cumplimiento más bajos, el umbral es el 30 %.
- Medios de pago (art. 5 **[V]**): depósitos en cuenta, giros, transferencias, órdenes de pago, tarjetas,
  cheques, remesas y cartas de crédito. **La letra de cambio no es un medio de pago.**
  → La entrega de una letra no bancariza. La bancarización se cumple cuando **se paga la letra** con un medio
  de pago **[inferencia]**.
- Art. 6 a) **[V]**: están exceptuados los pagos **a empresas del sistema financiero**. Por eso, cuando la
  letra está en descuento y el aceptante paga al banco tenedor, ese pago no exige medio de pago
  **[inferencia]**.
- Efectos de no usar medios de pago (art. 8 **[V]**): no se pueden deducir gastos, costos ni crédito fiscal.
  → El módulo debe registrar **cómo se pagó la letra** (banco, operación, medio según la Tabla 1) y no solo
  marcarla como pagada.

### 2.5 Retenciones del IGV

- Momento de la retención:
  - Informe 372-2002 **[V]**: si el pago se comprometió con una letra aceptada, la retención se efectúa «en la
    fecha de vencimiento o aquella en la que se haga efectivo dicho título valor, lo que ocurra primero»;
  - si la letra se **renueva**, se aplica la **nueva** fecha de vencimiento o el pago efectivo, lo que ocurra
    primero.
- Informe 112-2003 **[V]**:
  - quien retiene es el **comprador aceptante**, aunque la letra se haya descontado en un banco;
  - el aceptante emite el comprobante de retención a su proveedor cuando paga;
  - si paga parcialmente, retiene sobre cada pago.
- FAQ de SUNAT, pregunta 17 **[V]**: ejemplo en el que la letra **se emite deduciendo el monto de la
  retención**. La factura es de S/ 5 900, la retención de S/ 354 y la letra de S/ 5 546. La retención se
  declara en el periodo del vencimiento o pago de la letra (PDT 626).
- La FAQ usa la tasa histórica del 6 %. La tasa vigente es el **3 %** **[no verificado en esta
  investigación; ver `al_l10n_pe_retention`]**.
- **Requisitos del módulo**:
  - permitir girar la letra neta de la retención;
  - lado proveedor: generar el comprobante de retención al **pagar** la letra, no al canjearla;
  - cuenta 40114 «IGV – Régimen de retenciones» (PCGE **[V]**).
- **Percepciones**: no se encontró criterio de SUNAT específico para letras **[no verificado]**. Por analogía,
  la percepción se practica al cobrar **[inferencia]**.

### 2.6 Detracciones (SPOT)

- No se encontró un informe de SUNAT específico sobre letras y detracciones **[no verificado]**.
- Práctica e inferencia **[no verificado]**:
  - la letra se gira por el importe neto de la detracción, porque el depósito de la detracción no es un
    pago al proveedor por medio de la letra;
  - el plazo del depósito (R.S. 183-2004/SUNAT) suele vencer antes que la letra, ya que se cuenta desde el
    pago o desde la anotación en el Registro de Compras.
- El módulo debe calcular el **neto canjeable**: total − detracción − retención.

### 2.7 PLE, SIRE y libros

- **Registro de Ventas / RVIE (SIRE) y Registro de Compras / RCE**: se registran **comprobantes** (Tabla 10).
  Como la letra no es comprobante (RCP, art. 2 **[V]**), **las letras no se anotan en esos registros**
  **[inferencia]**. Sí se anotan las notas de débito por intereses (código 08).
- **Tabla 10**, Anexo 3 del PLE (R.S. 169-2015/SUNAT) **[V]**:
  - no tiene ningún código para «letra de cambio»;
  - los códigos van del **00 «Otros»** al 98, e incluyen el 20 «Comprobante de Retención» y los 40/41 de
    percepción.
  - En los libros que piden el tipo de documento (Libro Diario 5.1, Libro Mayor), lo habitual es usar **00**
    y el número de la letra **[no verificado]**.
- **Tabla 1** (tipo de medio de pago) **[V]**:
  - incluye el 001 depósito en cuenta, el 003 transferencia y el 999 «otros medios de pago», entre otros;
  - **no hay código para letra**;
  - en el Libro Caja y Bancos 1.2 se informa el medio con el que se cobró o pagó la letra **[inferencia]**.
- **Libro de Inventarios y Balances 3.3** (detalle del saldo de las cuentas 12 y 13): campos por cliente
  (tipo y número de documento, nombre, fecha de emisión o de referencia del comprobante, monto)
  **[V: `docs/ple/oficial/Estructura del PLE.xls`]**.
  - Las letras en cartera, cobranza y descuento forman parte de ese saldo.
  - Como «fecha de referencia» se usa la de la letra **[inferencia]**.
- **3.12** (cuenta 42) y **3.13** (cuenta 46): análogos para las letras por pagar **[no verificado
  campo a campo]**.

---

## 3. Contabilidad según el PCGE 2019

**Norma vigente**: PCGE aprobado por la Res. CNC 002-2019-EF/30, obligatorio desde el 01/01/2020. Deroga el
PCGE 2010 (Res. 041-2008-EF/94 y versión modificada 043-2010-EF/94) **[V]**.

> **Atención**: el PCGE 2010 numeraba **1231 En cartera / 1232 En cobranza / 1233 En descuento**. El
> **PCGE 2019** numera **1232 / 1233 / 1234** y **no tiene 1231** (PCGE_2019.txt, líneas 936-939, y tabla
> comparativa, líneas 9240-9243 **[V]**). El plan de Odoo `addons/l10n_pe/data/template/account.account-pe.csv`
> ya usa la numeración 2019: `1232` «Letras por cobrar - En cartera», `1233` «- En cobranza», `1234` «- En
> descuento». Un módulo que asuma 1231/1232/1233 está **desactualizado**.

### 3.1 Cuentas con denominación exacta (PCGE 2019 [V])

**Cuentas por cobrar**

| Código | Denominación exacta |
|---|---|
| 12 | CUENTAS POR COBRAR COMERCIALES – TERCEROS |
| 121 | Facturas, boletas y otros comprobantes por cobrar |
| 1211 | No emitidas |
| 1212 | Emitidas en cartera |
| 1213 | En cobranza |
| 1214 | En descuento |
| 123 | Letras por cobrar |
| 1232 | En cartera |
| 1233 | En cobranza |
| 1234 | En descuento |
| 133 / 1331… | Letras por cobrar (relacionadas), subcuentas 1331 En cartera, etc. |
| 191 / 1913 | Cuentas por cobrar comerciales – Terceros / Letras por cobrar (estimación de cobranza dudosa) |
| 192 / 1923 | Cuentas por cobrar comerciales – Relacionadas / Letras por cobrar |

**Cuentas por pagar y obligaciones financieras**

| Código | Denominación exacta |
|---|---|
| 42 | CUENTAS POR PAGAR COMERCIALES TERCEROS |
| 4212 | Emitidas |
| 423 | Letras por pagar |
| 433 / 4331 | Letras por pagar (relacionadas) |
| 45 | OBLIGACIONES FINANCIERAS |
| 451 / 4511 | Préstamos de instituciones financieras y otras entidades / Instituciones financieras |
| 454 / 4541 | Otros Instrumentos financieros por pagar / Letras |
| 4554 / 45541 | Otros instrumentos financieros por pagar / Letras (costos de financiación por pagar) |

**Impuestos, efectivo e intereses diferidos**

| Código | Denominación exacta |
|---|---|
| 40111 | IGV – Cuenta propia |
| 40113 | IGV – Régimen de percepciones |
| 40114 | IGV – Régimen de retenciones |
| 1041 | Cuentas corrientes operativas |
| 3731 | Intereses no devengados en transacciones con terceros |
| 4931 | Intereses no devengados en transacciones con terceros (493 Intereses diferidos: «intereses relacionados con cuentas por cobrar, los que aún no han devengado») |

**Gastos e ingresos**

| Código | Denominación exacta |
|---|---|
| 6391 | Gastos bancarios |
| 6412 | Impuesto a las transacciones financieras |
| 6714 | Documentos vendidos o descontados (671 = gastos distintos de intereses con instituciones financieras) |
| 6734 | Documentos vendidos o descontados (673 Intereses por préstamos y otras obligaciones) |
| 6736 | Obligaciones comerciales |
| 676 / 776 | Diferencia de cambio / Diferencia en cambio |
| 7722 | Cuentas por cobrar comerciales (772 Rendimientos ganados) |
| 7599 | Otros ingresos de gestión |

Dinámicas y glosario oficiales **[V]**:

- la cuenta 12 se carga y se abona por «el traslado entre cuentas internas, como es el caso del canje de
  facturas con letras, o el cambio de condición de letras emitidas, a cobranza o descuento»;
- la cuenta 42 se mueve igual «cuando se canjean las facturas por letras»;
- el glosario define la «transferencia de cuentas» con el ejemplo del canje de letras dentro de las cuentas
  por cobrar.

**No existe en el PCGE una cuenta de «letras protestadas»** **[V: no aparece]**. En la práctica se abre una
divisionaria propia (p. ej. 12341x o 1235 «Letras protestadas», no oficial) o se distingue por estado o por
cuenta analítica **[no verificado]**. La estimación de cobranza dudosa va en 1913.

### 3.2 Asientos típicos

Los asientos combinan la dinámica oficial **[V]** con la práctica **[no verificado]**. Importes de ejemplo:
factura de S/ 1 180 con IGV.

**Cliente**

| # | Operación | Debe | Haber |
|---|---|---|---|
| 1 | Venta (factura) | 1212 | 70xx / 40111 |
| 2 | Nota de débito por intereses de financiamiento en el canje | 1212 | 7722 (o 4931 si se difiere y se devenga mes a mes) / 40111 |
| 3 | **Canje** factura (+ nota de débito) → letras | 1232 (una línea por letra) | 1212 (factura y nota de débito) |
| 4 | Envío a **cobranza** (libre o en garantía) | 1233 | 1232 |
| 4b | Comisión y portes de cobranza | 6391 (+ 40111 si la comisión está gravada) | 1041 |
| 5 | Cobro de una letra en cobranza (abono del banco) | 1041 (+ 6412 ITF) | 1233 |
| 6 | Envío a **descuento** | 1234 | 1232 |
| 6b | Desembolso del descuento (**con recurso**: el riesgo no se transfiere, NIIF 9, así que se reconoce un pasivo) | 1041 (neto) + 6734 intereses (o 3731 si se difieren) + 6714 / 6391 comisiones + 6412 ITF | 4511 (o 4541) por el nominal |
| 6c | El aceptante paga al banco a su vencimiento | 4511 | 1234 |
| 6d | Variante: sin pasivo, con baja de la letra al descontar (criticable con NIIF 9) | 1041 + 67xx | 1234 |
| 7 | Cobro directo (letra en cartera) | 1041 / 101 | 1232 |
| 8 | **Protesto** o impago de una letra en cartera | 1232-protestadas (divisionaria) | 1232 |
| 8b | Impago de una letra **en descuento**: el banco carga la cuenta | 4511 | 1041 |
| 8b' | (mismo caso) la letra vuelve a cartera como protestada | 1232-protestadas | 1234 |
| 8c | Gastos de protesto y portes | 6391 | 1041 |
| 8c' | (mismo caso) si se recobran al cliente, mediante nota de débito | 1212 | 7599 / 40111 |
| 9 | **Renovación**: amortización + letra nueva por el saldo + intereses | 1041 (amortización) + 1232 (letra nueva) | 1232 (letra antigua) |
| 9' | (mismo caso) los intereses de la renovación, mediante nota de débito canjeada | 1212 | 7722 / 40111 |
| 10 | Anulación de un canje antes de la aceptación o la circulación | 1212 | 1232 |
| 11 | Estimación de cobranza dudosa de una letra | 6871 (Estimación de cuentas de cobranza dudosa) | 1913 |

**Proveedor**

| # | Operación | Debe | Haber |
|---|---|---|---|
| P1 | Compra | 60xx / 40111 | 4212 |
| P2 | Canje (aceptamos letras) | 4212 | 423 |
| P3 | Pago de la letra (retención, si somos agente de retención) | 423 | 1041 (+ 40114 por la retención, si la letra no se giró neta) |
| P4 | Nota de débito del proveedor por intereses de la renovación | 6736 (o 3731) + 40111 | 4212 |
| P4' | (mismo caso) letra nueva por saldo e intereses | 423 (antigua) + 4212 (nota de débito) | 423 (nueva) |

### 3.3 Multimoneda

Según el PCGE **[V]**, las cuentas por cobrar y por pagar en moneda extranjera se expresan al **tipo de cambio
de cierre**, y la diferencia de cambio va a 676/776.

Criterios **[inferencia; no verificado en norma]**:

- la letra se gira en la **misma moneda** que la factura;
- el canje es una «transferencia entre cuentas» y debe hacerse **al importe en moneda extranjera de la factura
  y a su valor contable**, sin crear una diferencia de cambio artificial, o reconociendo la diferencia
  devengada hasta la fecha del canje, una sola vez;
- la diferencia de cambio sigue devengándose sobre la letra hasta su cobro;
- para cobros en moneda nacional de letras en moneda extranjera, el tipo de cambio legal de pago es el
  **venta** del día de vencimiento (LTV, art. 68 **[V]**).

---

## 4. Práctica del mercado peruano [no verificado salvo lo marcado]

### 4.1 Modalidades bancarias

| Modalidad | Qué es | Base legal |
|---|---|---|
| **Cobranza libre** | El banco recibe las letras en endoso en procuración, cobra por cuenta del cliente y abona lo cobrado. No adelanta fondos. Cobra comisión y portes. | Art. 41 LTV **[V]** |
| **Cobranza en garantía** | Las letras quedan endosadas en garantía de una línea de crédito, de un sobregiro o de otra deuda. El banco cobra y aplica lo cobrado a la deuda o lo libera al cliente. | Art. 42 LTV **[V]** |
| **Descuento** | El banco adelanta el importe neto de intereses (tasa por días al vencimiento), comisiones, portes e ITF. Es **con recurso**: si el aceptante no paga, el banco carga la cuenta del cliente. Exige una línea de descuento aprobada y la planilla o relación de letras. | Res. SBS 4358-2015, arts. 11 y 12 **[V]** (art. 12: contrato escrito de descuento) |

- Los bancos suelen exigir letras **aceptadas** y con aval, si lo hay.
- Usan su **propio formato de letra** o aceptan el del cliente con datos mínimos: RUC, domicilio y teléfono
  del aceptante.
- Reciben la «planilla» de letras de forma física o electrónica (archivo de la banca por internet).
- Envían al cliente avisos de vencimiento y estados de cuenta de letras en cobranza o descuento.

### 4.2 Estados típicos de una letra

| Estado | Descripción |
|---|---|
| Borrador | Canje en preparación |
| Emitida o girada | En cartera, pendiente de aceptación |
| Aceptada (en cartera) | 1232 |
| En cobranza (libre o en garantía) | 1233; guardar el banco, el número de planilla y la fecha de envío |
| En descuento | 1234; guardar el banco, la planilla, la tasa, el neto abonado y el pasivo asociado |
| Cobrada o pagada | Total o **parcial**, porque el art. 65 obliga a aceptar pagos parciales |
| Protestada o impaga | Fecha de protesto, notaría, gastos; o «vencida» si tiene cláusula sin protesto |
| Renovada | Con enlace a las letras nuevas |
| Refinanciada | Enlace N:M |
| Devuelta por el banco | Retorno a cartera desde cobranza o descuento |
| Anulada | Revierte el canje |
| Castigada o incobrable | 1913 o baja |

### 4.3 Numeración

- La ley no impone ninguna numeración **[V: art. 119 no la exige]**.
- En la práctica se usa una **secuencia única por compañía**, a veces con serie por tipo (por cobrar o por
  pagar) o por año, y número de «canje» o «planilla».
- En las letras por pagar se guarda el número que puso el proveedor girador.
- El número del banco (número único asignado al recibir la letra en cobranza o descuento) se guarda aparte.

### 4.4 Campos del formato impreso

**Obligatorios por el art. 119 [V]**:

- denominación «LETRA DE CAMBIO»;
- lugar y fecha de giro;
- moneda e importe **en números y en letras** (si difieren, prevalece el menor según el art. 5.2);
- vencimiento;
- a la orden de (beneficiario);
- girado o aceptante: nombre o razón social, **RUC o DNI** y domicilio;
- girador: nombre, RUC o DNI y **firma**;
- lugar o forma de pago.

**Habituales [no verificado]**:

- número de letra y referencia del girador (facturas canjeadas);
- recuadro **«ACEPTADA»** con fecha, firma, nombre y DNI del aceptante o de su representante (art. 128
  **[V]**);
- **aval**: nombre, documento de identidad, domicilio y firma, con la cláusula «por aval» (art. 58 **[V]**);
- cláusulas impresas al dorso o en el anverso:
  - «sin protesto» (arts. 52 y 81);
  - prórroga (art. 49);
  - tasas compensatoria y moratoria desde el vencimiento (arts. 51 y 146);
  - pago en moneda extranjera (art. 50);
  - pago con cargo en cuenta: banco y número de cuenta (art. 53);
- espacio de endosos al reverso;
- código del banco o número único.

Módulos existentes imprimen **2 letras por hoja A4** (ver §5).

---

## 5. Módulos en Odoo Apps (consulta del 07/10/2026)

Búsquedas en apps.odoo.com con las series 16.0 a 19.0 y los términos «letras», «letras de cambio», «bill of
exchange», «letras por cobrar», «canje», «descuento de letras», «protesto» y «l10n_pe». Precios en EUR tal
como los muestra la tienda.

| Nombre técnico | Título | Autor | Versiones | Precio | Licencia | Funciones declaradas |
|---|---|---|---|---|---|---|
| `pc_account_boe` | Letras de Cambio | Codex Development (perucodex.com) | 15, 16, 18, 19 | 227,57 € (con «In-App Purchases») | LGPL-3 | Formulario de canje desde clientes o proveedores; estado de pago «canjeada» en facturas y letras; recepción de letras de terceros; responsables y aceptante; impresión de 2 letras por A4. En la 19.0 la ficha indica que **requiere Enterprise**. |
| `pc_account_boe_send` | Envíos al Banco y Renovaciones | Codex Development | 15, 16, 18, 19 | 306,34 € | LGPL-3 | Envío de letras al banco, estados de las letras enviadas, asistente de **desembolso** de letras en descuento y renovaciones. |
| `pc_account_boe_advance` | Anticipos de Letras | Codex Development | 16, 18, 19 | 253,25 € | LGPL-3 | Letras como **anticipo** de clientes sin factura. |
| `cerevantix_bill_of_exchange` | Bill of Exchange (LCR / Traite) | Cerevantix Technologies | 17, 18, 19 | 79,44 € | OPL-1 | Generar, imprimir, exportar y conciliar letras desde facturas. Orientación francesa (LCR). |
| `facture_traite` | Bill of Exchange | Auneor Conseil | 8 a 19 | 65,00 € | — | Exportación de «traites» (Francia). |
| `dynamic_print_exchange` | Dynamic Print bill of exchange | Ahmed Mnasri | 16, 17, 19 | 25,00 € | OPL-1 | Solo impresión configurable por posiciones (Túnez). |
| `dvl_l10n_pe_account` (y `_mype`, `_micro`) | Contabilidad peruana, pack completo | Develogers | 16, 17, 18 | 2 568,07 € | OPL-1 | La ficha **no menciona letras**. |

Lo que ofrecen y que un módulo propio podría no tener **[según las fichas; no probado]**:

1. Letras **de terceros recibidas en pago**, endosadas a nosotros.
2. **Anticipos con letras** sin factura previa.
3. **Envíos al banco** agrupados por planilla y **asistente de desembolso** del descuento: neto, intereses y
   comisiones en un solo paso.
4. Renovaciones desde el envío al banco.
5. Impresión de 2 letras por página A4.

No se encontró en ninguna ficha: protesto con gastos y notaría, cláusula de prórroga, pagos parciales
anotados, intereses con nota de débito automática, retención o detracción neta en el canje, integración con
PLE, ni reportes de cartera por estado o banco. **Son puntos de diferenciación posibles.**

---

## 6. Lista de verificación para auditar un módulo de letras en Odoo 19

### A. Datos y requisitos legales

- [ ] Hay un modelo de letra propio (no un `account.move` disfrazado) con **todos los campos del art. 119**:
  - denominación, lugar y fecha de giro, moneda, importe y **importe en letras**;
  - girado con RUC o DNI (y domicilio), beneficiario o «a la orden de», girador con RUC o DNI;
  - vencimiento, lugar o cuenta de pago (art. 53).
- [ ] Hay un único vencimiento por letra: un canje en cuotas genera N letras (art. 121.2).
- [ ] Tipos de vencimiento soportados, al menos fecha fija y, de forma opcional, a la vista y a plazo desde el
  giro o la aceptación. Hay una alerta si el vencimiento cae en un día inhábil (art. 144.4).
- [ ] Hay campos de aceptación (fecha y aceptante o representante con documento de identidad) y de **aval**
  (nombre, documento de identidad, domicilio).
- [ ] Hay cláusulas configurables: «sin protesto», prórroga, tasas compensatoria y moratoria **desde el
  vencimiento**, pago en moneda extranjera y cargo en cuenta.
- [ ] El módulo **no** permite pactar intereses anteriores al vencimiento como cláusula (art. 146): el
  interés de financiamiento va en el nominal.
- [ ] La numeración es secuencial por compañía y no editable tras emitir. Se guardan el número del banco y el
  número del girador en las letras por pagar.
- [ ] La letra queda vinculada a sus facturas o notas de débito de origen, en relación N:M con importes
  asignados.

### B. Estados y flujo

- [ ] Estados cubiertos: borrador → aceptada (cartera) → en cobranza libre o en garantía / en descuento →
  cobrada (total o **parcial**) / protestada / renovada / refinanciada / devuelta / anulada / castigada.
- [ ] Las transiciones son coherentes. Por ejemplo, no se puede descontar una letra protestada, y no se
  puede renovar una letra protestada mediante reaceptación (art. 140).
- [ ] El **pago parcial** se registra y deja el saldo pendiente (art. 65).
- [ ] Al renovar o refinanciar se enlazan las letras origen y destino, la amortización y los nuevos
  vencimientos, y se impide renovar dos veces la misma letra.
- [ ] Al anular, se revierte el canje y la factura vuelve a quedar pendiente.
- [ ] El historial (chatter) registra el banco, la planilla, las fechas de envío y de retorno y el motivo del
  protesto.

### C. Asientos y cuentas

- [ ] Las cuentas por defecto siguen el **PCGE 2019**: **1232 / 1233 / 1234** (no 1231/1232/1233 del PCGE
  2010) y **423**. Son configurables por compañía o diario.
- [ ] El canje produce un asiento de **reclasificación** 1212 → 1232 (y 4212 → 423) con **conciliación** de la
  línea de la factura: la factura queda «pagada» o «en canje» sin que exista un pago real.
- [ ] El estado de pago de la factura distingue «canjeada» de «cobrada», para reportes y para el art. 1233 del
  Código Civil.
- [ ] Se usan los tipos de cuenta correctos (`asset_receivable` / `liability_payable`) y el reconcile
  activado en 1232, 1233, 1234 y 423, para que los asistentes de pago funcionen.
- [ ] El paso a cobranza o descuento es un asiento 1232 → 1233 / 1234 con partner y conciliación de la
  línea anterior.
- [ ] El desembolso del descuento registra el neto en el banco, los intereses (6734 o 3731), las comisiones
  (6714 o 6391), el ITF (6412) y el pasivo (4511 o 4541). El criterio, con o sin pasivo, es configurable y
  está documentado.
- [ ] El pago de una letra descontada por el aceptante cancela el pasivo contra 1234. El impago revierte al
  banco y devuelve la letra a cartera como protestada.
- [ ] El protesto reclasifica la letra a una divisionaria o estado «protestada», registra los gastos (6391) y
  permite recobrarlos.
- [ ] Hay un asiento de estimación de cobranza dudosa en 1913.
- [ ] Los asientos de letras van a un diario propio o configurable, y no hay asientos huérfanos al cancelar.
- [ ] Multicompañía: `company_id`, `check_company=True`, record rules, secuencias por compañía.

### D. Conciliación

- [ ] Las letras cobradas se concilian con el extracto bancario: cada letra o planilla es una línea
  conciliable, y se admiten cobros agrupados.
- [ ] La reversa de una conciliación (desconciliar) devuelve los estados de forma consistente.
- [ ] No hay doble conteo de cartera: el saldo de 1212 de una factura canjeada es cero y la deuda vive en 123.

### E. Multimoneda

- [ ] La letra está en la moneda de la factura y no se permite mezclar monedas en un mismo canje, o se exige
  convertir de forma explícita.
- [ ] El canje se hace al valor contable o con la diferencia de cambio devengada **una sola vez**, sin
  diferencias artificiales por usar el tipo de cambio del día sobre `amount_currency`.
- [ ] El ajuste por diferencia de cambio al cierre alcanza 1232, 1233, 1234 y 423. Está integrado con
  `al_l10n_pe_exchange_closure` o con la revaluación de Enterprise.
- [ ] El cobro en soles de una letra en dólares usa el tipo de cambio **venta** del vencimiento (art. 68).
- [ ] La diferencia de cambio realizada al cobrar va a 676 o 776.

### F. Intereses y gastos

- [ ] El canje con intereses genera una **nota de débito electrónica** referida a la factura, con IGV si la
  operación está gravada (art. 14 de la Ley del IGV; RCP 10.2.1). La letra incluye la nota de débito.
- [ ] Los intereses moratorios se tratan **sin IGV** (RTF 214-5-2000) y el documento que se emite es
  configurable.
- [ ] La renovación con intereses hace lo mismo y además ofrece una opción para cobrar la amortización en la
  misma operación.
- [ ] Los gastos de protesto, de cobranza o los portes se pueden trasladar al cliente (nota de débito) o
  asumir como gasto.
- [ ] Si se difieren intereses (3731 / 4931), hay devengo mensual automático o asistido.

### G. Impuestos y SUNAT

- [ ] **Retención del IGV**:
  - opción de girar la letra **neta** de la retención;
  - en las compras, el comprobante de retención se emite al **pagar la letra** (vencimiento o pago, lo que
    ocurra primero) y no al canjear (Informes 372-2002 y 112-2003);
  - en las renovaciones, se usa el nuevo vencimiento.
- [ ] **Detracción**: la letra se gira neta de la detracción y el estado del depósito es visible.
- [ ] **Percepción**: hay un tratamiento definido.
- [ ] **ITF**: hay una cuenta 6412 y su cálculo es opcional en el desembolso y el cobro.
- [ ] **Medios de pago**: el cobro o pago de la letra registra el medio (Tabla 1) y hay una alerta si el monto
  supera S/ 2 000 / US$ 500 sin medio bancario (salvo pago a un banco, art. 6 a).
- [ ] No se emite ningún CPE por el canje ni se tocan el SIRE o los registros de ventas y compras por la
  letra.

### H. Reportes

- [ ] Cartera de letras por estado, banco, cliente y vencimiento (aging), con totales por moneda.
- [ ] Planilla de envío al banco (cobranza o descuento), imprimible y exportable.
- [ ] Letras por pagar con su calendario.
- [ ] Letras protestadas, renovadas y anuladas.
- [ ] Cuadre del saldo contable de 1232, 1233, 1234 y 423 contra la suma de letras abiertas.

### I. Impresión

- [ ] Formato QWeb con todos los campos del art. 119, el **importe en letras** en español (soles o dólares),
  el recuadro de aceptación, el aval y las cláusulas.
- [ ] Opción de 1 o 2 letras por A4, márgenes adaptados a formularios preimpresos y vista previa.
- [ ] Se respetan las trampas de QWeb-PDF del proyecto (clase `article`, reset de bordes de wkhtmltopdf).

### J. PLE y libros

- [ ] El Libro Diario y el Mayor exportan las líneas de letras con tipo de documento **00** (Tabla 10 sin
  código de letra) y el número de la letra.
- [ ] El Libro de Inventarios y Balances 3.3 incluye los saldos de las letras en 12x por cliente, y 3.12
  hace lo mismo con 423.
- [ ] El Libro Caja y Bancos 1.2 refleja el cobro o pago de la letra con su medio de pago.

### K. Calidad técnica (Odoo 19)

- [ ] `security/ir.model.access.csv` para cada modelo, record rules multicompañía y grupos.
- [ ] Sin `sudo()` injustificado.
- [ ] Vistas `<list>` con `invisible=` / `readonly=`, `models.Constraint` para la unicidad del número por
  compañía y `aggregator=` en los importes.
- [ ] Pruebas: canje simple y en cuotas, nota de débito por intereses, cobranza, descuento con desembolso,
  cobro, protesto en cartera y en descuento, renovación con amortización, anulación, pago parcial,
  multimoneda con diferencia de cambio, retención en la compra y multicompañía.
- [ ] Traducción `i18n/es.po` y etiquetas con solo la primera letra en mayúscula.

---

## 7. Pendientes de verificación

1. Texto consolidado de la Ley 27287 en el SPIJ: comprobar si los arts. 10, 52, 72, 81, 119 y 146 se
   modificaron después del 2000, y leer el art. 279 (glosario).
2. TUO de la Ley del IGV (D.S. 055-99-EF), arts. 3 inc. b) y 14, y Reglamento, art. 5: leerlos en su fuente
   directa.
3. Catálogo 10 de SUNAT (tipos de nota de débito) en su versión vigente.
4. R.S. de SUNAT sobre la forma de pago y las cuotas en la factura electrónica al crédito, y su relación con
   el canje.
5. Ley 29623, D. Leg. 1178, Ley 30308 y D.S. 208-2015-EF: textos vigentes.
6. Tasa vigente de retención del IGV (3 %) y la R.S. que la fijó.
7. R.S. 183-2004/SUNAT: oportunidad del depósito de la detracción cuando el pago se hace con letras.
8. Ley 26702 (Ley General del Sistema Financiero): operaciones de descuento de letras autorizadas.
9. Práctica bancaria (§4): contrastar con los tarifarios y contratos de descuento y cobranza de BCP, BBVA,
   Interbank y Scotiabank.

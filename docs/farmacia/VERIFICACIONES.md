# Verificaciones normativas — suite de farmacias (OL-HEALTH)

Fecha de la investigación: 19/10/2026. Convención:

- **[V]**: verificado leyendo el texto de la fuente (URL indicada).
- **[I]**: inferido, o tomado de una fuente secundaria. Hay que confirmarlo con DIGEMID, la DIRIS/DIRESA, SUNAT o el cliente.

---

## 1. Observatorio Peruano de Productos Farmacéuticos (OPPF/SNIPPF)

### Marco vigente
- [V] **RM 040-2010/MINSA**, modificada por la **RM 341-2011/MINSA** (03/05/2011), que aprueba la **Directiva Administrativa N° 176-MINSA/DIGEMID V.01**, «Procedimiento para el reporte de precios de los establecimientos farmacéuticos en el Sistema Nacional de Información de Precios de Productos Farmacéuticos». Texto escaneado de El Peruano (06/05/2011): http://www.dirislimaeste.gob.pe/Virtual2/Otros_Link/DFCVS/R.M.341-2011-MINSA%20-%20SISTEMA%20NACIONAL%20DE%20INFORMACION%20DE%20PRECIOS.pdf
- [V] DIGEMID la seguía citando como vigente en el Comunicado 016-2023, junto con el art. 30 del DS 014-2011-SA: https://www.digemid.minsa.gob.pe/Archivos/Comunicados/2023/COM_016-2023.pdf
- [V] La **Ley 32033** (20/05/2024) incorporó el **art. 28-A** a la Ley 29459. Obliga a todos los establecimientos farmacéuticos a informar al sistema los precios de su oferta de **productos farmacéuticos y dispositivos médicos**, «en las condiciones que establezca el reglamento y la directiva correspondiente»: https://leyes.congreso.gob.pe/Documentos/2021_2026/ADLP/Texto_Consolidado/32033-TXM.pdf
- [V] No encontré ninguna directiva que sustituya a la 176. DIGEMID sigue publicando el «Indicador de precios» mensual, hecho con los datos que las boticas informan al OPPF (hasta diciembre de 2025): https://www.digemid.minsa.gob.pe/webDigemid/reportes/2025/indicador-de-precios-de-productos-farmaceuticos/

### Quién informa y qué informa (RM 341-2011, arts. 2, 3 y 4; Directiva 176)
- [V] Están obligados los laboratorios, las droguerías y las **farmacias y boticas públicas y privadas**, incluidas las farmacias de los establecimientos de salud.
- [V] Se informan los medicamentos (salvo agentes de diagnóstico, radiofármacos y gases medicinales) y los productos biológicos con registro sanitario vigente. El numeral 5.3 excluye además los productos sanitarios, los dispositivos médicos, los dietéticos y los edulcorantes. [I] La Ley 32033 extiende la obligación a los dispositivos médicos, pero falta la directiva que la ponga en práctica: por ahora los dispositivos no se informan.
- [V] **Precio de las farmacias y boticas** (num. 6.4.2 y art. 4.2): el **precio de venta al público con IGV**, con todos los descuentos de alcance, acceso o conocimiento general vigentes en el mes informado. Laboratorios y droguerías informan mínimo, máximo y mediana sin IGV.
- [V] Solo se informan los productos que el establecimiento **oferta en el mes** y tiene en stock (num. 5.1 y 6.2.4).
- [V] Los precios llevan **como máximo dos decimales** (num. 5.2).

### Periodicidad y plazos
- [V] El envío es **al menos una vez al mes** (art. 4; num. 5.1.4, 6.1.3 y 6.2.5). La directiva **no fija un día del mes** (el OCR dice «en [cualquier] día del mes»).
- [V] Durante el mes se permiten **envíos adicionales**, solo con los productos cuyo precio cambió o que se quedaron sin stock. A los productos no incluidos el sistema les pone la fecha del último envío.
- [V] Con **web service**, solo se envía cuando cambia un precio (num. 5.1.5 y 6.3.2).
- [V] **Rectificación**: una sola vez por entrega, dentro de los **7 días hábiles** siguientes al reporte mensual, y así se evita la sanción (art. 4 de la RM 040-2010, modificado).
- [V] Sanción: DIGEMID sancionó a Boticas Mifarma por no informar, con base en el num. 6.4.1.1 (RD 008-2021-DIGEMID-DFAU): https://www.digemid.minsa.gob.pe/Archivos/Resoluciones/DFAU/2021/RD_DFAU_008_2021.pdf
- [V] En 2023 la plataforma estuvo caída y el mes de febrero no se contó como incumplimiento (COM 016-2023). Las boticas hacen sus consultas al **Gestor del OPPF** de su DIRIS/DIRESA/GERESA.

### Métodos y formato
- [V] Hay tres métodos, que se pueden usar a la vez (num. 5.1.3 y 5.1.6): **formulario web**, **archivo Excel** (.xls/.xlsx) y **web service**. Antes hay que registrarse en el módulo del SNIPPF, que da usuario y clave. El sistema envía una confirmación por correo.
- [V] El Excel tiene una estructura distinta según el tipo de establecimiento (num. 6.2.1.2: «Farmacias y Boticas Privadas», que incluye las farmacias de clínicas privadas). El cuadro de columnas es una imagen que el OCR no recupera.
- [V] El **código del producto** es el del **Catálogo de Productos Farmacéuticos** que se publica en el portal del Observatorio (num. 6.2.2).
- [I] Columnas de la plantilla para boticas, según una guía de 2011 (https://webadicto.net/guia-para-enviar-la-lista-de-precios-de-boticas-y-farmacias-al-observatorio-peruano-de-productos-farmaceuticos-mediante-archivo-excel/): hoja **`Hoja1`**, columnas **`CodEstab`, `CodProd`, `Precio 1`, `Precio 2`**.
  - `CodEstab`: código del establecimiento que figura en la constancia de inscripción. Va como texto, porque puede empezar con cero, y se repite en todas las filas.
  - `CodProd`: código del catálogo de DIGEMID. Los nombres se ignoran.
  - `Precio 1` es el precio por empaque y `Precio 2` el precio por unidad, con 2 decimales.
  - Hay un manual de carga Excel del 31/07/2023 (solo en copias de terceros) y otro de carga masiva en .zip. Según este último, la **primera carga del mes reemplaza la lista**: los productos que no estén en el archivo se dan de baja. Las cargas siguientes solo actualizan. **Hay que confirmar la plantilla vigente descargándola del aplicativo del OPPF.**
- [I] El código de establecimiento es **uno por local** (cada botica tiene su autorización sanitaria y su código), no uno por RUC.

---

## 2. Servicios complementarios en farmacias y boticas

### Normas
- [V] El **art. 35 del DS 014-2011-SA** (Reglamento de Establecimientos Farmacéuticos) permite a las farmacias y boticas brindar **servicios sanitarios complementarios** y vender productos fuera de la clasificación de la Ley 29459. La ANS los actualiza por RM. Así lo cita la RM 734-2025: https://busquedas.elperuano.pe/dispositivo/NL/2453584-1
- [V] El **art. 46, num. 6 de la Ley 29459** (modificado por la Ley 32033) prohíbe en farmacias, boticas, farmacias de EESS y botiquines: **consultas médicas, consultorios médicos, análisis clínicos, recolección de muestras para laboratorio clínico, campañas médicas y demás actividades no autorizadas expresamente**. El num. 7 prohíbe vender productos vetados por la ANS (texto consolidado de la Ley 32033, enlace arriba).
- [V] La **RM 734-2025/MINSA** (30/10/2025, El Peruano 31/10/2025) aprueba la «relación de productos y servicios prohibidos de comercializar y/o de brindar en farmacias, boticas, farmacias de los EESS y botiquines» y **deroga la RD 006-2015-DIGEMID-DG-MINSA**. Antes se publicaron los proyectos RM 419-2025 y RM 486-2025.
  - [I] Contenido del anexo según la prensa (https://rpp.pe/politica/gobierno/minsa-actualiza-lista-de-productos-y-servicios-que-farmacias-y-boticas-estan-prohibidas-de-comercializar-cuales-son-noticia-1662087 y https://www.saludyfarmacos.org/lang/es/boletin-farmacos/boletines/feb202605/76_fa/):
    - **Servicios prohibidos**: análisis clínicos, recolección de muestras, consultas médicas presenciales o **virtuales**, consultorios, campañas médicas, cabinas de internet y locutorios, degustaciones, juegos de azar, tragamonedas, lotería y apuestas, videojuegos y máquinas de premios, lavandería, servicios estéticos (peluquería, spa, masoterapia, cosmiatría, podología).
    - **Productos prohibidos**: alimentos (salvo agua, bebidas con electrolitos y alimentos para regímenes especiales), animales, cigarrillos y vapeadores, combustibles, insecticidas, ferretería, medicamentos veterinarios, muebles, pinturas, plantas, ropa y calzado (salvo los desechables de uso neonatal u hospitalario).
    - Multa: 1 UIT.
    - No pude leer el anexo oficial, porque no viene en la edición de El Peruano.
- [V] El **Manual de Buenas Prácticas de Oficina Farmacéutica** se aprobó por la **RM 554-2022/MINSA** (27/07/2022) y lo modificaron las RM 091-2023, 1101-2023 y 810-2024: https://www.gob.pe/institucion/minsa/normas-legales/3302257-554-2022-minsa. No pude leer en el texto (escaneado) los requisitos que pone a los servicios complementarios.

### Servicios concretos
- [V] **Inyectables: permitidos con condiciones.** El Comunicado de prensa N° 016-2024 del Minsa (28/05/2024) dice que la Ley 32033 no los prohíbe y que la botica necesita **personal calificado, un área específica y el trámite ante la autoridad de salud**: https://www.saludyfarmacos.org/?p=72197. El Comunicado desmiente lo que publicó El Comercio el 24/05/2024.
- [I] El trámite es la «**Ampliación o modificación de las áreas declaradas**» ante la DIRIS/DIRESA (TUPA; plano A3 con las áreas). Ficha en gob.pe: https://www.gob.pe/81506 (no se pudo leer).
- [I] **Presión arterial y glucosa capilar**: ninguna norma consultada las menciona, ni para permitirlas ni para prohibirlas. La glucosa capilar puede chocar con «análisis clínicos / recolección de muestras», según cómo la interprete el inspector. Hay que confirmarlo con la DIRIS antes de ofrecerla. La presión arterial suele aceptarse como acto de atención farmacéutica, sin muestra.
- [I] **Vacunación**: no encontré ninguna norma vigente que autorice a las boticas privadas a vacunar. Hay proyectos de ley (PL 2522/2021-CR, PL 8488/2024-CR) que no son ley. Hasta nueva norma, se considera **no habilitada**.
- [V] Las **consultas médicas**, incluidas las virtuales (RM 734-2025), y la **toma de muestras** están **prohibidas**. Indecopi declaró barrera burocrática la prohibición anterior (enero de 2024), pero la Ley 32033 la elevó a rango de ley: https://lpderecho.pe/indecopi-declara-barreras-burocraticas-prohibiciones-vender-viveres-ofrecer-servicios-consulta-medica-boticas-farmacias/

---

## 3. Listado de medicamentos esenciales genéricos en DCI

- [V] El listado vigente es el de la **RM 220-2024/MINSA** (27/03/2024; DIGEMID la publicó el 09/04/2024), dictada en el marco del DU 005-2024. Tiene **434 medicamentos (278 principios activos)**: https://www.digemid.minsa.gob.pe/webDigemid/normas-legales/2024/resolucion-ministerial-n-220-2024-minsa/
  - Se publica en **PDF**: la resolución (`RM_220-2024-MINSA.pdf`), el anexo (`RM_220-2024-MINSA-LISTADO.pdf`) y la separata de El Peruano. **No hay Excel oficial.**
  - [I] El anexo trae DCI, concentración y forma farmacéutica (o presentación). Las columnas no se verificaron, porque DIGEMID bloquea la descarga automática.
- [V] Según la **Ley 32033**:
  - Art. 3: el listado se aprueba por RM y se actualiza **al menos una vez al año**.
  - 1.ª DCT: la RM 220-2024 **sigue vigente** hasta que se apruebe o actualice el listado.
  - **Art. 27.4 de la Ley 29459**: obliga a tener disponible **al menos el 30 % de la oferta de medicamentos de marca** en su alternativa genérica DCI del listado, **por ítem y no por unidades**, y solo sobre los productos de la propia oferta. **Las microempresas están exceptuadas.**
  - Art. 27.5: venta por esquema completo, unidad, blíster o caja.
  - Art. 5: multa de hasta 2 UIT.
  - Art. 39.3: la información comparativa de precios se exhibe ordenada **de menor a mayor precio y alfabéticamente por DCI**.
  - Art. 4 y 39.4/39.5: se informa si el producto es de un **laboratorio vinculado**.
- [I] No encontré ninguna RM de 2025 o 2026 que reemplace el listado de la RM 220-2024, aunque la ley pide actualizarlo cada año. Hay listas complementarias del PNUME (RM 182-2025 para diabetes e hipertensión, RM 393-2025 para salud mental), pero **no son** el listado del art. 3. Hay que revisar el portal de normas de DIGEMID antes de cada despliegue.
- [V] La nota de Andina sobre «31 genéricos» es de **diciembre de 2019** (DU 007-2019). Es histórica y no se aplica.

---

## 4. Estupefacientes y psicotrópicos: balance trimestral y libros

Norma: **DS 023-2001-SA** (Reglamento de Estupefacientes, Psicotrópicos y otras Sustancias Sujetas a Fiscalización Sanitaria), modificado por el DS 005-2019-SA y el DS 024-2020-SA. Texto: https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2001/DecretoSupremoN023-2001-SA.pdf

- [V] **Art. 50**: las farmacias, boticas y servicios de farmacia que manejan sustancias de las **listas IIA, IIIA, IIIB y IIIC** presentan **balances trimestrales** a DIGEMID o a la DIRIS/DIRESA.
  - El primer balance es el del trimestre que termina en marzo.
  - Al balance se adjuntan los **originales de las recetas especiales atendidas** y los vales de consumo (fórmulas magistrales con estupefacientes, art. 47).
  - **Se cierra el último día útil del trimestre y se presenta dentro de los 15 días calendario siguientes.**
  - En el local queda una copia del balance, con las copias de las recetas y los vales.
- [V] Anexo 1: el balance informa **ingresos, egresos y saldos** de cada sustancia controlada.
- [V] **Art. 47**: el Libro de Control de Estupefacientes registra proveedor, cantidad y concentración dispensadas, **prescriptor, paciente, número de receta especial y fecha**.
- [V] **Art. 44**: los libros van **foliados** y cada folio **visado** por DIGEMID o la DIRIS. Se mantienen al día y no salen del local.
- [V] **Art. 41**: las existencias deben cuadrar con el saldo del libro.
- [V] **Art. 43**: los robos y las mermas se descargan con autorización.
- [V] **Art. 46**: la documentación de las listas IIB, IIA, IVB y VI se guarda **2 años**.
- [V] El **DS 024-2020-SA** (04/08/2020) extendió a farmacias y boticas la obligación de llevar los **dos libros** (estupefacientes y psicotrópicos): https://cms.law/en/per/publication/decreto-supremo-que-modifica-el-reglamento-de-estupefacientes-psicotropicos-y-otras-sustancias-sujetas-a-fiscalizacion-sanitaria
  - DIGEMID distribuye los recetarios especiales, numerados y autocopiativos, para las listas IIA, IIIA, IIIB y IIIC.
  - [V] **Art. 36**: las recetas de las listas IIB, IVA, IVB y VI se **retienen** en el local, como recoge la presentación de DIGEMID: https://cdn.www.gob.pe/uploads/document/file/7696210/6514249-8-productos-controlados.pdf
- [V] **Formatos de DIGEMID** (https://www.digemid.minsa.gob.pe/webDigemid/formatos-y-tramites-empresa/):
  - **D3 y D4 NO son balances**: son las solicitudes de certificado oficial de importación y de exportación.
  - **D5** es la solicitud de **visación del libro** de estupefacientes y psicotrópicos.
  - **RE** es la solicitud para calificar un **registro electrónico** que reemplaza al libro. Hay un «Registro electrónico para oficinas farmacéuticas» y una declaración jurada RE.
  - Los balances trimestrales son formatos sin código: «Balance trimestral de estupefacientes» y «Balance trimestral de psicotrópicos». La DIRIS consolida las listas IIA, IIIA, IIIB y IIIC.
  - D8 es la comunicación de saldos descartables.
- [I] La DIRIS Lima Este (https://www.gob.pe/institucion/dirislimaeste/pages/110480-...) llamaría «D3» y «D4» a sus propios formatos de balance, según un resumen de búsqueda (la página dio 418). Si un cliente habla de «D3/D4», se trata de la nomenclatura local de su DIRIS. Hay que pedirle el formato.
- [I] La presentación sigue siendo en mesa de partes de la DIRIS o DIRESA (o virtual, si la DIRIS la habilitó), con el **formato firmado como declaración jurada por el Q.F.**, las recetas foliadas, una copia del balance anterior y copias de las facturas y guías de ingreso. El trámite es gratuito.
- [V] Para comprar estupefacientes se usa el FOPE actualizado, vigente desde el 01/09/2025 (COM 018-2025 de DIGEMID). No es parte del balance.

---

## 5. IGV de las tarjetas de regalo y las recargas de monedero

- [V] **Informe N.° 097-2010-SUNAT/2B0000**: https://www.sunat.gob.pe/legislacion/oficios/2010/informe-oficios/i097-2010.pdf
  - Conclusiones:
    1. La entrega de vales que **no especifican los bienes** **no está gravada con el IGV**, porque son documentos representativos de moneda (art. 2, num. 8 del Reglamento del IGV).
    2. Para Renta, el ingreso **se devenga con la venta de los bienes (canje) o cuando vence el plazo de canje**, siempre que no haya obligación de devolver el dinero.
    3. **No hay que emitir comprobante** a quien compra los vales.
    4. **Se emite el comprobante al tercero que canjea**, por la transferencia de los bienes.
- [V] **Informe N.° 0157-2015-SUNAT/5D0000**: https://www.sunat.gob.pe/legislacion/oficios/2015/informe-oficios/i157-2015.pdf
  - Aunque el vale mencione un producto, si solo representa dinero sigue sin ser bien mueble. El IGV nace en el canje.
  - Si lo pactado es que la entrega del vale **transfiere los bienes detallados**, el vale es bien mueble y su venta está gravada.
- [V] **Informe N.° 001-2022-SUNAT/7T0000** (04/01/2022): https://www.sunat.gob.pe/legislacion/oficios/2022/informe-oficios/i001-2022-7T0000.pdf
  - **Trata otra cosa**: no se pueden emitir documentos autorizados (DAE) en el rol de **adquirente** que procesa pagos con tarjetas prepago, de dinero electrónico o de regalo emitidas por entidades no financieras. Esas compensaciones tampoco están exoneradas del ITF.
  - **No dice** que la emisión de la tarjeta esté fuera del IGV, como afirma el blog de BYB Consultores. No hay que citarlo para eso.
- [V] Regla general de anticipos (art. 4 de la Ley del IGV; Informes 201-2008 y 017-2014-SUNAT/5D0000, https://www.sunat.gob.pe/legislacion/oficios/2014/informe-oficios/i017-2014-5D0000.pdf): en la venta de bienes, el **pago anticipado de un bien determinado** hace nacer el IGV por el monto cobrado, y hay que emitir comprobante al cobrar.
- [I] **Qué hacer en la suite**:
  - Una **tarjeta de regalo** o una **recarga del monedero** de la propia cadena, de monto en soles, sin bien determinado y canjeable por cualquier producto, es **dinero recibido por adelantado, no venta**. No va comprobante electrónico ni IGV al emitir o recargar. Basta un **recibo interno** (ticket no tributario) y un **pasivo** (cuenta 4xx de ingresos diferidos / anticipos de clientes).
  - En el **canje**, se emite la **boleta o factura por los bienes**, con su IGV o su exoneración. El monedero figura como **forma de pago**. Si una parte se paga con monedero, el comprobante va por el total y se informa el medio de pago.
  - Si la tarjeta **vence** sin canje y no hay que devolver el dinero, el saldo pasa a ingreso para Renta (Informe 097-2010, conclusión 2). [I] SUNAT no se pronunció sobre el IGV de un saldo vencido. La práctica habitual es no gravarlo, porque no hubo transferencia de bienes. Hay que confirmarlo con el contador.
  - **Riesgo**: si la tarjeta es «por» un producto determinado (por ejemplo, «vale por una caja de X»), puede contar como anticipo o venta gravada (Informe 157-2015).
  - Antes, la suite emitía el CPE en la recarga (commit 0628cb1, «la recarga del monedero también con impuesto inafecto»). Ese criterio **choca con el Informe 097-2010**: emitir una boleta por la recarga y otra por el canje **duplica la base** en el RVIE/PLE.

---

## 6. Copagos y convenios con EPS en la farmacia

- [V] **Informe N.° 029-2013-SUNAT/4B0000** (22/02/2013): https://www.sunat.gob.pe/legislacion/oficios/2013/informe-oficios/i029-2013.pdf
  - Los comprobantes por servicios que las entidades de salud prestan a los asegurados **por cuenta de las aseguradoras (SOAT) se emiten a nombre de la aseguradora**: factura, si tiene RUC, porque es la **usuaria**, y el gasto le da costo y crédito fiscal.
  - **Deja sin efecto** los Informes 061-2008 y 100-2010, que pedían emitir a nombre del paciente. [I] Algunas fuentes secundarias todavía citan el 061-2008 como vigente. Es un error.
- [I] Aplicado por analogía a la farmacia de convenio con una EPS o aseguradora:
  - **Factura a la EPS** por la parte que cubre, o por el total menos el copago, con su IGV.
  - **Boleta (o factura) al paciente** solo por el **copago o coaseguro** que paga en caja.
  - Son **dos comprobantes por la misma dispensación**, cada uno con su parte. La suma no debe pasar del precio total.
  - SUNAT no tiene un informe específico de farmacias ni de copagos. Hay que confirmar con el contrato de cada EPS si exige factura por atención o liquidación mensual con factura consolidada (que vaya en la factura la referencia de cada atención: autorización o código de siniestro, DNI del afiliado).
- [V] **SUSALUD – modelo TEDEF**: estándar obligatorio de tramas para facturar las prestaciones de las IPRESS privadas a las IAFAS (EPS). Tiene una tabla de **detalle de productos de farmacia** (tabla 4), validador y Mesa de Transacciones. La IAFAS reconoce los documentos de pago que traen sus tramas, y el reporte a SUSALUD es mensual, dentro de los 10 días:
  - https://cdn.www.gob.pe/uploads/document/file/7807796/6589744-reglamento-del-modelo-tedef.pdf
  - https://cdn.www.gob.pe/uploads/document/file/7807798/6589744-anexo-2_tedef-susalud_modif.pdf
  - [I] TEDEF se aplica a las **IPRESS**. Una botica independiente no es IPRESS: su relación con la EPS es **contractual** (red de farmacias afiliadas), y la EPS es quien informa a SUSALUD. Si el cliente es la **farmacia de una clínica** (IPRESS), sí entra en TEDEF.
- [I] Por **reembolso** (sin convenio), el afiliado paga todo y la boleta va **a su nombre**. Pide el reembolso a la EPS según sus lineamientos (ver los lineamientos de reembolso SUSALUD/IAFAS: https://cdn.www.gob.pe/uploads/document/file/5301244/4758416-modificacion-de-lineamiento-de-reembolso-107.pdf).
- [V] El copago variable (coaseguro) es el porcentaje del gasto de farmacia que asume el afiliado, según el plan de salud (manual del afiliado de Pacífico EPS): https://www.pacifico.com.pe/documents/28730/112029/Manual-del-afiliado/15b84a33-7f10-4315-aaa8-90d503f77cf3

---

## Impacto en la suite

### al_l10n_pe_pharmacy_digemid
1. **Código de establecimiento por local**: `CodEstab` debe ir en el almacén, el punto de venta o el local, no solo en `res.company`. Cada local tiene su propia autorización sanitaria.
2. **Exportación Excel del OPPF**: hoja `Hoja1` con columnas `CodEstab | CodProd | Precio 1 (empaque) | Precio 2 (unidad)`. `CodEstab` va como texto y los precios con 2 decimales y **con IGV**, descontando las promociones generales vigentes en el mes. Hay que validar la plantilla contra la que descarga el aplicativo antes de cerrar el formato.
3. **Universo del reporte**: solo medicamentos y biológicos con código DIGEMID **con stock y en oferta** en el mes. Se excluyen los dispositivos médicos, los productos sanitarios, los dietéticos, los agentes de diagnóstico, los radiofármacos y los gases medicinales. La primera carga del mes debe llevar **todo** el catálogo ofertado, porque reemplaza la lista. Las cargas siguientes van solo con los precios que cambiaron o los productos sin stock (`state=pending`).
4. **Recordatorio mensual** (cron o actividad) y **ventana de rectificación de 7 días hábiles** desde el envío.
5. **Listado esencial**: mantener `list_reference='RM 220-2024/MINSA'` y permitir cargar un listado nuevo (importación CSV de DCI, concentración y forma), porque el listado oficial solo sale en PDF.
   - El control del 30 % se mide **por ítem de marca ofertado con su genérico DCI disponible**, no por unidades, y se apaga si `pharmacy_microenterprise` está activo.
   - Añadir el **orden de exhibición** comparativo (de menor a mayor precio y por DCI) y el aviso de **laboratorio vinculado**.
6. **Servicios complementarios**: un catálogo de servicios con el indicador «requiere área declarada» (inyectables) y la fecha de la autorización de ampliación de áreas.
   - **Bloquear** como productos vendibles las categorías de la RM 734-2025: consultas presenciales o virtuales, toma de muestras, análisis, vapeadores, alimentos que no sean agua, electrolitos o regímenes especiales, y veterinarios.
   - Dejar la glucosa capilar y la vacunación desactivadas por defecto, con un aviso.

### al_l10n_pe_pharmacy_controlled
1. **Libros**: estupefacientes (lista IIA) y psicotrópicos (IIIA, IIIB, IIIC y demás), por local.
   - Campos del art. 47: proveedor, cantidad y concentración, prescriptor, paciente, número de receta especial y fecha.
   - Folio y visación D5, o registro electrónico «RE» calificado por DIGEMID: un número de resolución que habilite el modo electrónico.
2. **Balance trimestral** por sustancia o producto: saldo anterior, ingresos (facturas y guías), egresos (recetas) y saldo final, más el anexo de recetas foliadas.
   - Cierre el último día útil del trimestre y **vencimiento el día 15 calendario siguiente** (15/01, 15/04, 15/07, 15/10), con alerta.
   - Cuadre obligatorio con el stock (art. 41) y descargos por robo o merma solo con autorización.
   - El formato de salida debe poder configurarse por DIRIS, porque los nombres «D3/D4» son locales.
3. **Retención de receta** para las listas IIB, IVA, IVB y VI, y conservación de 2 años.

### al_l10n_pe_edi_pos
1. **Recarga de monedero o venta de tarjeta de regalo en soles**: **no** emitir CPE ni IGV. Emitir un recibo interno y registrar un pasivo (anticipo o ingreso diferido).
   - Esto contradice el criterio del commit 0628cb1 («recarga del monedero también con impuesto inafecto»). Hay que revisarlo con el contador del cliente, porque hoy puede **duplicar ventas** en el RVIE.
2. **Canje**: la boleta o factura va por los bienes, con su IGV, y el monedero aparece como **medio de pago**, sin rebajar la base.
3. **Vencimiento de saldos**: proceso para reconocer el ingreso (Renta) cuando caduca el plazo, sin CPE.
4. Si alguna tarjeta es «por producto determinado», tratarla como venta o anticipo gravado, con CPE al cobrar.

### al_pharmacy_insurance
1. **Desdoblar la dispensación en dos comprobantes**: una boleta o factura al paciente por el copago o coaseguro, y una **factura a la EPS por la parte cubierta**. El emisor y el receptor de la factura salen del convenio. La suma de los dos debe igualar el PVP.
2. **Liquidación** por atención o mensual (según el convenio), con referencia en cada línea a la autorización o siniestro, el DNI del afiliado y la receta. Ya existe `pharmacy_insurance_liquidation`: añadir la emisión de la factura consolidada a la EPS.
3. **Modo reembolso**: boleta al afiliado por el total, sin factura a la EPS.
4. **TEDEF (tabla 4 de farmacia)** solo como opción para clientes que sean IPRESS, como la farmacia de una clínica. No hace falta en una botica independiente.

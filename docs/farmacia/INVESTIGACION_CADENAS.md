# Cómo operan las cadenas de farmacias del Perú y qué software necesitan

> Insumo de [`PLAN_FARMACIA.md`](PLAN_FARMACIA.md) y complemento de [`INVESTIGACION.md`](INVESTIGACION.md). Fecha: 2026-10-19.
> Fuentes públicas (web, App Store, prensa, El Peruano, DIGEMID). No se probó ninguna app ni se visitó ninguna tienda.
> Marcas: **[V]** verificado en la fuente citada · **[I]** inferido (práctica habitual del rubro o deducción) · **[VERIFICAR]** no se encontró fuente.

---

## 0. El mercado en cifras

- **[V]** Al 30/06/2025 había 35 726 establecimientos activos. El 85,6 % son independientes y el 14,4 % pertenecen a cadenas, pero las cadenas tienen el 79,2 % de las ventas de medicamentos (2020-2024). Inkafarma y Mifarma suman el 57,3 % de los 4 238 locales de cadenas. Fuentes: [boletín DIGEMID EEFF](https://www.digemid.minsa.gob.pe/Archivos/Boletines/Establecimientos/EEFF-06-23.pdf), [Perú Retail](https://www.peru-retail.com/?p=400267), [Salud y Fármacos](https://www.saludyfarmacos.org/lang/en/boletin-farmacos/boletines/may202502/12_pe).
- **[V]** InRetail Pharma (Inkafarma y Mifarma) tiene unos 2 486 locales y opera desde diciembre de 2025 un centro de distribución automatizado de 85 000 m² en Punta Negra, con más de 2 000 tiendas abastecidas, más de 1 millón de unidades preparadas al día, pick-to-light y robots AMR. Fuentes: [Gestión](https://gestion.pe/economia/empresas/inkafarma-y-mifarma-fortalecen-suministro-con-nuevo-centro-de-distribucion-en-sur-de-lima-noticia/), [Perú Retail](https://www.peru-retail.com/farmacias-peruanas-inaugura-centro-de-distribucion-automatizado-para-inkafarma-y-mifarma/), [Infomercado](https://infomercado.pe/inkafarma-y-mifarma-inauguran-centro-de-distribucion-buscan-mejorar-margenes-y-ahorro-en-logistica/), [DIA 2024 InRetail](https://inretail.pe/Public/InRetail_DIA2024.pdf).
- **[V]** Boticas Perú tiene 365 locales (setiembre de 2026), alrededor del 8 % del mercado y un 40 % de sus tiendas en regiones. Abrió un almacén nuevo en San Juan de Miraflores (22 m de altura, unos US$ 8 M). Por El Niño subió el stock de provincias de 1,5 a 3 meses y despacha dos veces por semana. Su marca propia VitaVital pesa alrededor del 8 % de las ventas y la venta corporativa (mineras, clínicas) alrededor del 10 %. También vende en *shop-in-shop* dentro de Tiendas EFE. Fuente: [Gestión, 17/10/2026](https://gestion.pe/economia/boticas-peru-duplica-su-stock-por-el-nino-y-reorden-su-red-con-foco-en-provincias-noticia/).
- **[V]** Boticas y Salud pertenece al Grupo Deco, junto con la droguería Representaciones Deco y el Laboratorio Sherfarma, y tiene más de 150 locales. Vende por PedidosYa (2022) y tiene motorizados propios que entregan y cobran. Fuentes: [Perú Retail](https://www.peru-retail.com/?p=185779), [Computrabajo](https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-delivery-motorizado-chorrillos-part-time-boticas-y-salud-comisiones-descanso-rotativo-bonos-en-chorrillos-8c6dc9a8f9a7c4e761373e686dcf3405).
- **[V, dato de 2011]** Boticas Arcángel vendía la tarjeta Famisalud a S/ 35, con visitas médicas a domicilio, ambulancia y 20 % de descuento en sus Medicentros. Fuente: [Perú Retail](https://www.peru-retail.com/boticas-arcangel-lanza-nueva-campana/). Una nota de 2026 le atribuye 263 tiendas y 75 centros médicos **[VERIFICAR]**.
- **[VERIFICAR]** No se encontraron fuentes sobre Hogar & Salud ni Farmacias Universal. No hay que suponer nada de ellas.

**Consecuencia para el producto:** el mercado direccionable es la botica independiente o de 2 a 30 locales. Compite contra cadenas que integran droguería, laboratorio y marca propia.

---

## 1. Venta en tienda

| Tema | Hallazgo | Estado |
|---|---|---|
| Quién dispensa | La Ley 26842 (art. 33, modificado por la Ley 32033) hace al químico farmacéutico responsable de la dispensación y de la orientación al usuario. El DS 020-2024-SA (art. 49) establece que el director técnico o el QF asistente ofrece las alternativas. | [V] [Ley 32033](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2024/PERUANO_LEY_32033.pdf), [DS 020-2024-SA](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2024/PERUANO_DS_020-2024.pdf) |
| QF presente todo el horario | Es la práctica exigida al director técnico (DS 014-2011-SA). Solo se encontró en una fuente secundaria. | [I] [modelo.pe](https://modelo.pe/contrato-de-regencia-de-quimico-farmaceutico-para-botica-o-farmacia/), [VERIFICAR] artículo exacto |
| Caja separada | En las cadenas, el técnico o QF prepara la venta en el mostrador y otra persona cobra en caja. En las independientes suele cobrar la misma persona. | [I] |
| Venta fraccionada | Es **obligatorio** vender "por esquema terapéutico completo, unidad, blíster o caja, según corresponda". La unidad suelta va en un envase rotulado con establecimiento, producto, laboratorio, concentración y vía, vencimiento y lote. Del blíster se conserva la sección con el lote y el vencimiento. El usuario puede pedir ver el envase original. Los envases hospitalarios solo se manejan con área de fraccionamiento. | [V] DS 020-2024-SA, art. 48 |
| Genéricos primero | Al dispensar se ofrecen **primero los genéricos en DCI**, luego el genérico de marca y, si no hay genérico, el innovador, siempre con información de precios y sin inducir la compra. Vale **también en los canales virtuales**. Multa: 1 UIT (infracción 76). | [V] Ley 32033, DS 020-2024-SA art. 49 |
| Stock de genéricos | En cada ítem de su oferta de marca que esté en el listado del MINSA, la botica debe tener disponible el genérico en DCI en al menos el 30 %. Debe **identificar y listar** esos genéricos, y en la fiscalización puede probar el cumplimiento con el "stock previsto del mes de cada ítem". Las microempresas están exceptuadas. Multas: amonestación, luego 1 y 2 UIT (infracción 72) y 0,5 a 1 UIT si no lleva el listado (infracción 73). Listado vigente: RM 220-2024-MINSA (DU 005-2024), que se actualiza al menos una vez al año. | [V] DS 020-2024-SA art. 32-A, Ley 32033 art. 3; [VERIFICAR] si hay listado 2025-2026 |
| Empresa vinculada | La botica debe informar al vender si el producto lo fabrica o distribuye una empresa vinculada a ella (marca propia) y publicarlo en un cartel A4 o pantalla visible. El rótulo del envase lo indica (art. 39.4). Multa: 0,5 UIT por cada infracción (74 y 75). | [V] DS 020-2024-SA art. 32-B |
| Receta | Los antibióticos, antihipertensivos y antidiabéticos se venden con receta vigente, no usada y sin enmendaduras. Multa: alrededor de 1 UIT. Un estudio de 2017 encontró que el 44 % de las farmacias vendía sin receta. | [V] [Gestión](https://gestion.pe/peru/multaran-con-1-uit-a-farmacias-que-no-exijan-receta-antes-de-vender-medicamentos-que-la-requieren-minsa-noticia/), [Diario Correo](https://diariocorreo.pe/peru/venta-de-medicamentos-sin-receta-medica-sera-sancionada-con-multa-de-s5150-digemid-minsa-automedicacion-noticia/), [Andina](https://andina.pe/ingles/noticia-44-farmacias-sigue-vendiendo-medicinas-sin-receta-medica-671430.aspx) |
| Controlados | La norma es el DS 023-2001-SA (modificado por los DS 005-2019, 024-2020 y 020-2024). Las listas IIA y IIIA-C se venden con recetario especial y la dispensación está a cargo del QF. El libro de control lo visa la DIRIS o el gobierno regional. El balance es trimestral, con formatos D3 (IIA) y D4 (psicotrópicos). | [V] [presentación DIGEMID](https://cdn.www.gob.pe/uploads/document/file/7696210/6514249-8-productos-controlados.pdf), [DIRIS Lima Este](https://www.gob.pe/institucion/dirislimaeste/pages/110480-presentacion-de-balance-trimestral-de-estupefacientes-y-psicotropicos-devolucion-de-saldos-descartables-y-entrega-de-productos-controlados-por-cierre), [gob.pe visación](https://www.gob.pe/63932-solicitar-la-visacion-del-libro-de-control-de-estupefacientes-o-psicotropicos-al-gobierno-regional) |
| "Ley 31469" y "DS 024-2022-SA" | No se encontró relación con los genéricos. La norma correcta es la **Ley 32033 (20/05/2024)**, reglamentada por el **DS 020-2024-SA (25/10/2024)**. | [V] |

---

## 2. Fidelización y precios

- **Inkafarma, Inkaclub [V]:** la afiliación se hace en la app o la web. Se gana 1 Inkapunto por cada S/ 4 de compra, y 1 000 puntos dan un vale de S/ 5 (alrededor del 1,25 %) con 90 días de vigencia. Los afiliados tienen **precio diferenciado** ("el precio más bajo"), cupones y sorteos. Los beneficios valen también en Jorsa de la Selva y en socios de Intercorp. [inkafarma.pe/programa-inkaclub](https://inkafarma.pe/programa-inkaclub), [legales](https://inkafarma.pe/legales).
- **Mifarma, "Monedero del Ahorro" [V]:** la app muestra los "puntos-dinero" acumulados y el ahorro, y ofrece cupones personalizados. Hay reseñas que se quejan de cupones que no se aplican a algunos productos. [App Store](https://apps.apple.com/app/id1582018387). *Ojo:* "Monedero del Ahorro" es también el nombre del programa de la cadena mexicana Farmacias del Ahorro. En el Perú lo usa **Mifarma**, no Inkafarma.
- **Programa de apoyo al paciente de Inkafarma [V, existe; mecánica VERIFICAR]:** tiene términos publicados ([enlace](https://inkafarma.pe/atencion-clientes/terminos-y-condiciones-apoyo-al-paciente-inkafarma)), pero la página no se pudo leer. **[I]** Son programas de laboratorios para pacientes crónicos (un descuento por compra recurrente, o "lleva N y paga N-1"), identificados con DNI y receta.
- **Convenios EPS y aseguradoras [I]:** la cadena factura a la aseguradora el copago o la cobertura, y la venta corporativa (Boticas Perú, alrededor del 10 %) se hace con crédito. **[VERIFICAR]** no hay convenios públicos detallados.
- **Límite legal [V]:** el DS 020-2024-SA (art. 55) prohíbe en las instalaciones "canjes de envases, rifas, sorteos, premios, ofertas u otras actividades que fomenten el uso irracional" de medicamentos. El art. 46.8 de la Ley 29459 prohíbe dar incentivos al QF o al personal para que empujen marcas en desmedro de los genéricos. **Diseño:** puntos y cupones solo sobre productos que no son medicamentos de receta, o sobre el total con exclusiones configurables. Sin comisiones por marca para el QF. Los sorteos de Inkafarma van por la web (inkafarmatepremia.com).

---

## 3. Canal digital

- **[V]** La app de Inkafarma hace delivery con seguimiento en tiempo real y cobra contraentrega (efectivo o tarjeta). La cobertura en Lima es parcial. [App Store](https://apps.apple.com/us/app/-/id1418660567)
- **[V]** El delivery *express* de Inkafarma tarda entre 30 y 45 minutos en 7 distritos de Lima (2023). [Perú Retail](https://www.peru-retail.com/inkafarma-atendera-el-50-del-delivery-express-en-lima-para-el-2024/)
- **[V]** Desde octubre de 2024 Inkafarma tiene 38 tiendas con atención y delivery las 24 horas. [Perú Retail](https://www.peru-retail.com/inkafarma-implementa-servicio-de-atencion-y-delivery-24-7-en-tiendas-seleccionadas-aqui-la-lista/)
- **[V]** Las ventas digitales de las farmacias de InRetail crecieron 24 % en 2023. [Reporte de Sostenibilidad 2023](https://www.inretail.pe/Public/Reporte%20de%20Sostenibilidad%202023%20InRetail.pdf)
- **[VERIFICAR]** No se encontraron fuentes sobre recojo en tienda, delivery programado, receta subida por foto, stock por tienda en la web ni WhatsApp. **[I]** Las cadenas suelen tenerlos. Las independientes venden por WhatsApp y PedidosYa o Rappi.
- **[V] Obligación:** el canal virtual también debe ofrecer el genérico primero y mostrar precios (DS 020-2024-SA art. 49). La publicidad de productos sin receta debe incluir la DCI, la concentración y la forma farmacéutica (art. 39.1 de la Ley 29459). Los productos con receta no se publicitan al público.

---

## 4. Servicios farmacéuticos

- **[V] Lo que está prohibido** dentro de la botica: consultas médicas, consultorios, análisis clínicos, **toma de muestras** para laboratorio, campañas médicas, degustaciones y locutorios (DS 020-2024-SA art. 55, Ley 29459 art. 46.6). La multa es la infracción del anexo. **Por eso, los test rápidos con muestra y la "consulta médica" en la botica no son viables.** Arcángel tiene centros médicos **aparte**.
- **[V] Lo que está permitido:** "servicios sanitarios complementarios" con un **área específica e implementada**, personal calificado, comunicación a la DIRIS o ARM y bajo responsabilidad del director técnico (art. 55). **[I]** En la práctica: presión arterial, glucosa capilar e inyectables (con área de inyectables) y vacunación (con autorización del vacunatorio) **[VERIFICAR la lista que permite la RM]**.
- **[V]** La Ley 29459 (art. 32) exige Buenas Prácticas de Dispensación y de **Seguimiento Farmacoterapéutico**. La certificación de buenas prácticas de oficina farmacéutica cubre almacenamiento, dispensación, farmacovigilancia y, según el caso, seguimiento (DS 014-2011-SA art. 126, según un resumen de DIGEMID).
- **[V parcial]** Inkafarma y Mifarma hacen campañas de vacunación ([vphayuda](https://vphayuda.com/latam/pe-vacunacion/)) y publican contenido sobre el esquema de vacunación ([blog](https://inkafarma.pe/blog/inkafarma/salud/esquema-de-vacunacion-infantil-en-peru)). InRetail mencionó un proyecto de telemedicina en 2019. **[VERIFICAR]** no se encontraron precios ni el sistema de citas.

---

## 5. Operación y logística

| Práctica | Evidencia |
|---|---|
| CD central y despacho programado a tiendas (2 veces por semana a provincias) | [V] Boticas Perú, InRetail |
| Cobertura de stock por región (de 1,5 a 3 meses) | [V] Boticas Perú |
| Reposición por mínimos y máximos, y traslados entre locales | [I] |
| FEFO y lote en la unidad fraccionada | [V] el lote y el vencimiento se conservan hasta la venta (art. 48). FEFO [I] |
| Alertas y retiro de lotes: DIGEMID **inmoviliza a nivel nacional** el lote observado (p. ej., Alerta 121-2025, metformina 850 mg) | [V] [Alerta 121-25](https://www.digemid.minsa.gob.pe/Archivos/Alertas/2025/ALERTA_121-25-2.pdf), [Alerta 111-25](https://www.digemid.minsa.gob.pe/Archivos/Alertas/2025/ALERTA_111-25.pdf) |
| Almacenamiento: la RM 132-2015 (BPA) **no aplica** a farmacias y boticas, que siguen con la RM 585-99-SA/DM | [V] [RM 132-2015](https://www.minsa.gob.pe/Recursos/OTRANS/08Proyectos/2022/RM%20132-2015-MINSA%20BUENAS%20PR%C3%81CTICAS%20DE%20ALMACENAMIENTO.pdf), [SNI](https://sni.org.pe/incorporan-disposiciones-complementarias-transitorias-a-la-r-m-n-132-2015-minsa-que-aprobo-el-documento-tecnico-manual-de-buenas-practicas-de-almacenamiento-de-productos-farmaceuticos-dispo/) |
| Canje de vencidos con el laboratorio o la droguería, bonificaciones, inventarios cíclicos, cadena de frío con registro de temperatura | [I] |
| Precios por zona o formato (Express, 24 h, provincias) | [I] |

---

## 6. Regulación obligatoria (resumen)

| Obligación | Norma | Sanción | Software |
|---|---|---|---|
| Reportar precios al **Observatorio** (SNIPPF) con el **código de producto de DIGEMID**: el precio de la oferta en existencia, actualizado cuando el precio cambia o entra un producto nuevo. La frecuencia la fija la directiva. Se hace por el aplicativo web, no en papel. | DS 014-2011-SA art. 30 (modificado por el DS 020-2024-SA), RM 040-2010 y RM 341-2011 (Directiva 176) | 0,5 UIT si se reporta fuera de plazo (inf. 66); 1 UIT o cierre de 30 días si es incompleto (inf. 68) | Exportación con el código DIGEMID [V]; frecuencia mensual [V en resoluciones DFAU](https://www.digemid.minsa.gob.pe/Archivos/Resoluciones/DFAU/2021/RD_DFAU_035_2021.pdf); formato del archivo [VERIFICAR] |
| 30 % de genéricos y su listado | DS 020-2024-SA art. 32-A | hasta 2 UIT | Cruce marca → DCI con stock previsto del mes |
| Ofrecer alternativas con precio en todos los canales | art. 49 | 1 UIT | Lista ordenada por precio en el TPV y la web |
| Exhibir la lista comparativa de precios por DCI, de menor a mayor precio | Ley 29459 art. 39.3 | Código del Consumidor | Reporte imprimible o pantalla |
| Informar y publicar la empresa vinculada | art. 32-B | 0,5 + 0,5 UIT | Marca en el producto, aviso en el TPV y cartel A4 |
| Venta fraccionada con rótulo | art. 48 | — | Presentaciones y etiqueta de unidad |
| Receta (antibióticos y otros) y libro de recetas | DS 014-2011-SA | alrededor de 1 UIT | Bloqueo en el TPV y libro |
| Controlados: receta especial, libro visado y balance trimestral | DS 023-2001-SA | — | Libros y balance |
| QF director técnico y horario | DS 014-2011-SA | — | Turnos |
| Alertas e inmovilización de lotes | DIGEMID | — | Bloqueo de lote |
| Farmacovigilancia (NotiMED) | Ley 29459 | — | RAM |
| Libro de reclamaciones (virtual si hay web) y precio visible | Ley 29571 | INDECOPI | `al_l10n_pe_complaints_book` |
| Boleta y factura electrónica (SUNAT); IGV exonerado en oncológicos, VIH y diabetes | SUNAT | — | EDI |
| Registro sanitario vigente del producto | DS 016-2011-SA | — | Validación en la recepción |

---

## 7. Diferenciadores imitables con software

1. Precio de socio por DNI con puntos o monedero, como Inkaclub y Monedero. Mifarma tiene reseñas negativas por cupones que no se aplican: la regla de elegibilidad tiene que ser clara.
2. Stock por tienda visible para el vendedor ("lo tienen en el local X") y traslado o reserva inmediata.
3. Pedido web o WhatsApp con delivery propio y cobro contraentrega, más recojo en tienda.
4. Reposición automática desde el almacén por mínimos y máximos y cobertura por región.
5. Alertas DIGEMID convertidas en el bloqueo inmediato del lote en todas las tiendas.
6. Programa de crónicos: recordatorio de recompra según la posología, por SMS o WhatsApp.
7. Servicios complementarios con cita y registro (presión, glucosa, inyectables).
8. Marca propia o venta corporativa a crédito, como Boticas Perú.

---

## 8. Funcionalidades recomendadas (priorizadas)

⚖ = obligación legal. Esfuerzo: B bajo · M medio · A alto. La última columna dice si la suite actual (`OL-HEALTH`) ya lo cubre, según su README.

| # | Funcionalidad | ⚖ | Impacto | Esfuerzo | Suite |
|---|---|---|---|---|---|
| 1 | Exportación al Observatorio con código DIGEMID, disparada por cambio de precio o producto nuevo, con control de "no reportado" | ⚖ | Alto | B | ya existe en `al_l10n_pe_pharmacy_digemid`; validar el formato real del aplicativo |
| 2 | Cumplimiento del 30 % de genéricos por ítem con el listado del MINSA importable y la evidencia del "stock previsto del mes" | ⚖ | Alto | M | ya existe; falta un importador anual del listado RM |
| 3 | TPV con alternativas: genérico DCI → genérico de marca → innovador, con precio y sin inducir, también en la web | ⚖ | Alto | M | existe en el TPV; **falta en `website_sale`** |
| 4 | Venta por caja, blíster o unidad con etiqueta rotulada (lote y vencimiento) | ⚖ | Alto | B | ya existe; revisar que la etiqueta incluya los 6 datos del art. 48 |
| 5 | Receta obligatoria por condición de venta, controlados con libro y balance trimestral | ⚖ | Alto | M | ya existe |
| 6 | **Empresa vinculada**: marca en el producto, aviso en el TPV, cartel A4 imprimible y rótulo | ⚖ | Medio | B | **nuevo** (inf. 74 y 75) |
| 7 | Lista comparativa de precios por DCI (menor a mayor, alfabética) para exhibir | ⚖ | Medio | B | parcial (lista por DCI) |
| 8 | Alertas DIGEMID → bloqueo de lote multitienda y acta | ⚖ | Alto | B | ya existe en `al_pharmacy_stock`; añadir propagación multialmacén |
| 9 | Fidelización por DNI: precio de socio, puntos o monedero, cupones con **exclusión de medicamentos de receta** y sin incentivos al QF | ⚖ (límites) | Alto | M | **nuevo** (sobre `loyalty` de Odoo) |
| 10 | Reposición por mínimos y máximos desde el CD, cobertura por región y traslados entre locales | | Alto | B | Odoo nativo; configurar en `al_industry_pharmacy` |
| 11 | Stock por tienda en el TPV y la web, reserva y recojo en tienda | | Alto | M | **nuevo** |
| 12 | Pedido por WhatsApp o web con receta adjunta validada por el QF y delivery contraentrega | | Medio | A | **nuevo** |
| 13 | Servicios complementarios: área registrada, cita, registro de presión y glucosa, inyectables; **sin toma de muestras ni consulta** | ⚖ (límites) | Medio | M | `al_pharmacy_care` (en curso) |
| 14 | Pacientes crónicos y programas de laboratorio: recompra por posología, descuento N+1 y recordatorios | | Medio | M | **nuevo** |
| 15 | Canje de vencidos con la droguería, bonificaciones y cadena de frío | | Medio | B | parcial en `al_pharmacy_stock` |

**Pendientes de verificar antes de construir:** el formato y la frecuencia exacta del aplicativo del Observatorio para boticas (Directiva 176); si hay un listado de genéricos posterior a la RM 220-2024; la lista de servicios complementarios permitidos (RM del art. 35); y el artículo del DS 014-2011-SA sobre la presencia del QF.

# Farmacias y boticas — investigación previa

> Insumo del plan [`PLAN_FARMACIA.md`](PLAN_FARMACIA.md). Fecha: 2026-10-18.
> Tres frentes: módulos de farmacia en Odoo Apps, software del mercado
> (Perú, Latinoamérica e internacional) y normativa peruana vigente.
> Todo sale de páginas públicas: nada se probó en una demo. **[VERIFICAR]**
> marca lo que no se pudo confirmar en una fuente oficial.

---

## 1. Módulos de farmacia en Odoo Apps (17.0–20.0)

Se revisaron 26 fichas; 21 entran en la tabla. Ninguno cubre todo y
**ninguno está adaptado a Perú** (DIGEMID, Observatorio, controlados).

| Módulo (autor, serie) | Precio | Lo más relevante |
|---|---|---|
| `pharmacy_retail` (Odoo S.A., 19.0) | OEEL-1 | Paquete de industria: lotes y vencimientos; la ficha no detalla más. Es el modelo de `al_industry_pharmacy`. |
| `eb_pos_pharmacy_management` (echoBitz, 20.0) | 110,86 € | Receta con estados y bloqueo del cobro sin receta; sustitutos; alergias e interacciones; paciente con historial y recompra; FEFO y lote por código de barras; descuento por vencimiento cercano; posología 1-0-1; trabajo sin conexión. |
| `pharma_core` (Samy_Sensei, 19.0) | 109,99 € | Sustitutos por principio activo ordenados por precio; receta con vencimiento y dispensación parcial; interacciones en 4 niveles con bloqueo; bloqueo de lote vencido y alergia; seguro con cobertura y topes. |
| `cerevantix_pos_flexi_pharmacy` (19.0) | 133,26 € | **Precio por empaque (tableta / tira / caja) con selector al cobrar**; receta solo como aviso; distintivo «por vencer». |
| `hh_select_lot_multi_uom` (19.0) | 103,39 € | Cambio de unidad en el TPV con precio y stock; lote GS1; varios lotes por línea; FEFO; devolución por lote. |
| `pharmacy_management_1ts` (19.0) | 86,42 € | *Schedules* (H/H1/X/OTC); **ubicación en estante**; médicos con ventas por médico; precio por lote; aviso de **licencia sanitaria** propia y del proveedor; stock sin movimiento. |
| `pharmacy_management_system` (Webbycrown, 18.0) | gratis | Mapeo marca → genérico; reglas de alerta (vencimiento, stock, retiro de lotes, controlados); registro de controlados; multisucursal. |
| `es_farmacia_stock` (Pokutsoft, 19.0, España) | 119,60 € | Código nacional; **libro de estupefacientes con saldo**; baja de vencidos; pedido sugerido por mínimos y máximos. |
| `iet_controlled_medicines_eg` (19.0, Egipto) | 89 € | Lista oficial de controlados; licencias y cupos del cliente; declaración semanal en Excel; incidentes. |
| `viyug_pos_gs1_2d` (19.0) | 79 € | GS1 DataMatrix; **retiro de lotes (recall)**; rebaja por días al vencimiento; etiquetas GS1. |
| `aminitech_hms_app_pharmacy` (19.0) | 42,93 € | Farmacia hospitalaria: ATC, verificación por código de barras, **segundo verificador en controlados**. |
| `pos_pharmacy_management` (Webkul), `bi_`, `scs_`, `akr_`… | 89–178 € | Variantes de lo mismo: sal o composición, sustitutos, médico en el comprobante, ficha clínica del producto. |
| `pos_doctor_commission` (Webkul) | 221 € | Comisión al médico. |

**Lo común** (≥ 5 módulos): médico prescriptor, receta con estados,
sustitutos, lote y vencimiento con FEFO, principio activo, ficha clínica,
paciente con alergias, alertas de vencimiento y stock.
**Lo raro**: venta por blíster (1 módulo), ubicación en estante (1),
controlados con libro (3), recall (2), interacciones (4).

URLs: `https://apps.odoo.com/apps/modules/<serie>/<nombre_técnico>`;
búsquedas en `…/browse?series=19.0&search=pharmacy` (y `medicine`, `farmacia`).

## 2. Software del mercado

### Perú

| Producto | Lo que declara |
|---|---|
| [FarmaTec](https://farmatec.org/) | +18 000 productos del catálogo DIGEMID con IFA; alertas 90/60/30 días y FEFO; **unidad / blíster / caja**; libro de psicotrópicos y recetas retenidas; Observatorio; traslados y mermas; facturas de compra con IA. S/ 29,90–74,90 al mes. |
| [Farmasis](https://farmasis.site/) | Principio activo y similares; **4 precios (caja, blíster, unidad, local)**; alertas 1/3/6 meses; sugerencia de compra; traslados entre RUC con factura; puntos; archivo DIGEMID y precios; controlados; Yape/Plin. |
| [Oxerva](https://oxerva.com.pe/software/sistema-para-farmacias-y-boticas/) | Sustitutos y complementarios; aviso «requiere receta»; caja y fracción en un comprobante; faltantes y ventas perdidas. |
| [InfoFarma](https://infofarmaperu.com/) | Recetas y balance de controlados; Observatorio (formato aparte para droguerías); recepción con inspección organoléptica; faltantes por sucursal. |
| [FarmaSystem](https://www.farmasystem.pe/) | Componente; caja / blíster / unidad por lote; reportes DIGEMID; RUC y DNI; comisiones. |
| [Adiasoft](https://adiasoft.com/sistema-farmaceutico) | Kardex por lote, rotura de blíster, registro sanitario y código DIGEMID, ABC, OCR, delivery, libro de reclamaciones. |
| [PANCA](https://www.panca.pe/sistema-para-farmacias/) | **Listas de precios por convenio (empresas, EPS, seguros)**; traspasos. |

### Internacional
Farmatic y Nixfarma (España): receta electrónica, base de datos del colegio
(Bot Plus), pedidos a mayoristas (Fedicom), SPD y formulación magistral.
PioneerRx, Liberty y McKesson (EE. UU.): cobro a aseguradoras, sincronización
de medicación, multitienda. Ningún ERP (SAP B1, Odoo) tiene un vertical
peruano publicado.

### Conclusión
- **Imprescindible para competir en Perú:** CPE en el TPV, lotes con FEFO y
  alertas, **venta caja / blíster / unidad con precio propio**, búsqueda por
  DCI, multisucursal, Observatorio, libros de controlados, catálogo DIGEMID.
- **Diferencial (nadie lo publica):** bonificaciones de compra («12+1»),
  devolución al proveedor por vencimiento, convenios con EPS, interacciones,
  cadena de frío, cumplimiento del 30 % de genéricos, recall por alerta
  DIGEMID.
- Un informe de un tercero dice que el TPV Community «no vende lotes»: **falso
  en Odoo 19** (`pos.pack.operation.lot` en `point_of_sale`, CE).

## 3. Normativa peruana (qué exige → qué hace el software)

Fuentes leídas: Ley 32033 (2024), DS 020-2024-SA, DS 008-2025-SA, Manual
BPOF (RM 554-2022/MINSA), DIGEMID «Productos controlados» (2024), Comunicados
016-2023 y 002-2025. El DS 014-2011-SA original es un escaneo sin texto: se
cita por sus modificaciones.

| Tema | Exige | El software |
|---|---|---|
| Establecimiento | Farmacia (propiedad de un Q.F.) o botica; **un director técnico Q.F.** presente todo el horario; libros de recetas, estupefacientes, psicotrópicos y **ocurrencias** (papel o digital, correcciones visibles). | Libros digitales solo-ampliables con correlativo; turnos de Q.F. y reemplazos; alerta si no hay Q.F. en turno al dispensar con receta [VERIFICAR si debe bloquear]. |
| Almacenamiento (BPOF 7.5.1) | Recepción con lote, vencimiento, RS, cantidades y estado del envase; **temperatura (termohigrómetro) y cadena de frío 2–8 °C** con registro diario y plan de contingencia; inventario anual; aviso de vencimientos; FIFO/FEFO; devoluciones con causa y verificación del Q.F.; bajas y destrucción. | Recepción con datos obligatorios; estados de lote; registros ambientales con alerta y acción correctiva; ubicaciones de devoluciones y bajas; acta de destrucción. |
| Dispensación (7.5.2) | Según la condición de venta del RS; no atender recetas vencidas; anotar entregas parciales y alternativas; **etiqueta en la venta fraccionada** (producto, laboratorio, concentración, vía, lote, vencimiento). | Bloqueo por condición de venta; receta con dispensación parcial; etiqueta del fraccionado. |
| Farmacovigilancia (7.5.3) | Registro de sospechas de RAM con correlativo; graves en 24 h, otras en 15 días [VERIFICAR 15 vs 72 h]; NotiMED (Comunicado 002-2025). | Registro de SRA con plazos y campos de NotiMED. |
| Observatorio (art. 30 DS 014, Ley 29459 art. 28-A) | Informar precios de la oferta en existencia y actualizarlos al cambiar; código de producto DIGEMID; infracciones 66 y 68. Periodicidad para boticas [VERIFICAR]; carga web, ¿plantilla Excel? [VERIFICAR]. | Código del Observatorio; historial de precios; «pendiente de informar»; exportación; tablero por local. |
| Controlados (DS 023-2001-SA y mod.) | Listas IIA–VI; **receta especial** (original + 2 copias, 3 días, datos del art. 23); recetas retenidas (IIB, IVA, IVB, VI); **balance trimestral** con recetas foliadas ante la DIRIS (≈ día 15 del mes siguiente [VERIFICAR art. 50]); saldos descartables (D7); sin delivery; cannabis con RENPUC. | Lista de fiscalización por producto; validación de la receta especial; libros automáticos; balance trimestral; bloqueo en delivery. |
| Genéricos (Ley 32033, art. 32-A) | **Ofrecer primero genéricos DCI** con precios, también en web; **≥ 30 % por ítem** del listado MINSA (RM 220-2024 [VERIFICAR actualización]) con lista marca → genérico; aviso A4 de empresas vinculadas; comparación de precios por DCI; venta por esquema, unidad, blíster o caja. | Alternativas DCI ordenadas por precio en TPV y web; reporte del 30 %; marca «vinculada»; lista de precios por DCI. |
| Alertas DIGEMID | Inmovilizar y retirar lotes falsificados o de baja calidad. | Registro de alertas → bloqueo de lotes; trazabilidad hasta el cliente. |
| SUNAT | Medicamentos oncológicos y VIH (Ley 27450) y diabetes (Ley 28553) inafectos/exonerados según listas (DS 023-2016-SA, DS 004-2016-SA [VERIFICAR posteriores]); sin percepción ni SPOT [VERIFICAR]. | Afectación de IGV por producto desde las listas. |
| Consumidor y delivery (7.5.5) | Libro de reclamaciones físico y virtual; delivery solo desde establecimiento autorizado, con cadena de frío, conformidad firmada y sin controlados. | Ya existe `al_l10n_pe_complaints_book`; validación de receta en la web; hoja de reparto. |

Los PDF descargados (manual BPOF, leyes) quedaron en el scratchpad de la
sesión del 18/10/2026; las URLs oficiales están en las fuentes de cada tema.

### Fuentes oficiales
- [Ley 32033](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2024/PERUANO_LEY_32033.pdf) · [DS 020-2024-SA](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2024/PERUANO_DS_020-2024.pdf) · [DS 008-2025-SA](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2025/DS_008-2025-SA.pdf)
- [Manual BPOF, RM 554-2022/MINSA](https://cdn.www.gob.pe/uploads/document/file/3453401/Documento%20T%C3%A9cnico%3A%20Manual%20de%20Buenas%20Pr%C3%A1cticas%20de%20Oficina%20Farmac%C3%A9utica.pdf) · [RM 810-2024/MINSA](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2024/PERUANO_RM_810-2024-MINSA.pdf)
- [DIGEMID, productos controlados](https://cdn.www.gob.pe/uploads/document/file/7696210/6514249-8-productos-controlados.pdf) · [DIRIS Lima Este, balance trimestral](https://www.gob.pe/institucion/dirislimaeste/pages/110480-presentacion-de-balance-trimestral-de-estupefacientes-y-psicotropicos-devolucion-de-saldos-descartables-y-entrega-de-productos-controlados-por-cierre)
- [Comunicado 016-2023 (Observatorio)](https://www.digemid.minsa.gob.pe/Archivos/Comunicados/2023/COM_016-2023.pdf) · [Comunicado 019-2023](https://www.digemid.minsa.gob.pe/Archivos/Comunicados/2023/COM_019-2023-v2.pdf) · [RD DFAU 018-2021](https://www.digemid.minsa.gob.pe/Archivos/Resoluciones/DFAU/2021/RD_DFAU_018_2021.pdf)
- [Comunicado 002-2025 (NotiMED)](https://www.digemid.minsa.gob.pe/Archivos/Comunicados/2025/COM_002-2025.pdf) · [Alerta 105-2025](https://www.digemid.minsa.gob.pe/Archivos/Alertas/2025/ALERTA_105-25.pdf) · [Alerta 47-2025](https://www.digemid.minsa.gob.pe/Archivos/Alertas/2025/ALERTA_47-25.pdf)
- [Informe SUNAT 160-2016](https://www.sunat.gob.pe/legislacion/oficiosAd/2016/informes/2016-INF-160-5D1000.pdf)

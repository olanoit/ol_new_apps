# Análisis del partner ITGRUPO (localización peruana)

Análisis del 27/10/2026 de lo que muestra ITGRUPO en su sitio
([itgrupo.pe](https://itgrupo.pe)) y en su canal de YouTube
([@itgrupo4501](https://www.youtube.com/@itgrupo4501/videos)), comparado
con la suite `ol_new_apps` y con lo que trae Odoo 19 (Community y
Enterprise).

## Fuentes revisadas

- Sitio: inicio y las siete páginas de soluciones (cadena de suministro,
  venta y distribución, gestión humana, contable financiera, fabricación,
  clínica, mantenimiento y transporte). El sitio solo da listas de
  funcionalidades; no publica fichas técnicas ni módulos en Odoo Apps.
- Canal: los **30 videos** publicados (2020-2026). Se leyeron las
  transcripciones automáticas completas. Los más vistos son los de
  contabilidad v13/v15 (6 037 vistas), mantenimiento v13 (4 123) y
  backoffice v13 (3 259).
- Lo que muestran sobre todo es Odoo 13 y 15. La única demo reciente de
  localización es la de planillas en Odoo 17 (09/2024). Desde 2024 el canal
  se centra en la solución clínica.

## Conclusión

En localización fiscal pura (PLE, SIRE, CPE, detracciones, retenciones,
percepciones, planillas, T-Registro, PLAME) **la suite ya cubre todo lo que
ITGRUPO muestra, y bastante más** (SIRE, letras, cobranza, tesorería,
factoring, NIIF 16, pasarelas peruanas, TPV con CPE, farmacias, obra).

Donde ITGRUPO sí va por delante es en cuatro frentes, que son los que
proponemos desarrollar:

1. **Costos de producción y kardex por almacén** (su producto estrella).
2. **Cierre contable peruano**: hoja de trabajo, asientos de cierre y
   apertura, EEFF por centro de costo.
3. **Solución clínica (HIS)**, que encaja con la suite de farmacias de
   OL-HEALTH.
4. **Flota y mantenimiento con documentos peruanos** (SOAT, revisión
   técnica, licencias) y **BI externo**.

## Cobertura comparada

| Funcionalidad que muestra ITGRUPO | Nuestra suite | Estado |
|---|---|---|
| Libros electrónicos PLE (5.1, 6.1, 8.1, 8.2, 14.1, 1.1/1.2, 3.x) | `al_l10n_pe_ple` (incluye 3.17, 3.18, 7.1, 8.4/8.5, 14.4) | Cubierto |
| «Corrector de PLE» para errores del validador | Validación al publicar en `al_l10n_pe_sire` y `al_l10n_pe_ple` | Cubierto (otro enfoque) |
| Percepciones y recibos por honorarios | `al_l10n_pe_perception`, `al_l10n_pe_fourth_category` | Cubierto |
| Tipo de cambio SUNAT automático | `al_l10n_pe_currency` | Cubierto |
| Consulta RUC/DNI | Integración Decolecta | Cubierto |
| Canje de letras | `al_l10n_pe_account_letter` | Cubierto |
| Cuentas corrientes por fecha contable/documento, vencidas por tramos | `al_l10n_pe_collection`, informes de antigüedad de EE | Cubierto |
| Flujo de efectivo método directo | 3.18 en `al_l10n_pe_ple` | Cubierto |
| Caja chica, extractos, conciliación | `al_l10n_pe_cash_fund`, `al_l10n_pe_bank_statement_import` | Cubierto |
| Activos fijos y formato 7.1 | `account_asset` (EE) + 7.1 en `al_l10n_pe_ple` | Cubierto |
| Gastos vinculados a importación | `al_l10n_pe_import_dua` + `stock_landed_costs` | Cubierto |
| **Hoja de trabajo formato 1 y 2** (8 y 10 columnas: naturaleza/función) | — | **Hueco** |
| **Asiento de cierre y apertura automático** | — (los informes cuadran con o sin cierre) | **Hueco** |
| **EEFF por centro de costo** | Analítica nativa, sin EEFF PE por centro | **Hueco parcial** |
| Presupuestos de ingresos/gastos, por proyecto, con OC/OV | `account_budget` (EE); en obra, `al_construction_planner_budget` | Cubierto fuera de obra solo con EE |
| Planilla: PLAME (.rem, .jor, .snl, .toc), AFPnet, asiento, 5.ª, CTS, gratificación, liquidación, utilidades, préstamos, adelantos | `al_hr_pe*` | Cubierto |
| Boleta por correo con token y confirmación de recepción | `al_hr_pe_reports` (token HMAC) | Cubierto |
| Plantillas de carga masiva (empleados, contratos, tareo, inputs) | `al_hr_pe_import` | Cubierto |
| **Legajo digital con vencimientos y alertas** | `documents_hr` (EE) sin alertas de vencimiento PE | **Hueco parcial** |
| Biométricos y modo kiosco | Kiosco nativo; biométricos en Extendrix (fuera del repo) | **Hueco en la suite** |
| **Kardex valorizado con costo promedio por almacén** | `ol_stock_kardex_pe` avisa que el costo por almacén es aproximado | **Hueco principal** |
| **Revalorizar movimientos pasados y cierre mensual de almacén** | — | **Hueco** |
| Importador de saldos iniciales de inventario | Importación nativa de quants | Cubierto (nativo) |
| Tipos de operación de devolución separados, «fecha kardex» | `ol_stock_kardex_pe` | Cubierto |
| **Costeo de OP: mano de obra (costo hora desde la planilla), gastos indirectos prorrateados, máquinas** | `al_mrp_piece_costing` (solo órdenes de corte) | **Hueco** |
| BI en Power BI sincronizado (ventas 360, gastos por centro de costo, stock semanal) | Tableros nativos (`al_l10n_pe_dashboard`) y `al_mcp_server` | **Hueco parcial** |
| Mantenimiento de flota: SOAT, revisión técnica, licencias, combustible, repuestos | `fleet`/`maintenance` nativos sin capa PE | **Hueco** |
| Toma de pedidos en campo con rutas y geolocalización | — | **Hueco** |
| Despacho: carga por vehículo y documentos automáticos | Guías en `al_l10n_pe_stock_transfer` | Hueco parcial |
| Solución clínica HIS (citas web, triaje, HC con CIE-10/11, laboratorio, radiología, portal del paciente) | Solo farmacia (`al_pharmacy_*`) | **Hueco** |
| Mantenimiento de equipos por serie con paquetes de repuestos, preventivos y requerimiento de compra | `maintenance` nativo + `purchase_request` | **Hueco** |
| Back orders de compra/venta y saldos por almacén para vendedores | Informes nativos | Cubierto (nativo) |

Notas sobre lo que ITGRUPO **no** muestra en ningún video: SUSALUD,
SITEDS/IAFAS, DICOM/PACS funcionando (HL7 solo como «se puede integrar»),
SIRE, retenciones o detracciones automáticas, pasarelas peruanas concretas,
TPV con CPE. El video «Hospitalización y cirugía» repite el audio del portal
del paciente, así que no hay contenido sobre hospitalización.

## Propuesta de desarrollo

Por prioridad (impacto comercial frente a esfuerzo).

### 1. Costo promedio por almacén y cierre de inventario (OL-INVENTORY)

- **Por qué:** es el argumento central de ITGRUPO («Odoo solo maneja un
  costo general; en Perú el kardex valorizado es por almacén»).
  `ol_stock_kardex_pe` hoy avisa de que el costo por almacén es aproximado
  (`wizards/kardex_report_wizard.py:118`).
- **Alcance:**
  - costo promedio ponderado por producto y almacén, usado en las salidas y
    en el 13.1;
  - proceso «revalorizar movimientos» desde una fecha (facturas de compra
    tardías, costos de producción corregidos), con permiso propio;
  - cierre mensual de almacén que bloquea movimientos y revalorizaciones del
    periodo cerrado.
- **Riesgo:** Odoo 19 rehízo la valorización (valor en `stock.move`). Antes de
  diseñar, trazar `stock_account` v19 y decidir si el costo por almacén va
  como capa propia de valorización o como cálculo del kardex con asiento de
  ajuste.

### 2. Costeo de órdenes de producción (OL-INVENTORY)

- **Por qué:** segundo video más visto de los recientes (1 360 vistas).
  Tenemos `al_mrp_piece_costing` (órdenes de corte) y la suite de obra, pero
  no el costeo general de OP.
- **Alcance:**
  - mano de obra con el costo hora que sale de la planilla cerrada
    (`al_hr_pe`) y tareo importable por OP;
  - gastos indirectos prorrateados entre OP del periodo a partir de asientos
    publicados, por cantidad, peso o volumen;
  - costo de máquina por hora;
  - análisis de costo de la OP y reportes por centro de producción y por
    elemento del costo, con los asientos de consumo y producción.
- Sobre `mrp_account` y, si hay EE, `mrp_workorder` (que ya trae costo de
  centro de trabajo y de empleado).

### 3. Cierre contable peruano (OL-ACCOUNTING)

- **Alcance:**
  - hoja de trabajo formato 1 y 2 (saldos, balance, resultados por
    naturaleza y por función), en pantalla y Excel;
  - asientos de cierre del ejercicio (cancelación de 9 contra 79, de 6 y 7,
    determinación del resultado en 59) y asiento de apertura del ejercicio
    siguiente;
  - EEFF por centro de costo (situación y resultados filtrados por cuenta
    analítica).
- Encaja en `al_l10n_pe_financial_reports`, que hoy solo trae el 3.19.
- Esfuerzo bajo; los contadores lo piden en cada demo.

### 4. Solución clínica (OL-HEALTH)

- **Por qué:** es la apuesta actual de ITGRUPO (todos sus videos desde 2024)
  y ya tenemos la mitad del camino: farmacia, recetas, prescriptores CMP,
  seguros (`al_pharmacy_insurance`) y CPE.
- **Alcance en fases:**
  1. pacientes (DNI con Decolecta), médicos, horarios y citas, también desde
     el portal con pago en línea (pasarelas ya hechas);
  2. triaje, historia clínica ambulatoria con CIE-10, receta hacia
     `al_pharmacy_prescription`;
  3. órdenes de laboratorio (muestras, etiquetas, resultados) y de imágenes
     (informe, consumo de insumos), con CPE antes de la atención y
     resultados en el portal;
  4. diferenciadores que ITGRUPO no muestra: HL7 real con los equipos de
     laboratorio, enlace con PACS/DICOM, reportes a SUSALUD y consulta de
     acreditación SITEDS para pacientes con seguro.
- Revisar antes los módulos de salud de Odoo Apps y OCA para no partir de
  cero.

### 5. Flota y mantenimiento peruano (OL-TOOLS o nueva área)

- **Alcance:**
  - documentos del vehículo y del conductor con vencimiento y alertas
    (SOAT, revisión técnica, brevete, tarjeta de propiedad);
  - combustible y odómetro;
  - preventivos por kilometraje y por tiempo con paquete de repuestos que
    genera la salida de almacén;
  - requerimiento de compra desde la petición (`purchase_request`);
  - mantenimiento de equipos vendidos por número de serie (garantía y plan
    de preventivos).

### 6. Mejoras menores

- **Legajo digital** en `al_hr_pe`: documentos del trabajador con
  vencimiento y alertas (sobre `documents_hr` si hay EE).
- **Biométricos** en la suite (ZKTeco por red), hoy solo en Extendrix.
- **Preventa y despacho**: app de toma de pedidos con ruta y geolocalización,
  y hoja de carga por vehículo con guías masivas sobre
  `al_l10n_pe_stock_transfer`.
- **BI externo**: vistas de ventas 360, gastos por centro de costo y stock
  semanal publicadas para Power BI/Looker, o tableros nativos equivalentes en
  `al_l10n_pe_dashboard`.

## Ventaja comercial

El contenido de ITGRUPO es antiguo (Odoo 13/15) salvo planillas v17 y la
clínica. Una serie de videos cortos en Odoo 19 de lo que ellos no tienen
(SIRE, letras, cobranza, tesorería, TPV con CPE y QR, pasarelas peruanas,
farmacias, obra) marcaría la diferencia frente al «partner n.º 1».

Ver también [oportunidades por Odoo Apps](OPORTUNIDADES_LOCALIZACION_PE.md).

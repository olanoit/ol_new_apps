# Plan de desarrollo — `al_l10n_pe_ple`

> **Prompt de arranque / planificación completa** del módulo que completa los
> Libros Electrónicos PLE de SUNAT (Perú) en Odoo 19, cubriendo los formatos
> que la localización oficial (CE + EE) **no** genera hoy.
>
> Fecha del plan: 2026-07-18 · Branch: `19.0` · Autor del plan: sesión Claude
> con análisis del código instalado y de `docs/ple/Estructura del PLE.xls`.

---

## 1. Contexto y entorno

| Elemento | Valor |
|---|---|
| Repositorio addons propios | `/home/och/odoo/ce19/myodoo/ol_new_apps` |
| Odoo | 19 (CE `addons/` + EE `ee19/` en el mismo `addons_path`) |
| Configuración de pruebas | `/home/och/odoo/ce19/cfg/my/pe.cfg` (puerto 19700, `dbfilter=ol_pe_v19`) |
| Base de datos de pruebas | `ol_pe_v19` (PostgreSQL local, usuario `odoo`/`odoo`) |
| Convención de versión | `N.AAAAMMDD` (ver memoria `module-version-convention` / skill `odoo-module-versioning`) |
| Estructura oficial SUNAT | `docs/ple/Estructura del PLE.xls` (Anexo 2 — estructuras e información de los libros) |

Referencias oficiales:

- Documentación Odoo Perú: <https://www.odoo.com/documentation/19.0/applications/finance/fiscal_localizations/peru.html>
- eLearning Odoo — Reportes PLE 5.1, 5.3 y 6.1: <https://www.odoo.com/es/slides/slide/reportes-ple-5-1-5-3-y-6-1-localizacion-peru-5413>

## 2. Estado actual — qué ya existe (NO reimplementar)

Análisis del código instalado en `ol_pe_v19` (todos `installed`):

| Formato PLE | Módulo que lo genera | Mecanismo |
|---|---|---|
| **1.1 / 1.2** Caja y Bancos | `l10n_pe_reports` (EE) | `account_ple_cash_bank.py` — botones sobre Flujo de Caja (`l10n_pe_export_ple_11_to_txt` / `_12_`) |
| **3.1–3.7, 3.11–3.15, 3.16.1, 3.16.2, 3.17, 3.18, 3.20, 3.24, 3.25** | `l10n_pe_reports_lib` (EE) | `account_general_ledger.py::l10n_pe_export_lib_to_txt` — un ZIP con todos los TXT; modelos de apoyo `l10n_pe_reports_lib.financial.rubric`, `l10n_pe.shareholder`, rubro EEFF en `account.account` |
| **5.1** Libro Diario, **5.3** Plan contable, **6.1** Libro Mayor | `l10n_pe_reports` (EE) | `account_general_ledger.py` — botones "PLE 5.1 / 5.3 / 6.1" en el Libro Mayor (lo que muestra el slide oficial) |
| **8.1 / 8.2** Registro de Compras (y no domiciliados) | `l10n_pe_reports` (EE) | `account.report` con handlers `account_ple_purchase_8_1/8_2.py` (los nombra "RCE 8.4/8.5" por SIRE) |
| **12.1 / 13.1** Inventario permanente | `l10n_pe_reports_stock` (EE) | wizard `stock_move_ple_report.py` (`get_ple_report_12_1/13_1`) + campos SUNAT en producto/picking/almacén |
| **14.1** Registro de Ventas | `l10n_pe_reports` (EE) | `account_ple_sales_14_1.py` |
| Capa visual 12.1/13.1 (kardex XLSX/PDF/pantalla) | `ol_stock_kardex_pe` (propio) | vista SQL + wizard; complementa el TXT de EE |

Módulos propios de apoyo ya operativos: `al_account_base` (menú raíz **Perú**,
glosa `l10n_pe_gloss` en asientos/líneas, página de ajustes),
`al_account_destinations` (dinámica destino 6↔9), `al_l10n_pe_currency`
(TC SUNAT), `l10n_pe_vat_sunat` (consulta RUC/DNI). `account_asset` (EE) está
**instalado** → fuente de datos del Libro 7. `mrp` **no** está instalado →
condiciona el Libro 10.

## 3. Brecha — alcance de `al_l10n_pe_ple`

Formatos del Anexo 2 SUNAT **sin cobertura actual**:

| Formato | Nombre | Fuente de datos en Odoo | Prioridad |
|---|---|---|---|
| **7.1** | Activos fijos revaluados y no revaluados | `account.asset` (EE, instalado) | **Alta** |
| **7.3** | Activos fijos — diferencia de cambio | `account.asset` + TC (`al_l10n_pe_currency`) | Media |
| **7.4** | Activos en arrendamiento financiero | `account.asset` + datos de contrato (campos nuevos) | Media |
| **4.1** | Retenciones inc. e)/f) Art. 34 LIR | Sin nómina PE en Odoo → modelo de captura manual/importación | Media |
| **9.1 / 9.2** | Consignaciones (consignador/consignatario) | `stock.picking`/`stock.move` con propietario (consignación nativa) | Media |
| **3.8** | Detalle cta. 30 Inversiones mobiliarias | Modelo de captura + `account.move.line` | Baja |
| **3.9** | Detalle cta. 34 Intangibles | `account.asset` (tipo intangible) o captura | Baja |
| **3.19** | Estado de cambios en el patrimonio neto | Balance por rubros (reusar rubros de `l10n_pe_reports_lib`) | Baja |
| **3.23** | Notas a los EEFF | Adjunto **PDF** (sin estructura TXT) | Baja |
| **10.1–10.4** | Registro de Costos (anual) | Sin `mrp`: modelos de captura manual; con `mrp` futuro: cálculo | Baja |
| **5.2 / 5.4** | Diario Simplificado + su plan contable | Mismo dato del 5.1/5.3 (excluyente: solo contribuyentes menores) | Baja |
| **8.3** | Registro de Compras Simplificado | Subconjunto del 8.1 (excluyente con 8.1) | Baja |
| **14.2** | Registro de Ventas Simplificado | Subconjunto del 14.1 (excluyente con 14.1) | Baja |

Notas de alcance:

- Los formatos *simplificados* (5.2/5.4, 8.3, 14.2) solo aplican a
  contribuyentes de menor escala y son **excluyentes** con el formato completo;
  se implementan al final y se habilitan por configuración de compañía.
- **SIRE**: desde 2024 SUNAT migra los registros 14 y 8 al SIRE (RVIE/RCE);
  Odoo EE ya apunta ahí (los llama RCE 8.4/8.5). `al_l10n_pe_ple` no toca
  ventas/compras completos, solo los simplificados por completitud del Anexo 2.
- Licencia: los módulos EE son **OEEL-1** — se puede **depender** de ellos y
  llamar a sus métodos, pero **no copiar su código** a un módulo LGPL-3.

## 4. Arquitectura del módulo

```
al_l10n_pe_ple/
├── __manifest__.py            # version '1.20260718', depends abajo
├── models/
│   ├── ple_mixin.py           # AbstractModel 'l10n_pe.ple.mixin': motor común
│   ├── ple_asset.py           # 7.1 / 7.3 / 7.4 (campos extra en account.asset)
│   ├── ple_withholding.py     # 4.1 modelo de captura l10n_pe.ple.withholding
│   ├── ple_consignment.py     # 9.1 / 9.2 sobre stock.picking/move (owner_id)
│   ├── ple_investment.py      # 3.8 modelo l10n_pe.ple.investment
│   ├── ple_intangible.py      # 3.9 (account.asset intangible o captura)
│   ├── ple_equity.py          # 3.19 (rubros patrimonio) · 3.23 (adjunto PDF)
│   ├── ple_cost.py            # 10.1–10.4 modelos de captura anual/mensual
│   └── res_config_settings.py # régimen (general/RER/simplificado), opciones
├── wizards/
│   └── ple_export_wizard.py   # wizard único: periodo + selección de formatos → ZIP
├── views/                     # menú "Perú ▸ Libros PLE", vistas de captura
├── security/ir.model.access.csv
├── data/ple_tables.xml        # tablas paramétricas SUNAT faltantes (18,19,20,15,16,21…)
├── tests/                     # ver §7
└── README.md
```

**Dependencias** (`depends`): `al_account_base` (menú Perú, glosa),
`l10n_pe_reports` (motor EE, nombres de archivo, usage), `l10n_pe_reports_lib`
(rubros EEFF, accionistas), `l10n_pe_reports_stock` (campos SUNAT stock),
`account_asset`, `stock`. `mrp` NO como dependencia (los 10.x se capturan
manualmente; un sub-módulo futuro `al_l10n_pe_ple_mrp` podrá calcularlos).

### 4.1 Motor común (`l10n_pe.ple.mixin`)

Responsabilidades — implementa las **Reglas Generales** del XLS una sola vez:

1. **Nombre de archivo** (33 caracteres):
   `LE + RUC(11) + AAAA + MM + DD + LLLLLL + CC + O + I + M + G .txt`
   - `MM=00` en libros anuales (7, 10); `DD≠00` solo en libro 3; `CC` solo
     libro 3 (oportunidad 01–07); `O`: 1=operativa (2=cierre libro,
     0=baja RUC); `I`: 1=con información, 0=vacío; `M`: 1=PEN, 2=USD; `G=1`.
2. **Serialización de línea**: unión con `|`, SIN palotes de cierre para los
   campos libres no usados; montos `12e2d` sin separador de miles, negativos
   `-#.##`; fechas `DD/MM/AAAA`; sanitizado de texto (prohibidos `| / \`);
   cantidades `12e8d` donde aplique.
3. **CUO y correlativo**: reuso del criterio EE (`_get_serie_folio` de
   `l10n_pe_reports`) — CUO = id del `account.move`; correlativo con prefijo
   `A`/`M`/`C` (apertura/movimiento/cierre).
4. **Estado de operación** por familia: contables `1/8/9`; ventas
   `0/1/2/8/9`; compras `0/1/6/7/9` (validado contra el periodo).
5. **Empaquetado**: un TXT por formato; ZIP cuando el libro tiene varios
   formatos (patrón de `l10n_pe_reports_lib`); archivo "sin información"
   (indicador `I=0`, contenido vacío) cuando el periodo no tiene datos.
6. **Validador interno**: función `assert_structure(code, line)` que verifica
   nº de campos por formato (tabla §6) — usada por los tests.

### 4.2 Wizard de exportación

`l10n_pe.ple.export.wizard`: compañía + periodo (mes o ejercicio según
libro) + moneda + selección múltiple de formatos habilitados → genera y
adjunta ZIP/TXT. Menú **Perú ▸ Libros PLE** (parent
`al_account_base.al_l10n_pe_root`). Los formatos ya cubiertos por EE se
listan en el wizard como enlaces informativos a su reporte nativo (no se
regeneran) para que el usuario tenga un punto único de entrada.

### 4.3 Datos maestros nuevos

- `account.asset`: campos SUNAT — código propio del activo (A24), catálogo
  (tabla 13), tipo de activo (tabla 18), estado (tabla 19), método de
  depreciación (tabla 20) + % SUNAT, marca/modelo/serie-placa, datos leasing
  (nº contrato, fecha, nº cuotas, monto) para 7.4, datos ME/TC para 7.3.
- `l10n_pe.ple.withholding` (4.1): fecha de pago, prestador (tipo/nº doc,
  nombre), monto bruto, retención (negativa), estado. Importable por XLSX.
- `l10n_pe.ple.investment` (3.8): emisor, código título (tabla 15), valor
  nominal, cantidad, costo en libros, provisión.
- Costos 10.x: `l10n_pe.ple.cost.sales` (anual), `l10n_pe.ple.cost.element`
  (mensual), `l10n_pe.ple.cost.production` (procesos, tabla 21),
  `l10n_pe.ple.cost.center` (correlativo + unidad + centro de costos, puede
  precargarse desde `account.analytic.account`).
- Consignaciones 9.x: se derivan de pickings con `owner_id` (consignación
  nativa de Inventario); campos de enlace guía↔CdP donde falten.

## 5. Fases de desarrollo

| Fase | Contenido | Entregable verificable |
|---|---|---|
| **0** ✅ 2026-07-18 | Esqueleto del módulo + mixin (naming, serialización, validador) + wizard + menú | Tests unitarios del naming/serialización en verde; módulo instala en `ol_pe_v19` |
| **1** ✅ 2026-07-18 | **Libro 7**: campos en `account.asset`, generadores 7.1 (37 c.), 7.3 (15 c.), 7.4 (11 c.) | TXT válidos con activos reales de la BD; docs `docs/ple/reportes/libro_7.md` |
| **2** ✅ 2026-07-18 | **4.1** (captura + import) y **9.1/9.2** (consignación stock) | TXT 10 c. / 22 c. / 21 c.; docs por libro |
| **3** ✅ 2026-07-18 | **3.8, 3.9, 3.19** (+ 3.23 adjunto PDF) integrados al ZIP del libro 3 | TXT según §6; docs |
| **4** ✅ 2026-07-18 | **10.1–10.4** captura manual | TXT anuales/mensuales; docs |
| **5** ✅ 2026-07-18 | Simplificados **5.2/5.4, 8.3, 14.2** (flag de régimen en ajustes) | TXT subconjunto validado contra 5.1/8.1/14.1; docs |
| **6** ✅ 2026-07-19 | Documentación índice (`docs/ple/reportes/README.md`: matriz formato→módulo→menú→estructura), pruebas integrales en `ol_pe_v19`, bump versión y commit | 30/30 tests en verde con `pe.cfg` (24 PLE + 10 kardex); app única «Perú» con todos los accesos |

Cada fase termina con: actualización de `__manifest__.py` (`N.AAAAMMDD`),
tests de la fase en verde y su documento en `docs/ple/reportes/`.

### Documentación por reporte (obligatoria — criterio del proyecto)

Para **cada formato** (incluidos los ya existentes de EE, para tener el mapa
completo) crear `docs/ple/reportes/<libro>.md` con: código y nombre SUNAT,
periodicidad y patrón de nombre de archivo, módulo/menú que lo genera,
estructura campo a campo (tabla del §6 ampliada con el mapeo campo→fuente
Odoo), reglas de estado aplicables, configuración previa necesaria y
limitaciones conocidas.

## 6. Estructuras oficiales (extracto verificado del XLS)

> Fuente: `docs/ple/Estructura del PLE.xls` — resumen fiel; el XLS manda ante
> cualquier duda. Convenciones: N=numérico, A=alfanumérico, T=texto,
> F=fecha `DD/MM/AAAA`; `12e2d`=hasta 12 enteros/2 decimales; **(op)**=opcional.
> Tras el campo "Estado" siguen campos de libre utilización que, si no se
> usan, **no llevan palotes**.

### 6.1 Nombre de archivo

`LE RRRRRRRRRRR AAAA MM DD LLLLLL CC O I M G .TXT` — RUC(11) + año + mes
(`00` en anuales) + día (`00` salvo libro 3) + código de formato (6 díg.) +
oportunidad EEFF (`00` salvo libro 3; 01=31/12 … 07=libre) + indicador de
operaciones (0/1/2) + contenido (1/0) + moneda (1=PEN, 2=USD) + `1` fijo.

**Códigos**: 010100=1.1, 010200=1.2 · 0301xx–0325xx=libro 3 (030100=3.1,
030200=3.2, 030300=3.3, 030400=3.4, 030500=3.5, 030600=3.6, 030700=3.7,
030800=3.8, 030900=3.9, 031100=3.11, 031200=3.12, 031300=3.13, 031400=3.14,
031500=3.15, 031601=3.16.1, 031602=3.16.2, 031700=3.17, 031800=3.18,
031900=3.19, 032000=3.20, 032300=3.23·PDF, 032400=3.24, 032500=3.25) ·
040100=4.1 · 050100=5.1, 050200=5.2, 050300=5.3, 050400=5.4 · 060100=6.1 ·
070100=7.1, 070300=7.3, 070400=7.4 · 080100=8.1, 080200=8.2, 080300=8.3 ·
090100=9.1, 090200=9.2 · 100100=10.1, 100200=10.2, 100300=10.3, 100400=10.4 ·
120100=12.1 · 130100=13.1 · 140100=14.1, 140200=14.2.

### 6.2 Reglas generales

- Separador `|`; texto sin `| / \`; montos sin separador de miles, negativos
  `-#.##`; fechas `DD/MM/AAAA` ≤ periodo.
- **Estado** libros contables (1,3,4,5,5A,6,7,9,10,12,13): `1` operación del
  periodo · `8` de periodo anterior NO anotada · `9` ajuste de anotación
  anterior (el CUO referencia el original).
- **Estado** ventas (14): `0` optativa sin efecto IGV · `1` del periodo ·
  `2` anulado/inutilizado · `8` · `9`.
- **Estado** compras (8.1/8.3): `0` sin crédito fiscal · `1` con crédito ·
  `6` emisión anterior dentro de 12 meses · `7` ídem sin crédito · `9`
  ajuste. (8.2 solo `0`/`9`.)
- Docs de identidad (tabla 2): 1=DNI(8N), 4=CE, 6=RUC(11N), 7=Pasaporte,
  A=Céd. diplomática, 0=otros.
- Validación de comprobantes (hoja "Reglas Comprobantes de Pago"): tipo de
  CdP (tabla 10) válido por registro y por estado; serie electrónica
  `E001/FXXX/EB01/BXXX`; DUA serie=cód. aduana+año; número ≤8 díg. (20
  alfanumérico en tipo 00).

### 6.3 Formatos a implementar (campo a campo)

**7.1 Activos fijos — 37 campos** (periodo `AAAA0000`): 1 Periodo · 2 CUO ·
3 Correlativo (A/M/C) · 4 Cód. catálogo (t13) · 5 Cód. propio del activo A24 ·
6 Catálogo UNSPSC/GTIN (op) · 7 Cód. UNSPSC (op) · 8 Tipo activo (t18) ·
9 Cta. contable N24 · 10 Estado del activo (t19) · 11 Descripción T40 ·
12 Marca ('-') · 13 Modelo ('-') · 14 Serie/placa ('-') · 15 Saldo inicial ·
16 Adquisiciones · 17 Mejoras · 18 Retiros/bajas · 19 Otros ajustes ·
20 Reval. voluntaria · 21 Reval. por reorganización · 22 Otras reval. ·
23 Ajuste inflación (15–23 `12e2d` ±) · 24 F. adquisición · 25 F. inicio uso ·
26 Método deprec. (t20) · 27 Nº doc. autorización cambio método ·
28 % deprec. `3e2d` (oblig. si 26='1') · 29 Deprec. acum. ejercicio anterior ·
30 Deprec. del ejercicio · 31 Deprec. retiros · 32 Deprec. otros ajustes ·
33–35 Deprec. de revaluaciones · 36 Ajuste inflación deprec. · 37 Estado.

**7.3 Diferencia de cambio — 15 campos**: 1 Periodo · 2 CUO · 3 Correlativo ·
4 Catálogo (solo 3/9 de t13) · 5 Cód. activo · 6 F. adquisición · 7 Valor
adq. ME · 8 TC adquisición `1e3d` · 9 Valor adq. MN · 10 TC 31/12 ·
11 Ajuste dif. cambio · 12 Deprec. ejercicio · 13 Deprec. retiros ·
14 Deprec. otros ajustes · 15 Estado.

**7.4 Leasing — 11 campos**: 1 Periodo · 2 CUO · 3 Correlativo · 4 Catálogo
(3/9) · 5 Nº contrato A20 · 6 F. contrato · 7 Cód. activo · 8 F. inicio
arrendamiento · 9 Nº cuotas N5 · 10 Monto total contrato · 11 Estado.

**4.1 Retenciones — 10 campos**: 1 Periodo · 2 CUO · 3 Correlativo (A/M/C) ·
4 F. pago/retención · 5 Tipo doc. prestador (t2) · 6 Nº doc. · 7 Apellidos y
nombres T100 · 8 Monto bruto · 9 Retención (**negativa o 0.00**) · 10 Estado.

**9.1 Consignador — 22 campos**: 1 Periodo · 2 Catálogo (t13) · 3 Tipo
existencia (t5) · 4 Cód. existencia A24 · 5 CUO · 6 Nombre existencia T80 ·
7 UM (t6) · 8 F. guía remisión · 9 Serie guía · 10 Nº guía · 11 Tipo CdP
('00' si no hay) · 12 F. emisión CdP (op) · 13 Serie CdP ('0') · 14 Nº CdP
('0') · 15 F. entrega/devolución · 16 Tipo doc. consignatario · 17 Nº doc. ·
18 Razón social · 19 Cant. entregada (1ª tupla=saldo inicial) · 20 Cant.
devuelta (−) · 21 Cant. vendida (−) — 19/20/21 excluyentes · 22 Estado.
**9.2 Consignatario — 21 campos**: espejo (16 RUC consignador N11 · 17 razón
social · 18 recibida + · 19 devuelta − · 20 vendida − · 21 Estado).

**3.8 Inversiones — 12 campos**: 1 Periodo · 2 CUO · 3 Correlativo · 4 Tipo
doc. emisor ('0' si no hay) · 5 Nº doc. · 6 Nombre emisor · 7 Cód. título
(t15) · 8 Valor nominal unitario · 9 Cant. títulos N12 · 10 Costo total en
libros · 11 Provisión (−) · 12 Estado.

**3.9 Intangibles — 9 campos**: 1 Periodo · 2 CUO · 3 Correlativo · 4 F.
inicio operación · 5 Cta. contable · 6 Descripción T40 · 7 Valor contable ·
8 Amortización acumulada (−) · 9 Estado.

**3.19 Cambios en patrimonio — 16 campos**: 1 Periodo (AAAAMMDD) · 2 Cód.
catálogo (t22) · 3 Cód. rubro (t34) · 4–15 columnas `12e2d`: Capital,
Acciones de inversión, Capital adicional, Resultados no realizados, Reservas
legales, Otras reservas, Resultados acumulados, Dif. de conversión, Ajustes
al patrimonio, Resultado neto, Excedente de revaluación, Resultado del
ejercicio · 16 Estado. **3.23**: se presenta en **PDF** (sin TXT).

**10.1 Costo de ventas anual — 6 campos**: 1 Ejercicio · 2 Inv. inicial PT ·
3 Costo producción PT · 4 Inv. final PT (−) · 5 Ajustes · 6 Estado.
**10.2 Elementos del costo (mensual) — 8 campos**: 1 Periodo · 2 Materiales
directos · 3 MO directa · 4 Otros costos directos · 5 GIF materiales ·
6 GIF MO indirecta · 7 Otros GIF · 8 Estado.
**10.3 Costo de producción anual — 13 campos**: 1 Ejercicio · 2 Cód. proceso
T10 · 3 Descripción T100 · 4–9 elementos (como 10.2) · 10 Inv. inicial en
proceso · 11 Inv. final en proceso (−) · 12 Cód. agrupamiento (t21) ·
13 Estado.
**10.4 Centros de costos — 7 campos**: 1 Periodo · 2 Correlativo N24 ·
3 Cód. unidad de operación (op) · 4 Descripción (op) · 5 Cód. centro de
costos (op) · 6 Descripción CC (op) · 7 Estado.

**5.2 Diario Simplificado**: estructura **idéntica al 5.1** (21 campos:
Periodo, CUO, Correlativo A/M/C, Cuenta N24, Unidad op. (op), CC (op),
Moneda t4, Tipo/Nº doc. emisor (op), Tipo CdP t10, Serie (op), Nº CdP,
F. contable (op), F. vencimiento (op), F. operación, Glosa T200, Glosa ref.
(op), Debe, Haber (excluyentes, cuadre por CUO), Dato estructurado T92 (op;
enlaza con 140100/080100/080200), Estado 1/8/9). **5.4** = idéntico al 5.3
(8 campos: Periodo AAAAMMDD, Cód. cuenta N24, Descripción T100, Cód. plan
t17, Descripción plan (op), Cta. corporativa (op), Descripción corp. (op),
Estado).

**8.3 Compras Simplificado — 32 campos** (subconjunto del 8.1): 1 Periodo ·
2 CUO · 3 Correlativo · 4 F. emisión · 5 F. vencimiento (op) · 6 Tipo CdP ·
7 Serie · 8 Número · 9 Nº final consolidado (op) · 10–12 Tipo/Nº doc./Razón
social proveedor · 13 BI gravada · 14 IGV/IPM · 15 ICBPER · 16 Otros ·
17 Importe total (=13+14+15+16) · 18 Moneda (op) · 19 TC (op) · 20–23 CdP
modificado (fecha/tipo/serie/nº) · 24–25 Detracción (op) · 26 Marca
retención (op) · 27 Clasificación t30 (op) · 28–30 Errores 1–3 (op) ·
31 Pago con medio de pago (op) · 32 Estado (0/1/6/7/9).

**14.2 Ventas Simplificado — 26 campos** (subconjunto del 14.1): 1 Periodo ·
2 CUO · 3 Correlativo · 4 F. emisión · 5 F. vencimiento (op) · 6 Tipo CdP ·
7 Serie · 8 Número · 9 Nº final tickets (op) · 10–12 Tipo/Nº doc./Razón
social cliente (oblig. salvo tipo 00, estado 2 o importe &lt; 700.00) ·
13 BI gravada · 14 IGV/IPM · 15 ICBPER · 16 Otros · 17 Importe total ·
18 Moneda · 19 TC · 20–23 CdP modificado · 24 Error tipo 1 · 25 Pago con
medios de pago · 26 Estado (0/1/2/8/9).

### 6.4 Tablas paramétricas SUNAT referenciadas

1 medios de pago · 2 doc. identidad · 3 entidades financieras · 4 monedas ·
5 tipo existencia · 6 unidades de medida · 10 tipos de CdP · 11 aduanas ·
12 tipo operación · 13 catálogo existencias · 14 método valuación ·
15 títulos · 16 tipos de acciones · 17 planes contables · 18 tipo activo
fijo · 19 estado del activo · 20 método depreciación · 21 agrupamiento
costos · 22 catálogo EEFF · 34 rubros EEFF · 35 países. Las tablas 5, 6,
10, 12, 13, 14, 22, 34 ya existen en los módulos EE/`l10n_pe_edi`; el módulo
nuevo agrega como `data/` las que falten (15, 16, 18, 19, 20, 21).

## 7. Plan de pruebas en `ol_pe_v19`

```bash
cd /home/och/odoo/ce19
# instalación / actualización
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -i al_l10n_pe_ple --stop-after-init
# tests del módulo
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_ple \
  --test-enable --test-tags /al_l10n_pe_ple --stop-after-init
```

Cobertura mínima de tests (`tests/`):

1. **Naming**: nombre de archivo correcto por formato/periodicidad (mensual
   `MM`, anual `00`, libro 3 con `DD` y `CC`, indicador `I=0` sin datos).
2. **Estructura**: nº exacto de campos por línea según §6 (usa
   `assert_structure`), separador, sin palotes finales, formatos de
   fecha/monto/negativos.
3. **Contenido**: casos con datos reales creados en el test (un activo fijo
   con depreciación → 7.1; retención capturada → 4.1; picking de
   consignación → 9.1; etc.), verificando cuadres (p.ej. 7.1 campo 15+16+17
   −18… coherente con `account.asset`).
4. **Exclusiones/estados**: estados 1/8/9 y las reglas 0/1/6/7/9 según libro.
5. **Humo en BD real**: wizard ejecutado sobre periodos con datos existentes
   de `ol_pe_v19` (facturas y activos ya cargados) sin errores; TXT abre y
   valida en el PLE de SUNAT (verificación manual final).

## 8. Prompt de arranque (para iniciar el desarrollo)

> Implementa el módulo `al_l10n_pe_ple` en
> `/home/och/odoo/ce19/myodoo/ol_new_apps` siguiendo este plan
> (`docs/ple/PLAN_MODULO_al_l10n_pe_ple.md`) fase por fase, empezando por la
> Fase 0 (mixin + wizard + menú) y la Fase 1 (Libro 7 con `account.asset`).
> Respeta: convención de versión `N.AAAAMMDD`; menú bajo
> `al_account_base.al_l10n_pe_root`; no copiar código OEEL (solo depender y
> extender); estructuras campo a campo del §6 con el XLS
> `docs/ple/Estructura del PLE.xls` como fuente de verdad; tests y prueba de
> instalación en la BD `ol_pe_v19` con `cfg/my/pe.cfg` al cierre de cada
> fase; documentar cada formato en `docs/ple/reportes/`. Al terminar cada
> fase: actualizar manifest, correr los tests y dejar commit preparado.

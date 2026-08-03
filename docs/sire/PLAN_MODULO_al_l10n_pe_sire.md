# Plan del módulo `al_l10n_pe_sire` — SIRE (RVIE / RCE) SUNAT

> **Fecha:** 2026-07-19 · **Branch:** `19.0` · **Autor:** CRISTÓBAL OCH
> **BD de pruebas:** `ol_pe_v19` · **Config:** `/home/och/odoo/ce19/cfg/my/pe.cfg` (puerto 19700)
> **Referencia v17:** `/home/och/odoo/ce17/al/thinksh/new/sire` (módulo `sire` de Carlos Gallo)
> **Normativa:** R.S. 112-2021/SUNAT y modificatorias — Sistema Integrado de Registros Electrónicos
> **Manuales:** [Manual práctico SOL](https://cpe.sunat.gob.pe/sites/default/files/inline-files/SIRE-ManualPracticoSOL_Complementar_0.pdf) · [SIRE](https://sire.sunat.gob.pe/) · Manuales de servicios Web API SIRE (cpe.sunat.gob.pe)

## 1. Contexto

El **SIRE** (Sistema Integrado de Registros Electrónicos) reemplaza progresivamente al PLE
para los registros de **Ventas e Ingresos (RVIE)** y **Compras (RCE)**. SUNAT genera una
**propuesta** a partir de los CPE emitidos/recibidos; el contribuyente la **acepta,
complementa o reemplaza** y luego **genera el registro** del periodo. SUNAT expone una
API REST (`api-sire.sunat.gob.pe`) autenticada con OAuth2 + credenciales SOL
(client_id / client_secret generados en el buzón SOL).

El módulo permite, por periodo (año/mes) y compañía:

1. Solicitar la **propuesta** de SUNAT (RVIE o RCE) vía API → ticket.
2. Consultar el **estado del ticket** y **descargar** el TXT de la propuesta (ZIP).
3. **Desplegar** la propuesta en líneas (parseo del TXT oficial).
4. **Desplegar el sistema**: construir las mismas columnas desde `account.move` de Odoo.
5. **Comparar** ambos lados por CAR SUNAT con campos configurables → estados
   *Correcto / No cuadran / Solo en SIRE / Solo en Sistema* y detalle de diferencias.
6. Exportar **XLSX** (2 hojas: SIRE y Sistema) y **TXT de reemplazo** (formato de importación
   SUNAT, comprimido en ZIP con nombre oficial `LE<RUC><periodo>00<libro>021112.zip`).

También admite **descarga manual**: si no se usa la API, el TXT exportado desde SOL se
carga a mano y el flujo continúa igual.

## 2. Qué ya existe (NO reimplementar)

| Pieza | Dónde | Uso desde este módulo |
| --- | --- | --- |
| Menú raíz «Perú» y app de ajustes | `al_account_base` (`al_l10n_pe_root`, `al_l10n_pe_config`, app `al_account_base`) | Colgar menús; el módulo añade su propio bloque `pe_sire_block` («SIRE (RVIE / RCE)») |
| Tipo/afectación de impuestos PE | `l10n_pe_edi` (`l10n_pe_edi_affectation_reason`, `l10n_pe_edi_tax_code`, `l10n_pe_edi_operation_type`, `l10n_pe_edi_refund_reason`) | Clasificar bases (gravada/exonerada/inafecta/exportación/gratuita) |
| Tipo de documento y serie-folio | `l10n_latam_invoice_document` | `l10n_latam_document_type_id.code`, `l10n_latam_document_number` |
| Detracciones | `al_l10n_pe_detraction` (`l10n_pe_detraction_applies`) | Columna «Detracción» del RCE (chequeo suave, sin dependencia dura) |
| Registros 8.1/14.1 PLE | `l10n_pe_reports` (EE) | No se toca; SIRE convive con PLE |

## 3. Alcance / brecha

- **Sí**: RVIE y RCE propuesta + comparación + exportables; credenciales por compañía;
  campos de comparación configurables; multicompañía.
- **Sí (fase 6)**: **aceptación de la propuesta**, **envío del reemplazo por API** (carga
  masiva sobre el servidor TUS de SUNAT) y **registro del preliminar**. El TXT de reemplazo
  se sigue pudiendo descargar para cargarlo a mano en SOL.
- **No**: la **generación del registro** (SUNAT no expone servicio: se completa en el portal),
  RCE No Domiciliados (080500) y ajustes posteriores.

## 4. Arquitectura

```
al_l10n_pe_sire/
├── __manifest__.py            # depends: al_account_base, l10n_pe_edi
├── models/
│   ├── res_company.py         # credenciales API SOL + res.config.settings
│   ├── sire_api.py            # l10n_pe.sire.api (AbstractModel): OAuth2 + REST SUNAT
│   ├── sire_mixin.py          # l10n_pe.sire.mixin: flujo, comparación, exportables
│   ├── sire_rce.py            # l10n_pe.sire.rce (+ .line): Registro de Compras
│   ├── sire_rvie.py           # l10n_pe.sire.rvie (+ .line): Registro de Ventas
│   ├── sire_compare_field.py  # l10n_pe.sire.compare.field: campos a comparar
│   └── account_move.py        # clasificación de bienes (Tabla 30) en facturas de compra
├── data/sire_compare_fields.xml
├── views/  (rce, rvie, compare_field, account_move, settings, menu.xml al final)
├── security/ir.model.access.csv
├── tests/test_sire.py
├── tools/sire_demo_data.py
└── docs/   (guía funcional)
```

**Endpoints SUNAT** (constantes en `sire_api.py`; verificados contra los manuales
oficiales de servicios web API SIRE Compras v22 y Ventas v22):

| Función | URL |
| --- | --- |
| Token OAuth2 | `POST https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/` (grant password, scope `https://api-sire.sunat.gob.pe`, username = `RUC+usuarioSOL`) |
| Propuesta RVIE | `GET …/libros/rvie/propuesta/web/propuesta/{periodo}/exportapropuesta` |
| Propuesta RCE | `GET …/libros/rce/propuesta/web/propuesta/{periodo}/exportacioncomprobantepropuesta` |
| Estado tickets | `GET …/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets` |
| Descarga reporte | `GET …/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte` |
| **Aceptar propuesta RVIE** | `POST …/libros/rvie/propuesta/web/propuesta/{periodo}/aceptapropuesta` → ticket |
| **Aceptar propuesta RCE** | `POST …/libros/rce/propuesta/web/registroslibros/{periodo}/aceptarpropuesta` → ticket |
| **Carga de reemplazo** | `POST …/libros/rvierce/receptorpropuesta/web/propuesta/upload` (TUS 1.0.0) → ticket |
| **Registrar preliminar RVIE** | `POST …/libros/rvierce/gestionlibro/web/registroslibros/{periodo}/registrapreliminar` |
| **Registrar preliminar RCE** | `POST …/libros/rce/preliminar/web/registroslibros/{periodo}/registrapreliminares` |

**Carga de archivos**: SUNAT expone un servidor **TUS 1.0.0** (su manual documenta el
cliente `tus-java-client` 0.5.0). Se implementa a mano en dos peticiones —`POST` de
creación con `Upload-Length`/`Upload-Metadata` y `PATCH` con los bytes— en vez de añadir
una dependencia. Los metadatos van en base64 y sus códigos salen del **Anexo I** del
manual: `codProceso` **3** para el reemplazo del RVIE y **61** para el del RCE;
`codLibro` **140000** (RVIE) y **080000** (RCE); `codOrigenEnvio` 2 (servicio web) y
`codTipoCorrelativo` 01.

Base: `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv`.

**Flujo de estados** (mixin): `draft → requested → downloaded → sire_loaded →
system_loaded → compared → done` (con `download_manual` se salta la API y se pasa
directo a `downloaded` cargando el TXT a mano; `action_reset` regresa a `downloaded`).

**Comparación**: clave = CAR SUNAT (SUNAT lo entrega; el sistema lo sintetiza como
`RUC(11) + tipoCP(2) + serie(4) + número(10)`). Se comparan los campos activos de
`l10n_pe.sire.compare.field` (ordenados por secuencia); se registran **todas** las
diferencias en `diff_detail` (mejora sobre v17, que solo guardaba la primera).
Estados de línea: `0` Correcto · `1` No cuadran · `2` Solo en SIRE · `3` Solo en Sistema.

**Importes del sistema** (en PEN, con signo negativo en notas de crédito):
bases clasificadas por `l10n_pe_edi_affectation_reason` del primer IGV de cada línea
(gravada 10-17/102, exonerada 20, inafecta 30-36, exportación 40, gratuitas 9996);
IGV/ISC/ICBPER desde las líneas de impuesto por grupo fiscal; conversión con
`amount_total_signed / amount_total` (3 decimales, vacío si PEN).
Regla RVIE: NC (07) de comprobante de periodo anterior → montos a columnas de
**descuento** (`dscto_bi`, `dscto_igv`); mismo periodo → columnas normales.

## 5. Fases

| # | Fase | Entregable verificable | Estado |
| --- | --- | --- | --- |
| 0 | Plan + esqueleto del módulo | Módulo instala en `ol_pe_v19` | ✅ |
| 1 | Credenciales API + cliente REST (`sire_api`) | Token simulado en tests; UserError claro sin credenciales | ✅ |
| 2 | RCE: propuesta/ticket/descarga/parseo + líneas sistema | TXT de muestra parsea; factura de compra genera línea correcta | ✅ |
| 3 | RVIE: ídem ventas | TXT 40 col parsea; factura/NC de venta generan línea correcta | ✅ |
| 4 | Comparación configurable + diferencias + XLSX + TXT reemplazo | Estados 0-3 correctos en tests; TXT con nº de columnas oficial | ✅ |
| 5 | Tests integrales, demo, docs y commit | Suite verde; guía funcional; `tools/sire_demo_data.py` | ✅ |
| 6 | Envío a SUNAT: aceptar, reemplazar y registrar preliminar | Metadatos oficiales verificados en tests; 27 tests | ✅ |

## 6. Estructuras oficiales usadas

- **TXT propuesta RCE** (exportación SUNAT): ≥ 41 columnas separadas por `|`
  (v17 esperaba 80 con relleno); se mapean las 41 primeras (CAR, fechas, tipo/serie/nro,
  proveedor, bases DG/DGNG/DNG, valor adq. NG, ISC, ICBPER, otros, total, moneda, TC,
  doc. modificado, DAM, clasificación, detracción, tipo nota, estado, inconsistencias).
- **TXT propuesta RVIE**: 40 columnas (CAR, fechas, tipo/serie/nro, cliente, exportación,
  BI gravada, descuentos, IGV, exonerado, inafecto, ISC, IVAP, ICBPER, otros, total,
  moneda, TC, doc. modificado, proyecto, tipo nota, estado, gratuitas, tipo operación, CLU).
- **TXT reemplazo RCE**: 36 campos (layout de importación SUNAT compras domiciliados,
  libro `080400`).
- **TXT reemplazo RVIE**: 34 campos (libro `140400`).
- Nombre de archivo: `LE{RUC}{AAAAMM}00{libro}021112.txt` dentro de un ZIP homónimo.

## 7. Configuración previa

Ajustes → Perú → SIRE (RVIE / RCE): usuario SOL, clave SOL, client_id y client_secret de la API
SIRE (se generan en SOL: Empresas → Credenciales de API SUNAT). Sin credenciales, los
botones de API lanzan `UserError`; la vía manual sigue disponible.

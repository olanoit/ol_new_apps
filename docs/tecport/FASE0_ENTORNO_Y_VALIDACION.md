# Fase 0 — Entorno de trabajo y estrategia de validación

Ver el plan completo en [ANALISIS_Y_PLAN_TECPORT_L10N_PE.md](ANALISIS_Y_PLAN_TECPORT_L10N_PE.md).

**Estado: verificado. El entorno ya existía; no hubo que levantar nada.**

---

## 1. Entorno destino — Odoo 19

| Dato | Valor |
|---|---|
| Configuración | `/home/och/odoo/ce19/cfg/my/pe.cfg` |
| Base de datos | `ol_pe_v19` |
| Puerto HTTP | 19700 |
| Addons | `addons`, `apps/tools`, `ee19`, `myodoo/ol_new_apps`, `ol_new_apps/tools`, `apps/developers` |
| Módulos instalados | 237 |
| Volumen | 2 compañías · 192 asientos · 447 apuntes · 61 facturas · 56 contactos |

### Módulos relevantes ya instalados

**Enterprise PE:** `l10n_pe`, `l10n_pe_edi`, `l10n_pe_edi_pos`, `l10n_pe_edi_stock`, `l10n_pe_pos`, `l10n_pe_reports`, `l10n_pe_reports_lib`, `l10n_pe_reports_stock`, `account_reports`, `account_asset`, `account_edi`, `account_edi_ubl_cii`, `l10n_account_withholding_tax`.

**Suite `al_*`:** las 15 de contabilidad/localización + las 8 de planillas. No está instalado `ol_stock_kardex_pe` (relevante para la Fase 4, contraste del formato 13.1).

**Conclusión:** la base v19 sirve para desarrollar, pero **no para validar**: 192 asientos no permiten contrastar un libro mensual.

---

## 2. Base de referencia — Odoo 18 con el proyecto origen

Existe una base con el proyecto `tecport/l10n_pe` instalado y volumen real:

| Dato | Valor |
|---|---|
| Configuración | `/home/och/odoo/ce18/cfg/mblz/tecport.cfg` (dbfilter `tecport`) |
| Base de datos | `tecport-mtest` |
| Versión | Odoo 18.0 |
| Volumen | 6 compañías · **52 378 asientos** · **167 836 apuntes** |

### Compañía de contraste

| ID | Compañía | RUC | Asientos publicados |
|---:|---|---|---:|
| 1 | Tecport Chile Spa | 76580701-8 | 27 819 |
| 2 | Tecport Latam LLC | 81-1451349 | 6 218 |
| **3** | **TECPORT PERU** | **20517256031** | **13 822** |
| 5 | Sarria De La Cotera Alejandro David | 10412246344 | 2 277 |
| 4, 6 | TECPORT INDUSTRIES / BRASIL | — | 0 |

**Compañía de referencia: id 3, TECPORT PERU.**

### Periodos disponibles (compañía 3, asientos publicados)

| Periodo | Asientos | Facturas |
|---|---:|---:|
| 2026-01 | 3 295 | 709 |
| 2026-02 | 1 641 | 500 |
| 2026-03 | 1 732 | 486 |
| 2026-04 | 1 789 | 387 |
| 2026-05 | 1 645 | 418 |
| 2026-06 | 1 749 | 414 |
| 2026-07 | 1 746 | 431 |
| 2026-08 | 223 | 68 (parcial) |

**Periodos de contraste propuestos: 2026-03** (mes representativo, cerrado) y **2026-01** (mes de mayor volumen, para estrés).

### Riqueza de datos SUNAT en la compañía 3

| Dato | Cantidad | Sirve para validar |
|---|---:|---|
| Apuntes con `serie_correlative` | 24 096 | todos los libros |
| Asientos con fecha SUNAT (`l10n_pe_reports_date`) | 13 963 | criterios de periodo y estado PLE |
| Capas de valoración de stock | 6 000 | formato 13.1 |
| **Activos fijos** | **0** | ⚠️ **7.1/7.4 no se puede validar aquí** |

### Módulos del origen instalados en `tecport-mtest`

Instalados: los 8 libros electrónicos salvo activos fijos, 7 de los 8 físicos, catálogos SUNAT, TXT de detracciones, tipo de cambio (ApisPeru y Decolecta), serie/correlativo, formatos de factura, y `mblz_l10n_pe_multicurrency_revaluation`.

**Desinstalados:** `l10n_pe_edi_efact`, `l10n_pe_reports_electronic_fixed_assets`, `l10n_pe_reports_physical_fixed_assets`, `l10n_pe_rate_update_bcrp`.

---

## 3. Estrategia de validación

El criterio de aceptación nº 1 del plan —«TXT idéntico en estructura al de la v18 para el mismo periodo y juego de datos»— es viable, pero requiere resolver que las dos bases no comparten datos.

### Procedimiento propuesto

1. **Generar los TXT de referencia en v18.** Levantar `tecport.cfg` contra `tecport-mtest`, compañía TECPORT PERU, periodos 2026-01 y 2026-03, y exportar los formatos disponibles. Archivar la salida en `docs/tecport/referencia/<formato>/<periodo>.txt`. Es una operación de solo lectura sobre la base.
2. **Construir un juego de datos equivalente en v19.** Para cada formato, un fixture mínimo pero representativo (los casos que el manual de 714 líneas documenta como especiales: notas de crédito, no domiciliados, gratuitas, anuladas, moneda extranjera, estado PLE 8 y 9). Es lo que se compara automáticamente en los tests.
3. **Comparar dos cosas distintas, sin confundirlas:**
   - **Estructura** (número de campos, longitudes, separadores, orden, nomenclatura del archivo): se valida contra los TXT de referencia y contra la especificación de SUNAT. Es un criterio duro.
   - **Contenido** (importes, totales): se valida contra el fixture, no contra la referencia, porque los datos de origen son distintos.
4. **Cuando Enterprise 19 ya emite el formato** (1.1, 1.2, 5.1, 5.3, 6.1, 8.1, 8.2, 14.1, 12.1, 13.1), la referencia pasa a ser **la salida de Enterprise**, no la de tecport. Ahí lo que se valida es que los criterios SUNAT añadidos (fecha, estado, exclusiones) modifiquen la selección de líneas como se espera, no que el formato coincida con tecport.

### Bloqueos conocidos

| Formato | Bloqueo | Salida |
|---|---|---|
| 7.1 / 7.4 activos fijos | 0 activos en la base de referencia, y el módulo está desinstalado | Contrastar contra `al_l10n_pe_ple`, que ya implementa 7.1/7.3/7.4, y crear fixtures propios |
| eFact / OSE | módulo desinstalado en la base de referencia | Validar contra la especificación UBL 2.1 de SUNAT y con un WSDL de pruebas de un OSE real |
| 13.1 inventario | tres implementaciones candidatas (EE, `ol_stock_kardex_pe`, tecport) | Fase 4: instalar `ol_stock_kardex_pe` en `ol_pe_v19` y comparar las tres con el mismo juego de datos |

### Ejecución — hecha el 15/08/2026

Autorizada la exportación restringida a la compañía TECPORT PERU. Resultado:

- **16 ejecuciones** (8 libros × 2 periodos), **todas correctas**, sin un solo error.
- **60 archivos** generados: 22 TXT (11 directos + 11 dentro de ZIP), 16 PDF físicos, 22 XLSX. Total 38 MB.
- Ninguna escritura persistente: `rollback` tras cada libro, los wizards son `TransientModel`.
- Script reutilizable: [`gen_referencia.py`](gen_referencia.py) · manifiesto: [`gen_manifiesto.py`](gen_manifiesto.py).

Los archivos completos viven en `docs/tecport/referencia/`, **excluida de git** por peso. Lo versionado es [REFERENCIA_ESTRUCTURA.md](REFERENCIA_ESTRUCTURA.md), con nombre, tamaño, líneas, campos por línea, MD5 y muestra de cada archivo — que es lo que se necesita para validar.

### Estructura capturada (la especificación a cumplir)

| Libro | Campos/línea | Líneas 2026-01 | Líneas 2026-03 |
|---|---:|---:|---:|
| 1.1 Caja | — | 0 (vacío) | 0 (vacío) |
| 1.2 Bancos | 15 | 24 | 34 |
| 5.1 Diario | 21 | 13 391 | 7 145 |
| 5.2 Diario simplificado | 21 | 13 391 | 7 145 |
| 5.3 / 5.4 Plan contable | 8 | 1 242 | 1 242 |
| 6.1 Mayor | 21 | 13 391 | 7 145 |
| **8.4 Compras RCE nacional** | **38** | 575 | 394 |
| **8.5 Compras RCE no domiciliados** | **36** | 37 | 4 |
| 13.1 Inventario valorizado | 26 | 25 | 38 |
| **14.4 Ventas RVIE** | **34** | 101 | 89 |

Los tres formatos que el plan marca como clave (8.4, 8.5, 14.4) se entregan **dentro de un ZIP**, no como TXT suelto — detalle de la nomenclatura SUNAT que la implementación debe respetar.

### ⚠ Defectos detectados en el proyecto origen

La exportación reveló tres problemas, verificados por MD5 sobre datos reales:

1. **5.1, 5.2 y 6.1 generan un archivo byte a byte idéntico.** El Libro Diario, el Diario Simplificado y el Libro Mayor son tres libros con estructuras distintas en la norma; aquí los tres emiten las mismas 21 columnas y las mismas líneas. Confirmado en los dos periodos (`0af6a4de02f3` en marzo, `a8e02d609410` en enero).
2. **5.3 y 5.4 también son idénticos** (`548828d06dbb` / `d73e325f0a20`). Son el anexo de plan contable, correcto en sí, pero duplicado entre los dos libros.
3. **Anomalía de periodo:** en el libro de marzo, 120 de 7 145 líneas (1,7 %) llevan periodo `202605` y `202606` en el campo 1, todas con estado PLE `1` («mismo periodo»). O el campo periodo no respeta el periodo del reporte, o el estado debería ser `8`. Requiere verificación al implementar; no es concluyente sin conocer el criterio exacto de selección.

**Consecuencia para el plan:** refuerza la decisión ya tomada de **reconstruir 5.1, 5.3, 5.2, 5.4 y 6.1 sobre los handlers de Enterprise 19**, que sí los implementa por separado, en lugar de portar los generadores del origen. También obliga a matizar el criterio de aceptación nº 1.

### Corrección al criterio de aceptación nº 1

El criterio original —«TXT idéntico en estructura al de la v18»— **no es válido para 5.1, 5.2, 5.3, 5.4 y 6.1**, porque la referencia está defectuosa. Para esos cinco formatos la referencia es la **especificación de SUNAT** y la salida de Enterprise 19, no el proyecto origen.

Sigue siendo válido para: 1.2, 8.4, 8.5, 13.1 y 14.4.

---

## 4. Dependencias Python — inventario corregido

El `requirements.txt` del proyecto origen declara tres paquetes que **ningún módulo importa** y omite los ocho que sí se usan.

### Declarado en origen (incorrecto)

```
pdf417gen==0.7.1     ← no se importa en ningún módulo
PyPDF2==2.12.1       ← no se importa en ningún módulo
Babel==2.9.1         ← no se importa en ningún módulo
```

### Dependencias reales, verificadas por análisis de imports

| Paquete | Módulos que lo usan | Estado en el entorno v19 | Nota para la migración |
|---|---:|---|---|
| `xlsxwriter` | 8 | ✅ 3.1.9 | los 8 libros; imprescindible para el XLSX de revisión |
| `requests` | 4 | ✅ 2.31.0 | eFact y los 3 proveedores de tipo de cambio |
| `lxml` | 2 | ✅ 5.2.1 | EDI |
| `zeep` | 1 | ✅ 4.2.1 | **en v19 se importa como `odoo.tools.zeep`**, no como paquete externo — verificado disponible |
| `num2words` | 1 | ✅ | importe en letras del formato de factura |
| `pytz` | 1 | ✅ 2025.2 | conversión a hora de Lima en el formato 13.1 |
| `python-dateutil` | 1 | ✅ 2.8.2 | programación del cron de tipo de cambio |
| `markupsafe` | 1 | ✅ 2.1.5 | mensajes de error del EDI |

**Ninguna dependencia nueva que instalar:** las ocho ya están disponibles en el entorno v19, y `zeep` se consume desde `odoo.tools`. El proyecto destino no necesita `requirements.txt` propio.

---

## 5. Resumen de la Fase 0

| Tarea | Estado |
|---|---|
| Auditoría de licencias y procedencia | ✅ hecha — ver [FASE0_ACTA_LICENCIAS.md](FASE0_ACTA_LICENCIAS.md) |
| Decisión de licencia | ✅ **vía B, clean-room** |
| Entorno v19 de desarrollo | ✅ ya existía (`ol_pe_v19`, puerto 19700) |
| Base de referencia v18 con datos reales | ✅ localizada (`tecport-mtest`, TECPORT PERU, 13 822 asientos) |
| Autorización de exportación | ✅ concedida (solo compañía TECPORT PERU) |
| TXT/XLSX/PDF de referencia | ✅ generados — 16/16 libros, 60 archivos, 0 errores |
| Manifiesto de estructura versionado | ✅ [REFERENCIA_ESTRUCTURA.md](REFERENCIA_ESTRUCTURA.md) |
| Estrategia de validación | ✅ definida y **corregida** tras detectar defectos en la referencia |
| Inventario de dependencias | ✅ corregido — ninguna que instalar |
| Relación con Mobilize Spa. (1 módulo OPL-1) | ⛔ pendiente de confirmar; entretanto se trata en clean-room |

**Fase 0 cerrada.** Siguiente: Fase 1 (base y catálogos) o, si se prioriza valor, Fase 3 (RCE/RVIE) — cuyos requisitos de estructura ya están capturados arriba.

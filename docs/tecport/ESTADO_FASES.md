# Estado de las fases

Seguimiento del [plan de unificación](ANALISIS_Y_PLAN_TECPORT_L10N_PE.md).
Actualizado el 15/08/2026.

| Fase | Estado | Entregable |
|---|---|---|
| **0 · Preparación** | ✅ | [Acta de licencias](FASE0_ACTA_LICENCIAS.md) · [Entorno y validación](FASE0_ENTORNO_Y_VALIDACION.md) · [Referencia](REFERENCIA_ESTRUCTURA.md) |
| **1 · Base y catálogos** | ✅ | `al_account_base` v2.20260815 |
| **2 · Tipo de cambio** | ✅ | `al_l10n_pe_currency` — proveedor BCRP |
| **3 · RCE 8.4 / 8.5** | ✅ | [Estructura](ESTRUCTURA_RCE_8_4_8_5.md) · `al_l10n_pe_ple` v4 |
| **3b · RVIE 14.4** | ✅ | [Estructura](ESTRUCTURA_RVIE_14_4.md) |
| **3c · Bug SQL de Enterprise** | ✅ | [Diagnóstico y arreglo](BUG_EE_RCE_SQL.md) |
| **4 · Contraste de formatos** | ✅ | [Decisión](FASE4_CONTRASTE_FORMATOS.md) — no había duplicación real |
| **8 · TXT de detracciones** | ✅ | `al_l10n_pe_detraction` v4.20260815 |
| **5 · XLSX de revisión de los registros SIRE** | ✅ | botón «XLSX» junto al TXT en los tres informes |
| 6 · Serie/correlativo en el apunte | **descartada** | ver abajo: perdió su justificación |
| 7 · EDI OSE | pendiente | requiere un WSDL de pruebas de un OSE real |
| 9 · Documentación de usuario | parcial | |

---

## Lo entregado

### Fase 1 — Base y catálogos

Campos que alimentan los libros, en `al_account_base`:

| Campo | Modelo | Para qué |
|---|---|---|
| `l10n_pe_annex_code` | `res.partner` | establecimiento anexo (libros de inventario y guías) |
| `l10n_pe_bank_code` | `res.partner.bank` | entidad financiera, tabla 3 del PLE (libro 1.2) |
| `l10n_pe_journal_kind` | `account.journal` | distingue apertura y cierre de los movimientos |
| `l10n_pe_exclude_from_books` | `account.journal` | excluye diarios auxiliares de los libros |

La exclusión de diarios ya está **conectada al extractor del RCE y del RVIE**: los comprobantes de
un diario marcado no entran en los registros.

**Descartado del plan original:** la validación estructural de RUC/DNI. Odoo ya la hace en
`base_vat` + `l10n_latam_base`, y se comprobó funcionando (rechaza un RUC de 3 dígitos con el
mensaje del formato esperado). Añadir otra capa habría duplicado el core.

**Nota de diseño:** ninguno de los campos usa `size`. Truncar convertiría un valor erróneo en uno
válido —«123» pasaría a «12», que es otro banco— y el libro saldría mal sin aviso. Se prefiere
rechazar el valor.

### Fase 2 — Tipo de cambio

Nuevo proveedor **BCRP** en `al_l10n_pe_currency`, con las series del sistema bancario SBS
(`PD04639PD` compra, `PD04640PD` venta) — las que SUNAT toma para efectos tributarios, no las
interbancarias.

Resuelve una limitación real: hasta ahora los históricos dependían de apis.net.pe, que puede
exigir token o limitar por frecuencia. El BCRP es gratuito, sin autenticación, y devuelve **el
rango completo en una sola llamada** en vez de una consulta por día.

El asistente permite elegir la fuente; «Hoy» sigue tomándose del TXT de SUNAT.

**Descartado:** múltiples tasas por día. Odoo 19 impone unicidad por (moneda, compañía, fecha) y
romperla obligaría a tocar el ORM nativo; es una necesidad de nicho que no compensa el riesgo.

### Fase 8 — Depósito masivo de detracciones

Archivo de ancho fijo del Banco de la Nación, en las dos modalidades del instructivo oficial
(adquiriente `*` y proveedor `P`), con cabecera de 68 caracteres y detalle de 107.

Añade el campo **cuenta de detracciones del Banco de la Nación** en el contacto y el **tipo de
operación SPOT** (tabla 5.5) en la factura.

El asistente valida antes de entregar el archivo —el banco rechaza el lote completo si una línea
no mide lo que debe— y **lista los comprobantes excluidos con su motivo** en vez de omitirlos en
silencio.

Ejemplo generado:

```
*20512528458SERVICIOS ANDINOS DEMO S.A.C.      260001000000000070800
620601034809                                            022000712345670000000000708000120260301F00100002644
```

---

### Fase 5 — XLSX de revisión

El TXT es el archivo legal, pero ilegible: 41 columnas sin cabecera separadas por pipes. Los tres
informes del SIRE ofrecen ahora un botón **XLSX** junto al de TXT, con las mismas líneas y una
cabecera por nombre de campo, reutilizando el generador de Excel que el módulo ya tenía para los
demás libros PLE.

Un test comprueba que el número de columnas de cada hoja coincide con el número de campos del
archivo legal (41, 35 y 33), de modo que una futura corrección de la estructura no pueda dejar el
Excel desalineado.

---

## Cobertura de tests

| Módulo | Tests |
|---|---:|
| `al_l10n_pe_ple` | 85 |
| `al_l10n_pe_detraction` | 43 |
| `al_l10n_pe_currency` | 17 |
| `al_account_base` | 9 |
| **Total** | **154** |

---

## Fase 6 descartada, y por qué

El plan justificaba llevar la serie y el correlativo al apunte contable
(`account.move.line.serie_correlative`) como **prerrequisito de los libros**: era la vía por la que
el proyecto origen alimentaba sus consultas SQL.

Con el enfoque adoptado esa necesidad desaparece. El extractor trabaja sobre `account.move` y toma
la serie y el número de `l10n_latam_document_number`, que es el campo nativo de la localización.
Añadir el dato al apunte —con su índice y su cron de reparación— sería duplicar información ya
disponible, con el coste de mantenerla sincronizada.

Si en el futuro hiciera falta (por ejemplo para un libro diario propio que Enterprise no cubra),
puede recuperarse; hoy no aporta.

---

## Pendiente

**Fase 7 — EDI OSE.** Es lo único de valor que queda del proyecto origen sin migrar. Dos
obstáculos: hay que reescribir el XML UBL contra la API de nodos de v19 (el generador cambió por
completo), y **no se puede validar sin un WSDL de pruebas de un OSE real**. Antes de acometerla
conviene verificar caso por caso qué resuelve ya `l10n_pe_edi` nativamente: puede que buena parte
de los 14 overrides del origen sobren.

**Verificación con datos reales.** Todo lo entregado se ha probado con fixtures y con comprobantes
creados a mano en `ol_pe_v19`. Falta contrastar **un cierre mensual completo** contra la base de
referencia `tecport-mtest` —compañía TECPORT PERU, periodos 2026-01 y 2026-03—, que es lo que da
confianza para producción. Los archivos de referencia ya están generados; falta portar un juego de
datos equivalente a la base v19.

**Reporte en pantalla vs exportación.** El motor ORM sustituye al de Enterprise en ambos casos,
pero solo se ha verificado con volúmenes pequeños. Sobre miles de comprobantes conviene medir:
la extracción itera los apuntes en Python, y ahí Enterprise era más rápido aunque estuviera roto.

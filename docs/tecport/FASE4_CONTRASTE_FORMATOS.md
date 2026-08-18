# Fase 4 — Contraste de los formatos que aparecían duplicados

El [análisis inicial](ANALISIS_Y_PLAN_TECPORT_L10N_PE.md) marcaba tres formatos como
«contrastar»: había más de una implementación candidata y hacía falta elegir una para no
acabar con dos cifras distintas del mismo mes. Verificado el 15/08/2026.

**Conclusión: no había duplicación real en ninguno de los tres.** No hay nada que descartar.

---

## 12.1 / 13.1 — Inventario permanente

Parecía el caso más claro de duplicación: `l10n_pe_reports_stock` (Enterprise) y
`ol_stock_kardex_pe` (propio) generan ambos el kardex. Verificado en código, **producen cosas
distintas**:

| Módulo | Qué produce | Papel |
|---|---|---|
| `l10n_pe_reports_stock` (EE) | **TXT legal** con la nomenclatura `LE…1201…` / `LE…1301…` | presentación a SUNAT |
| `ol_stock_kardex_pe` (propio) | **XLSX y PDF** (`file_format` solo admite `xlsx` y `pdf`) | revisión interna e impresión |

`ol_stock_kardex_pe` no emite ningún TXT. Es exactamente la capa de presentación que el
análisis identificaba como valor del proyecto origen —los XLSX y PDF de los libros—, ya
implementada.

**Decisión: los dos se quedan.** Son complementarios, no alternativas. El único riesgo real es
que las cifras difieran entre el TXT y el XLSX; convendría un contraste de importes cuando haya
volumen de inventario en la base de pruebas, que hoy no lo hay.

---

## 5.2 / 5.4 — Diario simplificado

| Implementación | Estado |
|---|---|
| `al_l10n_pe_ple` | los genera (`export_52`, `export_54`) |
| Enterprise 19 | **no** los genera — solo 5.1 y 5.3 |
| `tecport/l10n_pe` | los generaba, pero su salida **está defectuosa**: el 5.2 es byte a byte idéntico al 5.1 y al 6.1 (ver [REFERENCIA_ESTRUCTURA.md](REFERENCIA_ESTRUCTURA.md)) |

**Decisión: se queda `al_l10n_pe_ple`.** No hay competencia: Enterprise no cubre estos formatos y
la implementación del origen no es utilizable, además de quedar fuera por el
[régimen clean-room](FASE0_ACTA_LICENCIAS.md).

---

## 7.1 / 7.3 / 7.4 — Activos fijos

| Implementación | Estado |
|---|---|
| `al_l10n_pe_ple` | genera los tres formatos |
| Enterprise 19 | no los genera |
| `tecport/l10n_pe` | generaba 7.1 y 7.4, pero el módulo estaba **desinstalado** en la base de referencia y la compañía no tenía ni un activo fijo, así que no hay salida con la que contrastar |

**Decisión: se queda `al_l10n_pe_ple`,** que además cubre un formato más (7.3, diferencia de
cambio).

---

## Resultado de la fase

| Formato | Decisión | Motivo |
|---|---|---|
| 12.1 / 13.1 | conservar **ambos** | EE hace el TXT legal, el kardex propio el XLSX/PDF |
| 5.2 / 5.4 | conservar `al_l10n_pe_ple` | nadie más lo cubre correctamente |
| 7.1 / 7.3 / 7.4 | conservar `al_l10n_pe_ple` | nadie más lo cubre |

La fase no requiere cambios de código. Queda una verificación pendiente para cuando haya datos:
**contrastar los importes del TXT 13.1 de Enterprise con los del XLSX de `ol_stock_kardex_pe`**
sobre el mismo periodo, para confirmar que ambas vías cuentan lo mismo.

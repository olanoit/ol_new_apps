# Fase 0 — Acta de licencias y procedencia del código origen

Documento de soporte para la decisión de reutilización de `tecport/l10n_pe`.
Ver el plan completo en [ANALISIS_Y_PLAN_TECPORT_L10N_PE.md](ANALISIS_Y_PLAN_TECPORT_L10N_PE.md).

**Estado: DECIDIDO — vía B, clean-room.** (Decisión del titular, 15/08/2026.)

---

## 1. Procedencia verificada

| Dato | Valor |
|---|---|
| Repositorio | `git@github.com:MobilizeTI/Tecport.git` |
| Ruta local | `/home/och/odoo/ce18/mblz/tecport` |
| Rama analizada | `master` |
| Rango de commits | 10/12/2024 – 13/08/2026 |
| Commits totales del repo | 92 |

### Autoría por volumen de commits

| Autor | Commits | Rol aparente |
|---|---:|---|
| Dfunn1k `<danychavezdev@gmail.com>` | 42 | autor principal de `l10n_pe` (33 de sus commits) |
| dulivu `<GeorgeL1102@gmail.com>` | 25 | — |
| Dany Chavez `<danychavezdev@gmail.com>` | 10 | mismo autor que Dfunn1k |
| Felipe Angulo `<ti@mobilize.cl>` | 7 | Mobilize |
| **olanoit `<olanoit@gmail.com>`** | **4** | **titular de este proyecto** |
| Felipe Angulo Achurra `<felipe@pudutechnology.cl>` | 2 | — |
| williamIT207, MobilizeTI | 2 | — |

**Dato relevante:** el titular de este proyecto tiene commits de escritura en el repositorio origen (los módulos `mblz_import_management`, `mblz_l10n_pe_multicurrency_revaluation` y `mblz_account_reports`). No se trata de código ajeno obtenido de un tercero sin relación: existe acceso y participación en el repositorio. Lo que **no** consta en el repositorio es el acuerdo que regula esa participación.

---

## 2. Licencias declaradas

| Licencia | Módulos | Autor declarado |
|---|---:|---|
| `Other proprietary` | **58** | IT SERVICE S.A.C. (`www.itservice.com.pe`) |
| `OPL-1` | 1 | Mobilize Spa. (`mobilize.cl`) |
| `LGPL-3` | 1 | IT SERVICE |

- **No hay archivo `LICENSE` ni `COPYING`** en el repositorio.
- **No hay cabeceras de copyright** en ningún archivo `.py` (0 coincidencias en 21 400 LOC).
- Los 58 módulos de IT SERVICE fueron añadidos por `Dfunn1k` entre el 30/04/2026 y el 01/07/2026.

### Los dos módulos que no son de IT SERVICE

| Módulo | Licencia | Autor | Primer commit | Situación |
|---|---|---|---|---|
| `mblz_l10n_pe_multicurrency_revaluation` | OPL-1 | Mobilize Spa. | 11/08/2026 por **olanoit** | Aportado por el propio titular; su reutilización depende del acuerdo con Mobilize, no de IT SERVICE |
| `its_editar_digito_decimal` | **LGPL-3** | IT SERVICE | 26/06/2026 | **Libremente reutilizable.** Es el único módulo sin restricción — y es uno de los que el plan descarta por irrelevante |

---

## 3. Qué significa `Other proprietary`

Es el valor que Odoo reserva para código propietario que **no** se distribuye bajo OPL-1. No concede ningún derecho de uso, copia, modificación ni redistribución. En ausencia de un contrato que diga otra cosa, **copiar ese código a la suite `al_*` sería una infracción**, y lo seguiría siendo aunque el código se reorganice o se renombre, porque la obra derivada conserva la protección de la original.

Esto afecta a **58 de los 60 módulos**, incluidos todos los que el plan marca como valiosos: RCE/RVIE, libros físicos, proveedor OSE, framework de tipo de cambio y TXT de detracciones.

---

## 4. Lo que sí es reutilizable sin permiso

La protección cubre **la expresión** (el código concreto), no **los hechos ni los métodos**. Queda fuera de la licencia:

1. **La normativa SUNAT.** Las estructuras de los formatos PLE (8.4, 8.5, 14.4, 5.x, 6.1, 1.x, 7.x, 13.1), la longitud y el orden de sus campos, los códigos de catálogo, las reglas de inclusión y las nomenclaturas de archivo son contenido de resoluciones de superintendencia: son públicos y no los posee IT SERVICE.
2. **El conocimiento del dominio.** Que exista un estado PLE 1/8/9, que la fecha SUNAT deba poder diferir de la contable, que los diarios se puedan excluir del registro de compras/ventas, o que el Banco de la Nación acepte un TXT de detracciones en dos modalidades: todo eso son hechos del negocio.
3. **La arquitectura como idea.** Que convenga un modelo base de periodo, un wizard despachador y generadores separados por formato es una decisión de diseño, no una obra protegida — siempre que la implementación se escriba de nuevo.
4. **El análisis ya realizado** en este proyecto: el mapa de qué formatos existen, cuáles cubre Enterprise 19 y cuáles no, y qué rompe en la migración.

---

## 5. Las tres vías posibles

| Vía | Qué implica | Riesgo legal | Coste |
|---|---|---|---|
| **A — Autorización expresa** | Obtener de IT SERVICE S.A.C. una cesión o licencia escrita que permita derivar y redistribuir. Permite copiar y adaptar el código directamente | Nulo si se documenta | Depende de la negociación |
| **B — Clean-room** | Usar `tecport/l10n_pe` **solo como mapa de requisitos** (qué formatos, qué campos, qué casos) y escribir la implementación desde la documentación oficial de SUNAT. No se copia ni se adapta código | Bajo, si se documenta la fuente de cada formato | +20–30 % de esfuerzo sobre el plan |
| **C — Abandonar** | Descartar el proyecto origen y quedarse con la cobertura actual de `al_*` + Enterprise | Nulo | Se pierden RCE/RVIE, PDF físicos, OSE y multiproveedor de tipo de cambio |

### Recomendación

**Vía B (clean-room) por defecto, salvo que exista ya un acuerdo que habilite la vía A.**

Razones:
- Es el método que la suite `al_*` **ya viene aplicando**: el módulo SIRE se construyó desde los manuales oficiales de SUNAT en PDF, no desde código de terceros. La práctica está establecida y ha funcionado.
- El valor real de `tecport/l10n_pe` para este proyecto no está en su código —que hay que reescribir de todos modos por las dos rupturas de la v19 (generador UBL y consultas SQL)— sino en **saber qué hay que construir**. Ese conocimiento ya está extraído en el documento de análisis y su uso no está restringido.
- El sobrecoste es menor de lo que parece: el plan ya contempla reescribir el UBL desde cero, rehacer todas las consultas SQL y sustituir 16 implementaciones duplicadas por un mixin. Buena parte del código origen no se iba a copiar tal cual en ningún caso.

Si se elige la vía B, conviene además **no leer el código origen mientras se implementa** cada formato: trabajar sobre la especificación de SUNAT y sobre el documento de análisis, y reservar el proyecto origen para verificar cobertura funcional al cerrar cada fase.

---

## 6. Decisión adoptada — vía B (clean-room)

**Fecha:** 15/08/2026. **Decisión del titular del proyecto.**

Las fases 1 a 9 se ejecutan en modo clean-room. No se copia ni se adapta código de `tecport/l10n_pe`.

### Reglas operativas

1. **Fuente de verdad = normativa SUNAT.** Cada formato se implementa desde la resolución de superintendencia y el anexo de estructura correspondiente. Antes de escribir un generador, se localiza y se cita la especificación en la cabecera del módulo o en el documento de la fase.
2. **El proyecto origen solo se usa como mapa de requisitos.** Se puede consultar para saber *qué* hay que construir (qué formatos, qué campos, qué casos especiales, qué configuración se necesita) y para verificar cobertura funcional al cerrar una fase. No se abre para saber *cómo* está escrito mientras se implementa.
3. **Los datos de salida sí son comparables.** Los TXT que produce el proyecto origen son el resultado de aplicar una norma pública a unos datos: su estructura (nº de campos, longitudes, orden, nomenclatura del archivo) es un hecho verificable, no una obra protegida. Se usan como referencia de validación — ver [FASE0_ENTORNO_Y_VALIDACION.md](FASE0_ENTORNO_Y_VALIDACION.md) y [REFERENCIA_ESTRUCTURA.md](REFERENCIA_ESTRUCTURA.md).
4. **Cero copia literal**, tampoco de fragmentos: ni consultas SQL, ni cadenas de formato, ni nombres de campo del origen. Los nombres de campo siguen la convención propia (`l10n_pe_*` de la suite `al_*`).
5. **Excepción documentada:** `its_editar_digito_decimal` es LGPL-3 y podría reutilizarse libremente, pero el plan lo descarta por irrelevante. No aplica.
6. **`mblz_l10n_pe_multicurrency_revaluation`** (OPL-1, Mobilize Spa., aportado por el propio titular) queda fuera de la restricción de IT SERVICE. Si se confirma titularidad propia o cesión, su fusión en `al_l10n_pe_exchange_closure` puede hacerse por la vía A. **Pendiente de confirmar.**

### Impacto en el plan

- El sobrecoste estimado (+20–30 %) se concentra en las fases 3, 5 y 7, donde había código sustancial que en la vía A se habría adaptado.
- No afecta a las fases 1, 2, 4, 6, 8 ni 9, cuyo trabajo era en su mayoría de diseño o de reescritura obligada.
- **Beneficio colateral ya materializado:** la validación de la Fase 0 detectó tres defectos en los generadores del origen (ver [REFERENCIA_ESTRUCTURA.md](REFERENCIA_ESTRUCTURA.md), sección de archivos idénticos). Reimplementar desde la norma evita heredarlos.

### Punto pendiente

**¿Cuál es la relación con Mobilize Spa.** respecto a `mblz_l10n_pe_multicurrency_revaluation`? Mientras no conste aquí, ese módulo también se trata en clean-room.

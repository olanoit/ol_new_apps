Historial de cambios — Planillas Perú - Importadores Excel (AL)
===============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_import.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 5.20261007 — 07/10/2026

- Seguridad: un valor del archivo que empieza por «=» ya no se escribe como fórmula en el Excel de resultados.

## 4.20260816 — 27/09/2026

- Solo se puede importar en una compañía a la que el usuario tiene acceso.
- Al importar datos de versiones, la AFP y los demás catálogos se toman de la compañía del asistente o globales, nunca de otra compañía.
- Una celda de salida vacía ya no borra la salida registrada al actualizar asistencias.
- Límite de 20 MB por archivo y 50 000 filas por hoja.
- Una importación sin avance durante 30 minutos se marca como interrumpida en vez de quedarse «Procesando».
- El botón «Importar desde Excel» solo aparece a quien puede usar el asistente.

## 3.20260816 — 18/08/2026

- Menú «Importar desde Excel» al final de Nómina.

## 2.20260722 — 26/07/2026

- La plantilla se descarga sin guardar el asistente.
- Opción para adaptar el código de las reglas salariales de la versión anterior.
- Las asistencias aceptan el documento además del nombre.

## 1.20260722 — 25/07/2026

- Primera versión para Odoo 19. Motor de importación con progreso en vivo e importadores de planilla.

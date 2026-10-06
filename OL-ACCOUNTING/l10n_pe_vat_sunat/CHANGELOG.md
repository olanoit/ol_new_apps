Historial de cambios — Búsqueda RUC/DNI desde SUNAT
===================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/l10n_pe_vat_sunat.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 10.20260828 — 27/09/2026

- El token de cada conexión solo lo ven los administradores; el resto de usuarios sigue consultando RUC y DNI con normalidad.
- Cada compañía ve solo sus propias conexiones RUC/DNI y sus mapeos.
- Las conexiones RUC/DNI se pueden crear y borrar desde la lista (antes estaba bloqueado).
- Buen contribuyente y agente de retención: si la API ya trae el dato se respeta, y el padrón solo completa lo que falta. Con el padrón aún sin descargar ya no se desmarcan las casillas.
- Una descarga del padrón SUNAT sin RUCs ya no vacía la caché; y tras cada descarga diaria se actualizan las casillas de los contactos.
- Un estado o condición SUNAT desconocido ya no hace fallar la consulta: se ignora ese dato y se completa el resto.
- La consulta automática al escribir el RUC/DNI es más rápida (sin reintentos) y ya no crea representantes ni locales anexos si luego se descarta el contacto; eso queda para el botón «Actualizar desde API».
- La sincronización del padrón solo la lanza la acción planificada.

## 14/09/2026

- Menús de la app Perú reordenados; consultas RUC/DNI agrupadas en Configuración.

## 8.20260828 — 28/08/2026

- Los ajustes de RUC/DNI se ven dentro de la sección Perú de Ajustes (antes salían en blanco).
- Padrón SUNAT y conexiones RUC/DNI también en la app Perú.

## 6.20260827 — 27/08/2026

- Buen contribuyente y agente de retención editables en el contacto, como fuente única de las excepciones de retención.

## 5.20260815 — 18/08/2026

- Nueva conexión Decolecta (RUC contra SUNAT y DNI contra RENIEC), añadida también en bases ya instaladas.

## 1.20260717 — 16/07/2026

- Consulta configurable por datos, mapeo de campos, fallback en cascada y padrón SUNAT con descarga diaria.

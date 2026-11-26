Historial de cambios — Formato común de documentos impresos (AL)
================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_report_base.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261126.5 — 26/11/2026

- La vista previa en pantalla (portal del cliente) ya no muestra «Página de» sin números en el pie: la numeración de páginas sale solo en el PDF.

## 20261126.4 — 26/11/2026

- La cabecera gris de las tablas sigue el borde redondeado: ya no se pinta en ángulo recto en las esquinas superiores (comprobantes, guías, boletas, valorizaciones, kárdex y demás documentos con este diseño).

## 20261027.3 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261011.2 — 23/10/2026

- Casillas de firma report_pe_sign_boxes: un rectángulo por paso (elaboró, cada nivel de aprobación, conformidad) con rol, nombre, cargo y fecha (requerimiento CREVAL v1.0, 3.12).

## 20261011.1 — 11/10/2026

- Formato común de los documentos impresos de la suite, tomado del comprobante A4: encabezado, pie, hoja de estilos pe-doc- y papel A4 vertical y horizontal.
- Plantilla report_pe_page: página completa en una sola llamada.

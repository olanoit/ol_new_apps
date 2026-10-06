Historial de cambios — Open PDF Reports and PDF Attachments in Browser
======================================================================

Módulo de Ivan Sokolov y Cetmix. Aquí se registran su incorporación a este
repositorio y los cambios locales hechos sobre la versión original.

## 19.0.1.0.1 — 28/09/2026

- Cambio local: una sola cabecera `Content-Disposition` al descargar un informe. Con dos, Chrome rechazaba la respuesta y fallaba la impresión de comprobantes desde el TPV.
- Cambio local: las opciones del informe ya no se decodifican dos veces, lo que convertía «+» en espacios y rompía «%».
- Cambio local: API de usuario de Odoo 19 y pruebas de las cabeceras y de la URL del informe.

## 19.0.1.0.0 — 01/09/2026

- Incorporado sin cambios desde la versión de Cetmix para Odoo 19.

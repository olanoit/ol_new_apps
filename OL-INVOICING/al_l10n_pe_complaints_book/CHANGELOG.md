Historial de cambios — Perú - Libro de Reclamaciones
====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_complaints_book.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 7.20261009 — 09/10/2026

- Ícono propio en el menú principal (libro abierto con un signo de admiración), con el estilo del de la app Perú (fondo de color y trazo blanco), para no confundirlo con la app oficial de Soporte; en Aplicaciones sigue el ícono nativo.

## 6.20261009 — 09/10/2026

- Etiquetas más cortas en el reclamo: «Fecha de respuesta», «Tipo según el consumidor», «Confirmado por el consumidor», «N.º de hoja de respaldo»; en el libro, «Domicilio». El detalle pasa a la ayuda (?).

## 5.20261008 — 08/10/2026

- Etiquetas en español: campos propios sin texto (Compañía, Moneda, Nombre del archivo…) y campos heredados (creado por, seguidores, actividades) traducidos con su i18n/es.po.

## 4.20261008 — 08/10/2026

- Los asistentes validan en el servidor que lo que reciben sea de su compañía (_check_company_auto y check_company).

## 3.20261008 — 08/10/2026

- «Obligada al SIREC» es del RUC: las sucursales usan el valor de su raíz.
- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 2.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 1.20261006 — 06/10/2026

- Primera versión: libros por establecimiento, formulario web sin registro, constancia en PDF, plazo de 15 días hábiles con feriados, oferta de solución, respuesta, SIREC, aviso del Anexo II y multicompañía.

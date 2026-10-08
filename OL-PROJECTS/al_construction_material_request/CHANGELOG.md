Historial de cambios — Requerimiento de materiales de obra (AL)
===============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_material_request.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 7.20261008 — 08/10/2026

- Etiquetas en español: los campos sin etiqueta propia (Activo, Nombre, Compañía, contadores…) y los heredados de Odoo (Creado por, Mensajes, Actividades…) ya no se muestran en inglés.

## 6.20261008 — 08/10/2026

- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 5.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 01/10/2026

- El reparto entre stock y compra sigue el algoritmo de la regla nativa «tomar de stock; si no hay, activar otra regla»: cálculo en la unidad del producto y el resto en la unidad de la línea, de modo que lo despachado más lo comprado siempre da lo pedido.
- Lo recibido en obra se calcula como en Compras: conversión con redondeo al medio y las devoluciones de la obra al almacén restan.
- Las transferencias del requerimiento comparten una referencia de inventario, como las de una orden de compra.

## 3.20261001 — 01/10/2026

- Corregido el error al agregar un material en un requerimiento nuevo (Expected singleton: uom.uom()).

## 2.20260930 — 30/09/2026

- Primera versión: requerimiento de obra, aprobación por niveles, división stock o compra por línea, compra vía almacén central o directo a obra, y cierre y cancelación automáticos.
- Ajustes propios de la app y menú de reglas de aprobación.
- Materiales como tarjetas en el celular; calendario por fecha requerida y vista de actividades.
- Mensajes del chatter legibles, también los del requerimiento de compra al confirmar la orden de compra.
- Vale de requerimiento de obra en PDF (botón «Imprimir vale»).
- Interfaz completamente en español, incluidos los campos de actividades, seguidores y aprobación.

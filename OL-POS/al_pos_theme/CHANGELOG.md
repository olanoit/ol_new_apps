Historial de cambios — TPV - Tema y marca blanca (AL)
=====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_pos_theme.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 8.20261027 — 13/11/2026

- Teclado numérico por caja (Ajustes ▸ Apariencia): visible, oculto con botón para abrirlo o sin teclado; el mismo estado en la venta y en el pago, y sin línea seleccionada queda deshabilitado en vez de desaparecer.
- Línea seleccionada del ticket con quitar, -/+ y cantidad editable; «Edición de cantidad» elige entre escribir en la línea, teclado en pantalla o automático.
- El ticket ya no salta al cambiar cantidades: sólo se desplaza si la línea seleccionada no se ve y la selección no parpadea.
- Medios de pago en una fila compacta con desplazamiento horizontal; los que tienen pago se marcan con «✓ monto» y otro clic (o la ×) quita sus pagos sin procesar.
- Tras un cobro ya procesado con saldo pendiente, tocar el medio agrega una línea por el saldo sin tocar lo cobrado.
- Montos rápidos de efectivo en el pago: exacto y redondeos a los billetes de la caja.
- Colores de la marca en los filtros del catálogo, las facetas, el control Cuadrícula | Lista y las fichas de stock por almacén de la vista de productos.
- Categorías con el botón «Todas», marca en la categoría actual y borde en sus ancestros.
- El indicador de sincronización de la barra superior ya no parpadea con cada llamada corta al servidor.
- La pantalla del cliente muestra el cambio sin signo menos.

## 7.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.
- El favicon y el ícono de la app del TPV siguen siendo la caja registradora neutra (static/src/img/icon.svg).

## 6.20261022 — 22/10/2026

- El buscador enfocado muestra un solo halo (antes se veían dos anillos, uno dentro del otro); igual en el buscador del historial de tickets.

## 5.20261022 — 22/10/2026

- Las categorías se muestran u ocultan desde la caja con el botón «Categorías» de la barra superior; el ajuste de la caja (ahora «Mostrar u ocultar categorías») activa ese botón. Cada dispositivo recuerda la elección.

## 4.20261022 — 22/10/2026

- Ajuste «Ocultar categorías de productos» por caja en Apariencia.

## 3.20261018 — 18/10/2026

- El nombre de la marca en la barra (cuando la caja no tiene logo) va a la izquierda y con puntos suspensivos: un nombre largo ya no se corta por el principio.

## 2.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 05/10/2026

- Primera versión en la suite: marca neutra por defecto, textos en español y compatibilidad con los módulos TPV de la suite.

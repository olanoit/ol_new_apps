Historial de cambios — Planificación de obra: compras y abastecimiento (AL)
===========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_purchase.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20261023 — 23/10/2026

- Paquete 1.11, M111-09: el resumen de inventario compacto pasa a «PE - Base Inventario» (al_stock_base), para que se vea también sin el planificador; aquí ya no se modifica la vista.
- Paquete 1.11, M111-12: la compra masiva y el tablero de abastecimiento redondean a planchas enteras los tableros indivisibles (la unidad «Plancha L×A m» tiene referencia m² y antes no se redondeaba).

## 8.20261021 — 21/10/2026

- Resumen de inventario: botones pequeños y en una sola línea (en las tarjetas angostas se partían y se veían más grandes).

## 7.20261021 — 21/10/2026

- Resumen de inventario compacto: sin gráficos en las tarjetas de los tipos de operación, tarjetas más angostas y etiquetas en español (Con demora, En espera, Órdenes parciales, Movimientos).

## 6.20261021 — 21/10/2026

- Paquete 1.11, M111-06: líneas del plan del material bajo el nivel y la etapa del pedido, con o sin asignaciones, para las cifras de la solicitud de aprobación.

## 5.20261016 — 16/10/2026

- La línea agregada a mano toma el nivel y la etapa del recuadro cuando hay uno solo elegido.
- Las etapas del requerimiento son las del perfil de vertical de la obra (y las que usa su plan).
- Una fecha de necesidad del plan ya pasada propone hoy como fecha requerida.
- La regla «Exceso sobre el plan» mira la política de materiales aplicada al requerimiento y no la general del plan: con materiales en «Solo alerta» ya no pide aprobación.

## 4.20261016 — 16/10/2026

- Requerimiento de obra con selección de nivel y etapa: niveles en cascada según la plantilla de la obra, etapas, tareas del Gantt y botón «Traer materiales del plan» (una línea por material, nivel y etapa con el saldo, enlazada al plan).
- Material de la etapa Producción a la preproducción de la planta, en su propia transferencia, con ajuste para permitirlo o no.

## 3.20261016 — 16/10/2026

- Requerimientos y compras con la política de exceso del plan (v1.8, M18-05): repetición dentro de la tolerancia y registro del exceso autorizado.
- Tablero de abastecimiento sin costos ni montos para quien no tiene el grupo de montos (M18-10).

## 2.20261013 — 15/10/2026

- Compra masiva (M17-08): agrupa también por etapa, partida y receta, con el nombre del grupo en cada línea del requerimiento.
- El tipo de operación de la compra se llama «Tipo de recepción», para no confundirlo con el destino.

## 1.20261013 — 15/10/2026

- Puente nuevo (v1.7, M17-07): compras, requerimientos de obra y abastecimiento salen del núcleo.

Historial de cambios — Planificación de obra: producción y requerimiento de obra (AL)
=====================================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_mrp_request.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 3.20261025 — 26/10/2026

- CR-16: aquí se suman al plan los consumos de las órdenes de fabricación al validar (antes en el puente de compras, que no depende de Fabricación).

## 2.20261025 — 25/10/2026

- La reposición a planta avisa al jefe de producción o, sin él, a los responsables de Fabricación, y lo deja como responsable de la orden; nunca a quien pide (verificación en dev1).

## 1.20261025 — 25/10/2026

- Paquete 1.11, M111-22: «Cubrir con retazo» y «Quitar retazo» en el despacho del requerimiento de obra; la línea cuenta la fracción cubierta y su redondeo; el despacho a la preproducción de una planta usa el tipo «Elegir componentes» del almacén.
- Paquete 1.11, M111-23: «Pedir reposición a planta» (menú Requerimientos y botón del requerimiento): orden en borrador en el tipo de reposición con el motivo, actividad al jefe de producción, estados según la orden y el despacho, y despacho a obra al terminar.

Historial de cambios — Planificación de obra: todos los puentes (AL)
====================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_suite.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 13.20261021 — 21/10/2026

- Pruebas del despacho por unidad con material sin departamento y con productos de módulo.

## 12.20261021 — 21/10/2026

- Prueba del departamento tomado de las líneas del requerimiento en el despacho a obra por unidad.

## 11.20261021 — 21/10/2026

- Prueba de que la solicitud de una versión nueva del plan muestra 0 %.

## 10.20261021 — 21/10/2026

- Pruebas del paquete 1.11 (M111-02 a M111-06), con una que revisa que ninguna vista del planificador use funciones que el navegador no evalúa.

## 9.20261019 — 19/10/2026

- Pruebas del paquete 1.10 (fabricación por etapas, despacho por departamento, lote, motivo de posventa y aprobaciones en bloque).

## 8.20261018 — 18/10/2026

- Las reglas de aprobación de ejemplo ya no llevan el prefijo «[DEMO]».

## 7.20261017 — 17/10/2026

- Los datos de demostración se instalan en una base nueva: las reglas de aprobación de ejemplo apuntaban a un modelo y un grupo sin el prefijo de `al_construction_planner`.

## 6.20261017 — 17/10/2026

- Pruebas de accesorios con la orden que ya trae los accesorios de su lista de materiales.

## 5.20261017 — 17/10/2026

- Instala también `al_construction_planner_production`; pruebas de accesorios de armado y presupuestado frente a real (M19-02 y M19-05).

## 4.20261017 — 17/10/2026

- Instala también `al_construction_planner_approvals_mrp`; pruebas del exceso en la orden de fabricación (M19-04).

## 3.20261017 — 17/10/2026

- Instala también `al_construction_planner_approvals`; pruebas del paquete 1.9 (aprobaciones en la aplicación Aprobaciones y ambiente medido).

## 2.20261013 — 15/10/2026

- Instala también `al_construction_planner_sale_furniture`; pruebas de operación nativa (compras con tres proveedores, spools de tuberías, cuadrilla por rol) y del perfil mobiliario sobre la demo.
- Obra de prueba de la contrata eléctrica: tablero con dos sistemas y cuatro partidas, compra masiva por partida, contrata de cableado por punto y control por tablero y sistema.

## 1.20261013 — 15/10/2026

- Módulo nuevo (v1.7, M17-07): reúne los puentes y las pruebas de integración.

Historial de cambios — Planificación de obra: presupuesto y control (AL)
========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_construction_planner_budget.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261101.9 — 16/11/2026

- Seguridad: confirmar una orden de compra que pasa el presupuesto con la marca de «ya revisado» en el contexto ya no se salta el asistente ni la autorización de la jefatura.
- Seguridad: el resultado del control de presupuesto de la orden lo escribe el sistema; ya no se puede escribir a mano.

## 20261101.8 — 01/11/2026

- D3: ajuste «Planes que controla el presupuesto»: la compra se compara solo con las líneas del presupuesto que coinciden en esos planes; vacío, como antes.
- M116-05: el presupuesto nativo del plan se rehace con las cuentas actuales (niveles y rubro) sin perder lo comprometido ni lo real.
- M116-01: la etapa del consumo que llega sin etapa se elige entre las del perfil de la obra.

## 20261027.6 — 27/10/2026

- Paquete 1.12, M112-02: el consumo de una orden de obra ya no recibe la primera etapa de fabricación del hook de apuntes: la trae el movimiento.

## 20261027.5 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261016.4 — 26/10/2026

- CR-16: el apunte de un consumo sin Fabricación instalada ya no lee la orden de fabricación del movimiento.

## 20261016.3 — 24/10/2026

- Al cancelar un plan aprobado o en ejecución, su presupuesto analítico queda Cancelado.

## 20261016.2 — 16/10/2026

- El control de presupuesto usa la política de exceso de material del plan (v1.8, M18-05).

## 20261013.1 — 15/10/2026

- Puente nuevo (v1.7, M17-07): el presupuesto analítico sale del núcleo.

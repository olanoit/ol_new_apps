Historial de cambios — Planificación de obra: aprobaciones en fabricación (AL)
==============================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_construction_planner_approvals_mrp.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261027.9 — 16/11/2026

- Seguridad: el estado, el porcentaje y el «aprobado por» del exceso de la orden de fabricación los escribe el sistema; antes, escritos a mano, la orden empezaba sin la aprobación.

## 20261027.8 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261024.7 — 24/10/2026

- El jefe de producción ve el Gantt de proyectos (grupo Gantt: usuario, que incluye Proyecto: usuario); el plan de recursos sigue en solo lectura.

## 20261024.6 — 24/10/2026

- El jefe de producción solo consulta el planificador (Plan: consulta): ya no edita planes, dependencias, cambios ni liquidaciones. Sigue aprobando el exceso de la orden dentro de su margen.

## 20261023.5 — 23/10/2026

- Requerimiento CREVAL v1.0, capítulo 5: accesos, menús y botones con los grupos en dos ejes (Plan: consulta, planificador, aprueba; Ejecución: reporta avance, ejecuta, valida, aprueba).

## 20261023.4 — 23/10/2026

- Paquete 1.11, M111-12: «Presupuestado frente a requerido» compara la necesidad de los tableros y muestra aparte el «Redondeo a plancha entera», que no cuenta como exceso.

## 20261021.3 — 21/10/2026

- Paquete 1.11, M111-05: la solicitud de exceso lleva el % de la orden, el mismo que ve la planta.

## 20261019.2 — 19/10/2026

- Paquete 1.10, M110-04 y M110-08: la comparación de la orden usa solo las etapas de su lista de materiales y la solicitud lleva lo presupuestado de la orden.

## 20261017.1 — 17/10/2026

- Puente nuevo (paquete 1.9, M19-04): exceso en la orden de fabricación con aprobación del jefe de producción y Aprobaciones.

Historial de cambios — Planificación de obra: aprobaciones (AL)
===============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_approvals.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 8.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 7.20261021 — 25/10/2026

- Paquete 1.11, M111-21: con «Aplicación Aprobaciones», el requerimiento interno va a Aprobaciones con el jefe del departamento de quien pide o, sin jefe, con el grupo de la opción M111-19 C; sin grupo se aprueba al solicitarlo, como con los niveles.

## 6.20261021 — 23/10/2026

- Requerimiento CREVAL v1.0, capítulo 5: accesos, menús y botones con los grupos en dos ejes (Plan: consulta, planificador, aprueba; Ejecución: reporta avance, ejecuta, valida, aprueba). La oficina técnica sale de la selección y equivale a Plan: planificador más Ejecución: valida.

## 5.20261021 — 21/10/2026

- La solicitud de una versión nueva del plan muestra 0 % de exceso: lo que sube frente a la versión vigente solo elige los tramos de la tabla de rutas.

## 4.20261021 — 21/10/2026

- Paquete 1.11, M111-02: el asistente «Rechazar» vuelve a abrir desde la solicitud y desde la lista (la vista usaba len(), que el navegador no evalúa).
- M111-05: el «Exceso %» de la solicitud es el del documento de origen con su regla (la orden de fabricación según la base del margen de la compañía); el mayor % por material sigue en cada línea.
- M111-06: presupuestado, ya pedido, saldo y % del requerimiento salen de todas las líneas del plan del material bajo el nivel y la etapa, aunque el pedido ya tenga asignada solo una parte.

## 3.20261019 — 19/10/2026

- Paquete 1.10, M110-07: la lista de Aprobaciones muestra documento, obra, «En el plan», exceso % y cantidad, con filtros «Me toca aprobar» y «Fuera del plan», y aprueba o rechaza en bloque solo las que le tocan al usuario.
- M110-08: la solicitud muestra presupuestado, ya pedido, saldo, pedido y exceso; con saldo negativo el exceso nunca supera lo pedido. Una solicitud ya aprobada cuyo documento siguió no se rechaza desde Aprobaciones.

## 2.20261017 — 17/10/2026

- Tipo de documento «Orden de fabricación» en la tabla de rutas (con el puente de aprobaciones en fabricación) y los campos de la solicitud se recalculan al crearla.

## 1.20261017 — 17/10/2026

- Puente nuevo (paquete 1.9, M19-03 y M19-07): plan y requerimiento de obra en Aprobaciones, con tabla de rutas, tramos en escalera, aprobadores por grupo, aprobar o rechazar desde el documento y el resultado de vuelta.

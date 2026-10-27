Historial de cambios — Planificación de obra: orden de fabricación del mueble (AL)
==================================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_production.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 5.20261019 — 23/10/2026

- Requerimiento CREVAL v1.0, capítulo 5: accesos, menús y botones con los grupos en dos ejes (Plan: consulta, planificador, aprueba; Ejecución: reporta avance, ejecuta, valida, aprueba).

## 4.20261019 — 19/10/2026

- Paquete 1.10, M110-04: «Pedir accesorios» y su aviso salen de las etapas marcadas «Accesorios a pedido desde la orden» (ya no del código de armado) y el informe compara solo las etapas de la orden. M110-08: cifras de la solicitud del pedido de accesorios.

## 3.20261018 — 18/10/2026

- Confirmar la orden sin accesorios ya no falla para el comprador: el aviso a Logística se arma aunque no pueda leer las compañías de los demás usuarios.

## 2.20261017 — 17/10/2026

- El pedido de accesorios no vuelve a proponer lo que la orden ya trae en sus componentes (prueba en dev1 del 17-oct).

## 1.20261017 — 17/10/2026

- Puente nuevo (paquete 1.9, M19-02 y M19-05): accesorios de armado desde la orden y presupuestado frente a real en la orden y en el planificador.

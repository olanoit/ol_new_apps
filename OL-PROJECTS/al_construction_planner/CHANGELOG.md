Historial de cambios — Planificación de obra (AL)
=================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20261010 — 10/10/2026

- Asignaciones y compras (fase 4, P-10 y P-11): cada documento generado desde el plan guarda qué parte corresponde a cada línea; lo comprado, despachado y consumido se reparte por fecha de necesidad.
- Pedido, comprado, despachado, consumido, saldo, comprometido, real y estado calculado de cada línea (excedida, completa, en compra, parcial, planificada).
- Asistentes «Compra masiva» (con analítica de la obra o stock general), «Requerimiento de obra» (por ambiente, departamento o piso) y «Orden de fabricación» (por piso o selección desde la BOM), en la barra del árbol y en el plan.
- Control de exceso al solicitar la aprobación del requerimiento de obra y al confirmar la OF, según la política del plan, con justificación y revisión adicional de la jefatura (W-10).
- Menú «Abastecimiento»; las asignaciones abiertas pasan a la versión nueva y el plan no se cierra con documentos abiertos.

## 3.20261010 — 10/10/2026

- Línea base (fase 3, P-03): flujo del plan con «Solicitar aprobación», aprobación por niveles (reglas de aprobación), rechazo a borrador y cierre.
- La aprobación crea el presupuesto analítico (una línea por combinación de cuentas), congela los montos y deja la versión anterior en «Reemplazado».
- Asistentes «Aplicar costo» (último precio, ponderado de 3 o 6 meses o manual, con su fecha) y «Nueva versión» (todo o solo saldos, con motivo).
- Pestaña «Resumen por etapa» y menú «Análisis del plan» con pivote y gráfico.

## 2.20261010 — 10/10/2026

- Árbol de recursos (fase 2, P-02): obra › piso › departamento › ambiente › módulo cargado por niveles, con módulos, ML y montos de cada nivel.
- Selección en cascada con barra de resumen y panel de recursos acumulados de la selección; filtros por etapa, tipo de recurso, estado del módulo y contrata.
- Botón «Árbol de recursos» en el plan; el menú «Árbol de la obra» pasa a llamarse «Tareas de la obra».

## 1.20261010 — 10/10/2026

- Primera versión (fase 1): niveles de obra en las tareas, tipologías con módulos, actividades y lista de materiales, actividades y tarifas de contrata, etapa de consumo en la BOM, plan de recursos con versiones y el asistente «Generar plan» con vista previa y advertencias.
- Ícono propio en el menú principal: edificio de pisos con las barras de su plan.

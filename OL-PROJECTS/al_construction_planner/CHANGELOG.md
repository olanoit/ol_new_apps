Historial de cambios — Planificación de obra (AL)
=================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261010 — 10/10/2026

- Control y personal propio (fase 7, P-13): estado de la línea y montos de control (comprometido, real, saldo, % ejecutado) guardados, filtrables y agrupables; pestaña «Control» del plan y «Análisis de control» en pivote y gráfico.
- La OC con analítica de la obra se contrasta al confirmarla con el presupuesto analítico de su combinación según la política del plan (W-10).
- «Asignar cuadrilla» (W-06): turnos por obrero y semana con la tarea y la línea del plan; las horas registradas suben el ejecutado y el real, los turnos sin horas son el comprometido.
- «Cambiar fechas» (W-08): desplaza n días o lleva a una fecha nueva la selección por etapas, recalcula la fecha de necesidad y avisa a Logística con una actividad en los requerimientos y OC desfasados.
- Revertir un avance validado baja el estado del módulo; los botones del árbol «Asignar cuadrilla» y «Cambiar fechas» quedan activos.

## 5.20261010 — 10/10/2026

- Contratas (fase 5, P-05 a P-07 y P-09): «Asignar contrata» con tarifa vigente, monto y retención por actividad; pone la contrata en las líneas y suma el alcance a la OC de servicio de la contrata en la obra.
- Avance reportado (AVN) por driver con fotos obligatorias, «Registrar avance» con el saldo por módulo o ambiente y la tolerancia del plan, y «Avances por validar» por obra, contrata y semana.
- Ejecutado, liquidado y avance de cada línea; avance valorizado de los niveles en el árbol y en la pestaña «Recursos y avance» de la tarea; estado del módulo automático.
- Liquidación semanal (fase 6, P-08): LIQ por contrata, obra y semana con acción programada en el día de liquidación, aprobación de la jefatura, recepción en la OC y factura con vencimiento el día de pago; «Pagada» con la factura pagada.
- Semana de la obra configurable (inicio, liquidación y pago) con valores por defecto en Ajustes; feriados al día hábil anterior; el plan no se cierra con liquidaciones pendientes.

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

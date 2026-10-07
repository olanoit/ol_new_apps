Historial de cambios — Planillas Perú - Asistencia y turnos (AL)
================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_attendance.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20261007 — 07/10/2026

- Turnos nocturnos con la convención estándar de Odoo (lunes 22-24 y martes 00-06): el turno se lee completo. Antes el lunes salía con 6 h extra falsas y el sábado como falta.

## 8.20261007 — 07/10/2026

- Un cierre de la compañía o un medio feriado ya no se tratan como feriado completo con sobretasa del 100 %: solo cuentan los feriados del calendario peruano.

## 7.20261007 — 07/10/2026

- Las horas nocturnas del tareaje van por defecto a «Horas trabajo nocturno» y alimentan la sobretasa nocturna de la boleta (antes quedaban solo informativas).
- Corregido: quien llegaba tarde y se quedaba después de hora cobraba esas horas como extras y además se le descontaba la tardanza. Ahora ese tiempo primero completa la jornada y solo el exceso es sobretiempo.

## 6.20260816 — 27/09/2026

- El turno nocturno cuenta como día trabajado completo en la boleta; antes el básico salía casi en cero.
- Al trabajar en un día de descanso o feriado se conserva el pago del descanso y se suma el día trabajado.
- Quien olvida marcar la salida queda como marcación incompleta, no como falta.
- Los feriados y las ausencias se leen en hora de Perú; el día siguiente al feriado ya no sale como feriado.
- No se pueden aplicar dos tareajes con fechas solapadas para los mismos trabajadores, ni reabrir uno ya usado en boletas cerradas.
- En el monitor, el documento de identidad solo lo ve Recursos Humanos y el usuario de Planning solo ve sus propias filas.
- «Sujeto a horas extras» aparece en la pestaña de nómina de la ficha y se lee de la versión vigente del periodo.

## 5.20260816 — 18/08/2026

- El menú pasa a llamarse «Asistencia» y se ubica tras Entradas de trabajo.

## 4.20260802 — 02/08/2026

- El calendario de feriados peruanos es dependencia obligatoria para detectar el feriado laborado.

## 3.20260722 — 26/07/2026

- Los turnos nocturnos que cruzan la medianoche ya no se leen como marcación incompleta.

## 2.20260722 — 25/07/2026

- Primera versión para Odoo 19. Ciclos atípicos, monitor de asistencia, fotocheck y tareaje.

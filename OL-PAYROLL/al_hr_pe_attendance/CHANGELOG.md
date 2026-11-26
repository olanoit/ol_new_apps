Historial de cambios — Planillas Perú - Asistencia y turnos (AL)
================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_hr_pe_attendance.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261027.23 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261012.22 — 12/10/2026

- Asistencia pasa a Entradas de trabajo ▸ Asistencia (registro, tareaje, monitor, asignaciones de ciclo) y Configuración ▸ Asistencia (ciclos atípicos, fotocheck).

## 20261010.20 — 10/10/2026

- La plantilla de turno de la asignación de ciclos atípicos se valida contra la compañía del trabajador (multicompañía).

## 20261010.19 — 10/10/2026

- Centro de costo del día en la marcación y en el detalle del tareaje (se copia de la marcación al generar). La boleta reparte su costo entre los centros de costo por días o por horas (Ajustes ▸ Perú: tareaje ▸ Reparto del costo por obra); los días sin centro de costo van a la ficha del trabajador.

## 20261009.18 — 09/10/2026

- Chatter en la gestión de tareaje: historial del estado y del periodo.

## 20261008.17 — 08/10/2026

- Tareaje aplicado: el detalle diario queda de solo lectura; el botón de detalle de cada línea solo aparece si la línea tiene días cargados.

## 20261008.16 — 08/10/2026

- Etiquetas en español: los campos sin etiqueta propia (Activo, Nombre, Compañía, contadores…) y los heredados de Odoo (Creado por, Mensajes, Actividades…) ya no se muestran en inglés.

## 20261008.15 — 08/10/2026

- Horario nocturno, horas extra, tolerancia y redondeo del tareaje en Ajustes ▸ Nómina ▸ Perú.
- El registro de asistencia valida que los trabajadores sean de su compañía.

## 20261008.14 — 08/10/2026

- Métodos de botón con la convención de Odoo (action_close, action_reopen, action_show_details); «Ver detalle» con el ícono genérico de Odoo (fa-list) en vez del ojo.

## 20261008.13 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 20261008.12 — 08/10/2026

- Asignación de ciclo de turnos con el trabajador como título.

## 20261008.11 — 08/10/2026

- «Sujeto a horas extras» pasa a «Planilla PE ▸ T-Registro»; el tareaje muestra su nombre como título; nombre legible en el monitor de asistencia.

## 20261007.10 — 07/10/2026

- Registro de control de asistencia (D.S. 004-2006-TR) en Excel: razón social y RUC del empleador, documento y nombre del trabajador, ingreso, salida e inicio y fin del sobretiempo de cada día, listo para una inspección de SUNAFIL. Usa el mismo cálculo que el tareaje, así que cuadra con la boleta.

## 20261007.9 — 07/10/2026

- Turnos nocturnos con la convención estándar de Odoo (lunes 22-24 y martes 00-06): el turno se lee completo. Antes el lunes salía con 6 h extra falsas y el sábado como falta.

## 20261007.8 — 07/10/2026

- Un cierre de la compañía o un medio feriado ya no se tratan como feriado completo con sobretasa del 100 %: solo cuentan los feriados del calendario peruano.

## 20261007.7 — 07/10/2026

- Las horas nocturnas del tareaje van por defecto a «Horas trabajo nocturno» y alimentan la sobretasa nocturna de la boleta (antes quedaban solo informativas).
- Corregido: quien llegaba tarde y se quedaba después de hora cobraba esas horas como extras y además se le descontaba la tardanza. Ahora ese tiempo primero completa la jornada y solo el exceso es sobretiempo.

## 20260816.6 — 27/09/2026

- El turno nocturno cuenta como día trabajado completo en la boleta; antes el básico salía casi en cero.
- Al trabajar en un día de descanso o feriado se conserva el pago del descanso y se suma el día trabajado.
- Quien olvida marcar la salida queda como marcación incompleta, no como falta.
- Los feriados y las ausencias se leen en hora de Perú; el día siguiente al feriado ya no sale como feriado.
- No se pueden aplicar dos tareajes con fechas solapadas para los mismos trabajadores, ni reabrir uno ya usado en boletas cerradas.
- En el monitor, el documento de identidad solo lo ve Recursos Humanos y el usuario de Planning solo ve sus propias filas.
- «Sujeto a horas extras» aparece en la pestaña de nómina de la ficha y se lee de la versión vigente del periodo.

## 20260816.5 — 18/08/2026

- El menú pasa a llamarse «Asistencia» y se ubica tras Entradas de trabajo.

## 20260802.4 — 02/08/2026

- El calendario de feriados peruanos es dependencia obligatoria para detectar el feriado laborado.

## 20260722.3 — 26/07/2026

- Los turnos nocturnos que cruzan la medianoche ya no se leen como marcación incompleta.

## 20260722.2 — 25/07/2026

- Primera versión para Odoo 19. Ciclos atípicos, monitor de asistencia, fotocheck y tareaje.

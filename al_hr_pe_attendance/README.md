# Planillas Perú — Asistencia y turnos

Turnos peruanos sobre la planificación nativa, ciclos atípicos con
validación legal, monitor de asistencia, fotocheck y el tareaje que
convierte las marcaciones en conceptos de la boleta.

> **Versión** 4.20260802 · **Depende de** `al_hr_pe`, `planning`,
> `hr_payroll_planning`, `hr_attendance`, `hr_payroll_attendance`,
> `hr_holidays`, `al_hr_pe_public_holidays` · **Licencia** LGPL-3

---

## 1. Qué incluye

* **Turnos peruanos** sobre el rol nativo de planificación, con la jornada
  nocturna detectada en la propia plantilla del turno.
* **Ciclos atípicos N×M** (D.S. 004-2006-TR) —los regímenes de campamento
  y mina, 14×7 o 20×10— con validador legal: promedio semanal de 48 horas
  y tope de 12 al día.
* **Monitor de asistencia**: turno planificado frente a marcación real,
  respetando la zona horaria de cada recurso.
* **Fotocheck**: configuración por compañía y carné en QWeb.
* **Tareaje**: clasifica las horas del periodo según la norma peruana y
  las vuelca a la boleta como conceptos de trabajo.

## 2. Las reglas que aplica el tareaje

| Concepto | Regla | Norma |
|---|---|---|
| Nocturnidad | 22:00 a 06:00 | art. 8 D.S. 007-2002-TR |
| Horas extras | 25 % las dos primeras, 35 % después | art. 10 D.S. 007-2002-TR |
| Descanso y feriado laborado | 100 % | D.Leg. 713 |

Los tramos y porcentajes son **parámetros de compañía**, no números
escritos dentro del cálculo.

> **Por qué exige el calendario de feriados.** El feriado se detecta
> leyendo los descansos globales del calendario laboral. Sin
> `al_hr_pe_public_holidays`, un 28 de julio trabajado se pagaría como
> jornada ordinaria y no se aplicaría la sobretasa del 100 %. Por eso es
> una dependencia obligatoria y no una recomendación.

## 3. Cómo se usa, paso a paso

1. **Definir los turnos** — en los roles y plantillas de planificación;
   los que cruzan la noche se marcan como nocturnos en la plantilla.
2. **Configurar los ciclos atípicos si los hay** — *Planillas →
   Asistencia PE*. El validador comprueba el promedio semanal y el tope
   diario antes de dejar generar nada.
3. **Generar la planificación** — los turnos se crean respetando la zona
   horaria del recurso, no la del servidor.
4. **Revisar el monitor** — planificado contra real, para detectar el
   turno sin marcación **antes** de calcular la planilla.
5. **Procesar el tareaje** — *Planillas → Tareaje*: clasifica las horas y
   las vuelca a la boleta como conceptos de trabajo, listas para que las
   reglas las paguen.
6. **Imprimir fotochecks** — desde la ficha del empleado.

## 4. Qué se hizo distinto

La versión anterior clonaba la planificación de Odoo Enterprise en unas
2 700 líneas. Aquí se **extiende** la nativa: los turnos son
`planning.slot` de verdad, con su gantt, sus permisos y sus futuras
mejoras incluidas.

## 5. Tests

```bash
odoo-bin -d <bd> -u al_hr_pe_attendance --test-enable \
         --test-tags /al_hr_pe_attendance
```

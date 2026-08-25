# Feriados peruanos

Diez años de feriados oficiales —2026 a 2035— aplicados a los calendarios
laborales con un clic, y renovados solos cada año.

> **Versión** 2.20260802 · **Depende de** `hr_holidays`, `hr_work_entry` ·
> **Licencia** OPL-1

---

## 1. Qué incluye

* **Diez años cargados**: todos los feriados oficiales de 2026 a 2035, los
  de fecha fija y los religiosos de fecha móvil — que son los que nadie
  quiere calcular a mano.
* **Un clic al calendario**: se aplican como ausencias a todos los
  calendarios laborales activos, que es lo que hace que las asignaciones
  de vacaciones salgan bien desde el primer día.
* **Renovación automática**: una tarea programada aplica el año nuevo cada
  2 de enero.
* **Medio día o día completo**, configurable por feriado, con marcas de
  tiempo que respetan la zona horaria de cada calendario.

## 2. Por qué importa en la planilla

No es solo un tema de vacaciones. El **tareaje** decide si un día es
feriado leyendo los descansos del calendario, y de ahí sale la sobretasa
del **100 % por feriado laborado** del D.Leg. 713.

> Sin este calendario, un 28 de julio trabajado se contaría como jornada
> ordinaria. Por eso `al_hr_pe_attendance` lo declara como dependencia
> obligatoria.

Los descansos llevan además el tipo de entrada de trabajo con el que la
nómina computa el feriado.

## 3. Cómo se usa, paso a paso

1. **Revisar la lista** — vienen todos cargados; se pueden desactivar los
   que una empresa no aplique o marcar los de medio día.
2. **Aplicar a los calendarios** — todos los calendarios laborales activos
   reciben los feriados como ausencias, almacenadas en UTC pero
   respetando su zona horaria.
3. **Olvidarse** — la tarea programada aplica el año siguiente cada 2 de
   enero.

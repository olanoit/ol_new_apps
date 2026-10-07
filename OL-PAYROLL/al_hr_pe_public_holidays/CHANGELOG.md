Historial de cambios — Planillas Perú - Feriados (AL)
=====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_public_holidays.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 8.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 7.20261008 — 08/10/2026

- El feriado muestra su nombre como título; años sin separador de miles.

## 6.20261007 — 07/10/2026

- Feriados por régimen laboral: el 25 de octubre, Día del Trabajador de Construcción Civil (2026-2035), solo se aplica a los calendarios de los trabajadores de construcción.

## 5.20261007 — 07/10/2026

- La aplicación automática de feriados alcanza a todas las compañías, también a las creadas después (antes solo a las del usuario técnico).

## 4.20260827 — 27/09/2026

- El Domingo de Resurrección deja de figurar como feriado: no es feriado legal en el Perú. Quedan 16 feriados por año y los descansos que ya se habían creado para ese domingo se borran al actualizar.
- El campo de medio día pasa a llamarse **Half Day Rest Until**: indica la hora hasta la que dura el descanso, que empieza a las 00:00.

## 27/08/2026

- Los descansos ya no se desplazan cinco horas por la zona horaria del usuario que los aplica.

## 2.20260802 — 02/08/2026

- Integración con la planilla peruana, tipo de entrada de trabajo por feriado, aplicación solo a las compañías activas y descansos sin duplicados.

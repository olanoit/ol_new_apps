Historial de cambios — Planillas Perú - Feriados (AL)
=====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_public_holidays.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20260827 — 27/09/2026

- El Domingo de Resurrección deja de figurar como feriado: no es feriado legal en el Perú. Quedan 16 feriados por año y los descansos que ya se habían creado para ese domingo se borran al actualizar.
- El campo de medio día pasa a llamarse **Half Day Rest Until**: indica la hora hasta la que dura el descanso, que empieza a las 00:00.

## 27/08/2026

- Los descansos ya no se desplazan cinco horas por la zona horaria del usuario que los aplica.

## 2.20260802 — 02/08/2026

- Integración con la planilla peruana, tipo de entrada de trabajo por feriado, aplicación solo a las compañías activas y descansos sin duplicados.

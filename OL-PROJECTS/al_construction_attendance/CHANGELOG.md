Historial de cambios — Sedes, marcación y costo de personal de obra (AL)
========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_attendance.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261016 — 16/10/2026

- La asistencia de la cuadrilla actualiza el ejecutado de sus días (v1.8); costo diario por empleado y categoría del rol; sedes de planta y creación automática de la sede de la obra.

## 2.20261013 — 13/10/2026

- La marcación con ubicación (app o quiosco de Odoo) sin sede toma la sede más cercana de la compañía y calcula su distancia y si está fuera de rango.

## 1.20261013 — 13/10/2026

- Sede de obra con ubicación, radio, hora límite de ingreso, etapa por defecto y quiosco de marcación con clave propia.
- Quiosco para el personal propio y el de las contratas (documento o PIN), con avisos de fuera de hora, fuera del radio y SCTR vencido.
- Personal y marcación de contratas, asistencia diaria y avances de contratas sin asistencia; parte diario de la cuadrilla en el portal (P-26).
- Marcación propia con distancia, fuera de rango y fuera de hora calculados desde la sede.
- Costo de la planilla por sede: la distribución analítica de la boleta suma la etapa de la sede y la partida MODF de la compañía (Ajustes).
- Cierre mensual de costo de personal (P-29): horas por sede por costo por hora, contra el plan, con publicación de los apuntes analíticos.

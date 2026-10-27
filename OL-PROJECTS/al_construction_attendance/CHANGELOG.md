Historial de cambios — Sedes, marcación y costo de personal de obra (AL)
========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_attendance.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 5.20261021 — 23/10/2026

- Requerimiento CREVAL v1.0, 4.3: la asistencia pasa a la sección Personal propio de Ejecución en el menú por momento.

## 4.20261021 — 21/10/2026

- Paquete 1.11, M111-01: «Con asistencia» del avance se calcula sin los permisos del usuario, así que la liquidación, la lista de avances y «Avances sin asistencia» abren sin grupos de Nómina; las sedes de obra siguen privadas de Nómina y la obra se lee o exporta sin ese campo.

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

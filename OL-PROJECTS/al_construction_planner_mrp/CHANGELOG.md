Historial de cambios — Planificación de obra: producción (AL)
=============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_mrp.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261023 — 23/10/2026

- Paquete 1.11, M111-12 (fase A): la orden de fabricación guarda la necesidad de cada tablero indivisible y al confirmarla pide planchas enteras por producto en toda la orden (la diferencia va al componente con más necesidad); el despacho a producción nace en enteros. Vale también para las órdenes que crea el abastecimiento y se vuelve a redondear al cambiar la cantidad a producir. El control de exceso mide la necesidad.
- Bloque «Planchas y retazos» en Ajustes ▸ Fabricación y aviso en la orden con necesidad, a entregar y redondeo.

## 5.20261021 — 21/10/2026

- Paquete 1.11, M111-03: «Estación de la etapa» y «Minutos por unidad» por compañía en el catálogo de etapas, para la operación de las listas por etapa.

## 4.20261019 — 19/10/2026

- Paquete 1.10, M110-01: cada etapa de fabricación del catálogo puede tener su planta (operación de fabricación) y la categoría del producto intermedio que entrega, por compañía, y la marca «Accesorios a pedido desde la orden».
- M110-03: el asistente de órdenes ya no impone la planta; cada orden nace en la planta de su lista de materiales y «Forzar planta» queda opcional.
- M110-04: la orden hija que crea Odoo por las rutas hereda el plan y los ambientes de la madre, se confirma sin el asistente de exceso y cada orden compara solo las etapas de su lista; el producto intermedio no es cambio de material.
- M110-06: motivo de fabricación obligatorio en los tipos de operación que lo piden (posventa, garantía, reposición), con lista configurable y etapa analítica.

## 3.20261016 — 16/10/2026

- Las órdenes de fabricación siguen la política de exceso de producción y registran el exceso autorizado (v1.8).

## 2.20261013 — 15/10/2026

- OF genérica (M17-09): sale de cualquier nivel con etapa de producción (spools, tableros, muebles) con su producto y su cantidad, no solo del ambiente de mobiliario.

## 1.20261013 — 15/10/2026

- Puente nuevo (v1.7, M17-07): las órdenes de fabricación desde el plan salen del núcleo.

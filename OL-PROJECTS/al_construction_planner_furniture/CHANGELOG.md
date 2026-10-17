Historial de cambios — Planificación de obra: rubro mobiliario (AL)
===================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_furniture.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20261017 — 17/10/2026

- Ambiente medido (paquete 1.9, M19-06): el supervisor marca el ambiente como medido con fecha y archivo, sin cantidades ni aprobación; lista de ambientes medidos por cargar a una orden para Optimización y aviso en la orden de los que no están marcados.
- En mobiliario, la orden de fabricación ya no espera al metrado con diferencia por aprobar.

## 3.20261016 — 16/10/2026

- Catálogo de mobiliario (v1.8): clase de módulo, tipo especial, método de unión con reglas, piezas y materiales por módulo; actividades de armado e instalación y listas de tarifas.
- Un producto por módulo al aprobar el plan, con su lista de materiales, fabricación y despacho de módulos a obra (M18-15).
- Receta real contra la planificada con umbral que bloquea la orden de fabricación.
- Importador de la proyección de materiales (M17-18) con validación de códigos contra Odoo (M17-19), y maestro de carga con piezas, productos nuevos, tarifas, obra, contratos, hitos y venta.

## 2.20261013 — 15/10/2026

- La OF del ambiente hereda la OF genérica del puente de producción; la familia de la partida pasa a `al_construction_planner_sale_furniture`.

## 1.20261013 — 15/10/2026

- Puente nuevo (v1.7, M17-07): lo propio del mueble (familia, módulos, ML, BOM y ETO) sale del núcleo.

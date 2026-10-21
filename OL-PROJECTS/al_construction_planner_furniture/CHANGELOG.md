Historial de cambios — Planificación de obra: rubro mobiliario (AL)
===================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_furniture.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20261021 — 21/10/2026

- El despacho a obra por unidad de un requerimiento toma el departamento de sus líneas cuando son de un solo departamento (al confirmar y al validar); con varios, se sigue pidiendo.

## 8.20261021 — 21/10/2026

- Paquete 1.11, M111-03: las listas por etapa sin operaciones reciben la de la estación de su etapa al importar, y la obra tiene «Completar operaciones» para las ya importadas; las operaciones puestas a mano se conservan.
- M111-04: la lista suma las cantidades por módulo ya redondeadas como el plan, así que la orden no sale «excede» por céntimos.

## 7.20261019 — 19/10/2026

- Paquete 1.10, M110-02: el importador separa en dos líneas un producto que está en dos etapas y, con cadena de plantas, arma una lista de fabricación por etapa (producto intermedio y lista final con los módulos como subproductos); la receta de la tipología queda detrás con secuencia 1000.
- M110-03: la orden del asistente usa la lista de fabricación de la tipología y lleva los módulos de sus ambientes, que pasan a «Producido» al cerrarla.
- M110-05: despacho a obra por departamento en el despacho nativo (obra y departamento obligatorios para validar); al validarlo los módulos que salieron pasan a «En obra» y se nombran los que faltan.
- M110-09: formato del lote del módulo configurable por compañía ({obra_prefijo}-{unidad_num}-{tipologia}-{modulo}).

## 6.20261017 — 17/10/2026

- El aviso de ambientes sin medir de la orden de fabricación nombra el departamento.

## 5.20261017 — 17/10/2026

- Con el exceso en la orden (paquete 1.9, M19-04), la autorización de la receta real ya no detiene la confirmación de la orden.

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

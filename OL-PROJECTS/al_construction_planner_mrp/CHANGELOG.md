Historial de cambios — Planificación de obra: producción (AL)
=============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_mrp.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 12.20261024 — 25/10/2026

- Sin «Jefe de producción» en Ajustes, la actividad «Revisar y confirmar fecha» va a los responsables de Fabricación de la compañía.

## 11.20261024 — 25/10/2026

- Paquete 1.7 parte 2, M17-18: cada orden que crea el asistente del plan lleva la actividad «Revisar y confirmar fecha» para el jefe de producción (Ajustes › Fabricación); la «Fecha confirmada» queda como fecha límite de la orden y mueve la etapa de producción de sus ambientes en el cronograma.
- Paquete 1.7 parte 2, M17-25: los avisos del asistente («Ya en una OF», metrado por aprobar, sin lista de materiales) dicen «Departamento / ambiente».
- Paquete 1.11, M111-22: columna «Retazo disponible» en el despacho: el retazo libre más chico que alcanza para la fracción; es un aviso, se usa con «Cubrir con retazo».

## 10.20261024 — 24/10/2026

- Paquete 1.11, M111-14: el jefe de producción («Fabricación: Usuario») declara sobrantes sin error de acceso, también si el producto retazo del tablero aún no existe.
- Paquete 1.11, M111-15: el retazo usado no cuenta como material sin presupuesto en «Presupuestado frente a requerido».
- Paquete 1.11, M111-16: un retazo que cubre todo un tablero deja la plancha en 0 sin cancelarla; «Quitar retazo» la vuelve a pedir y «Declarar sobrantes» la muestra.
- Paquete 1.11, M111-17: «Declarar sobrantes» marca los tableros sin entregar y deja declararlos cuando lleguen; terminar la orden exige solo los entregados.
- Paquete 1.11, M111-18: aviso de tablero sin área al declarar; cambiar la cantidad de la orden no multiplica el retazo.
- Paquete 1.11, M111-19 D: Ajustes › Fabricación › «Planchas y retazos» con alcance del redondeo, tolerancia del cuadre, «Piezas (m²)» editable con registro en el historial, formato del lote del retazo y verificación del despiece opcional.

## 9.20261023 — 23/10/2026

- Requerimiento CREVAL v1.0, capítulo 5: accesos, menús y botones con los grupos en dos ejes (Plan: consulta, planificador, aprueba; Ejecución: reporta avance, ejecuta, valida, aprueba).

## 8.20261023 — 23/10/2026

- La ubicación de retazos de la planta puede ser una vista con sububicaciones R25, R50, R75 y R99: cada retazo declarado entra a la de su banda, y el pool puede marcarse en la vista.

## 7.20261023 — 23/10/2026

- Paquete 1.11, M111-12 (fase B, retazos): producto retazo del tablero con una variante por banda (R25 a R99) y lote con largo, ancho, área, % de plancha, banda, orden y obra de origen; pool de retazos en las ubicaciones y ubicación de retazos por almacén.
- «Cubrir con retazo» y «Quitar retazo» en el despacho a producción: el retazo elegido cubre la fracción de la plancha, que baja a su entero.
- «Declarar sobrantes» en la orden de corte: retazos con lote y medidas como subproductos a su costo por área, devolución de las planchas sin tocar, cuadre con la merma y registro por tablero; opción para exigirlo antes de terminar.
- El aviso de consumo al terminar ya no salta por el redondeo a plancha entera ni por los retazos.

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

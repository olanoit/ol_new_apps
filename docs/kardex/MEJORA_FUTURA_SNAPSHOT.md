# Mejora futura — Snapshot de cierres para volúmenes extremos

> Continuación del límite anotado en
> [`ANALISIS_RENDIMIENTO.md`](ANALISIS_RENDIMIENTO.md) §5.
> Estado: **propuesta / no implementada**. La arquitectura actual (vista SQL con
> *window functions*) es suficiente para el rango objetivo (miles de
> movimientos/año). Este documento describe la evolución para cuando el volumen
> lo justifique.

## 1. Cuándo aplica (disparador)

Activar esta mejora solo si se cumplen **varias** de estas condiciones:

- Cientos de miles de movimientos valorados por año (`stock_move` con
  `is_in OR is_out`).
- Catálogo grande consultado en bloque (miles de productos en un mismo reporte).
- Kardex del **año completo** o consultas frecuentes de todo el histórico.
- Tiempo de respuesta del `SELECT` sobre la vista `l10n_pe_kardex_line` por
  encima de ~2–3 s de forma sostenida.

Por debajo de esos umbrales, **no implementar**: añade complejidad e
invalidación sin beneficio medible.

## 2. Diagnóstico del cuello de botella

La vista SQL calcula el saldo corrido con:

```sql
SUM(signed_qty) OVER (
    PARTITION BY product_id, company_id
    ORDER BY date, id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
```

`UNBOUNDED PRECEDING` obliga a PostgreSQL a **ordenar y recorrer la partición
completa de cada producto desde el primer movimiento histórico**, aunque el
reporte pida un solo mes. Con pocos miles de filas es milisegundos; con cientos
de miles y muchos productos a la vez, el *sort* + *window* domina el tiempo y se
repite en **cada** consulta (la vista no memoriza nada).

## 3. Solución propuesta: tabla de snapshots de cierre

Materializar el **saldo de cierre por período** (mes) en una tabla real
indexada. El cierre de un período es el saldo inicial del siguiente, de modo que
el reporte de un mes ya no recorre la historia: lee el cierre del mes anterior
(O(1) indexado) y solo corre la window **acotada a ese mes**.

### 3.1 Modelo / esquema

```python
class L10nPeKardexSnapshot(models.Model):
    _name = 'l10n_pe.kardex.snapshot'
    _description = 'Saldo de cierre de kardex por período'

    company_id   = fields.Many2one('res.company', required=True, index=True)
    product_id   = fields.Many2one('product.product', required=True, index=True)
    warehouse_id = fields.Many2one('stock.warehouse', index=True)  # NULL = consolidado
    period       = fields.Char(required=True, index=True)  # 'AAAAMM'
    date_close   = fields.Date(required=True)              # último día del período
    balance_qty   = fields.Float(digits='Product Unit')
    balance_value = fields.Float(digits=(16, 2))
    stale         = fields.Boolean(default=False, index=True)  # requiere recálculo

    _uniq = models.Constraint(
        'UNIQUE(company_id, product_id, warehouse_id, period)',
        'Ya existe un cierre para ese producto/almacén/período.')
```

Índice compuesto recomendado: `(company_id, warehouse_id, product_id, period)`.

### 3.2 Cómo lo consume el reporte

El motor (`_get_report_data` / la consulta de la vista) cambia a un patrón
**apertura + window acotada**:

```sql
-- opening = cierre del período anterior (lookup indexado, sin escanear historia)
SELECT s.balance_qty, s.balance_value
FROM l10n_pe_kardex_snapshot s
WHERE s.company_id = %(co)s AND s.product_id = %(p)s
  AND s.warehouse_id IS NOT DISTINCT FROM %(wh)s
  AND s.period = %(prev_period)s AND NOT s.stale;

-- saldo corrido dentro del período, sembrado con la apertura:
SELECT m.*,
       %(opening_qty)s + SUM(m.signed_qty) OVER w AS balance_qty,
       %(opening_val)s + SUM(m.signed_val) OVER w AS balance_value
FROM movimientos_del_periodo m
WINDOW w AS (ORDER BY m.date, m.id ROWS UNBOUNDED PRECEDING AND CURRENT ROW);
```

La window ahora recorre **solo los movimientos del mes**, no toda la historia.
La constante de apertura se suma como escalar (un `JOIN`/parámetro por producto).

> La vista `l10n_pe_kardex_line` actual se conserva como *fallback* y para el
> modo "todo el historial"; el snapshot solo acelera la consulta por período.

### 3.3 Poblado incremental

`_populate_period('AAAAMM')`:

1. Lee el cierre del período anterior (o 0 si es el primero).
2. Suma el **movimiento neto del período** (consulta acotada al mes).
3. `cierre = apertura + neto` → `upsert` en la tabla.

Es O(movimientos del mes), no O(historia). Encadenar meses es lineal. Idempotente
(recalcular un período sobrescribe sus filas).

Disparo:
- **Cron mensual** tras el cierre contable (pre-genera el snapshot del mes
  cerrado). Reutiliza el `ir.cron` ya existente o uno dedicado.
- **A demanda** al pedir un reporte cuyo período anterior no tiene snapshot
  vigente (lazy): se calcula la cadena faltante una sola vez.

### 3.4 Invalidación (el punto delicado)

Un movimiento **retroactivo** o un cambio de valorización en un período ya
cerrado invalida ese cierre y **todos los posteriores**. Estrategias, de menor a
mayor rigor:

1. **Marca `stale`**: un `create`/`write`/`unlink` de `stock.move` (o de
   `product.value`) con `date` dentro de un período con snapshot marca
   `stale=True` ese período y los siguientes de ese producto. El cron los
   recalcula. Barato de detectar, recálculo diferido.
2. **Recalcular en cascada** desde el período tocado hacia adelante en el mismo
   cron.
3. **Sellado por lock date**: alinear con las *lock dates* contables nativas de
   v19 (ya presentes en la localización) — impedir retroactividad en períodos
   cerrados hace el snapshot **inmutable** y elimina la invalidación. Es la
   opción más robusta si el negocio lo permite.

Recomendación: **(1) + (3)**. La marca `stale` cubre correcciones excepcionales;
las *lock dates* evitan el caso general.

### 3.5 Coexistencia y activación

- Ajuste por compañía `l10n_pe_kardex_use_snapshot` (Boolean, en
  `res.config.settings`). Desactivado por defecto → comportamiento actual
  (vista SQL sobre historia completa), 100 % compatible.
- Activado → el motor usa apertura-desde-snapshot + window acotada.
- Cambiar el flag no rompe datos: el snapshot es una capa de aceleración, la
  vista sigue siendo la fuente de verdad para recomputar.

## 4. Optimizaciones complementarias (menor esfuerzo, hacer primero)

Antes de construir el snapshot, medir con estas mejoras baratas:

- **Índice parcial/cubridor** en `stock_move`:
  ```sql
  CREATE INDEX idx_sm_kardex ON stock_move (company_id, product_id, date, id)
  WHERE state = 'done' AND (is_in OR is_out);
  ```
  Acelera directamente el *sort* de la window. Bajo riesgo, alto impacto.
- **`MATERIALIZED VIEW` nativa** de PostgreSQL con
  `REFRESH MATERIALIZED VIEW CONCURRENTLY` en un cron: más simple que el modelo
  de snapshots pero refresca todo el conjunto y tiene *staleness* global. Útil
  como paso intermedio si el índice no basta y no se quiere aún la lógica de
  cierres por período.

Orden sugerido de adopción: **índice parcial → materialized view → snapshot de
cierres**, activando cada nivel solo si la métrica lo exige.

## 5. Plan de implementación por fases

| Fase | Entregable | Estimación |
|---|---|---|
| F0 | Índice parcial + *benchmark* con dataset grande (medir antes/después) | 0.5 día |
| F1 | Modelo `l10n_pe.kardex.snapshot` + `_populate_period` incremental + tests | 2 días |
| F2 | Motor lee apertura desde snapshot (query acotada) tras flag de compañía | 2 días |
| F3 | Invalidación: marca `stale` en stock.move/product.value + recálculo cron | 1.5 días |
| F4 | Integración con *lock dates* (sellado de períodos) + ajustes settings | 1 día |
| F5 | Cron mensual de cierre + documentación + *benchmark* final | 1 día |

**Total estimado: ~8 días.** F0 puede evitar el resto si el índice ya resuelve.

## 6. Criterios de aceptación / métricas

- El kardex de un mes con snapshot vigente responde en **tiempo constante**
  respecto al tamaño del histórico (no crece con los años acumulados).
- Cuadratura idéntica a la vista SQL actual (mismo saldo final por producto,
  tolerancia de redondeo de precio) — test comparativo obligatorio.
- Recalcular la cadena completa de un producto = O(nº de períodos), verificable.

## 7. Riesgos

- **Deriva por invalidación incompleta**: si un `stale` no se propaga, el kardex
  muestra saldos desfasados. Mitigación: test de propagación + un cron de
  *auditoría* que revalida N períodos al azar contra la vista.
- **Complejidad operativa**: dos rutas de cálculo. Mitigar con el flag por
  compañía y tests que corran ambas rutas sobre el mismo dataset.
- **Multi-moneda / revaluaciones**: el snapshot guarda valor en moneda compañía;
  las revaluaciones manuales (`product.value`) deben marcar `stale` igual que los
  movimientos.

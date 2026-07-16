# Análisis de rendimiento y arquitectura — ol_stock_kardex_pe

**Contexto:** empresa con **miles de movimientos de inventario en el lapso de
un año**. ¿Cómo generar el Kardex SUNAT sin degradar la interfaz, automatizarlo
y evitar poblar un modelo intermedio?

## 1. Problema del diseño inicial (v1)

La primera versión usaba `l10n_pe.kardex.line` como **`TransientModel`** y un
método `_generate_lines()` que, en cada corrida, creaba **una fila transient
por movimiento** (`create(vals_list)`), más filas sintéticas de saldo inicial y
totales.

Costos de ese enfoque con volumen alto:

| Problema | Impacto con ~50k movimientos/año |
|---|---|
| `INSERT` masivo en cada visualización | Miles de escrituras + índices por corrida |
| Recorrido Python del saldo corrido | O(n) en el worker, con GIL |
| Resolución de documento por movimiento | Riesgo de N+1 queries |
| Tabla transient que crece | Presión sobre el autovacuum de Odoo |
| Bloquea la petición HTTP | El usuario espera con la UI congelada |

## 2. Solución adoptada (v2): vista SQL + window functions

`l10n_pe.kardex.line` pasa a ser un **modelo respaldado por una vista SQL**
(`_auto = False`, `init()` crea la `VIEW`). Es el patrón canónico de Odoo para
reportes (como `sale.report`, `stock.report`). **No se puebla nada**: los datos
se derivan en vivo de `stock.move`.

El **saldo corrido** —la parte difícil— se calcula con *window functions* de
PostgreSQL, en dos particiones simultáneas:

```sql
SUM(signed_qty) OVER (
    PARTITION BY product_id, company_id          -- consolidado (contable)
    ORDER BY date, id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance_qty
SUM(signed_qty) OVER (
    PARTITION BY product_id, warehouse_id, company_id  -- por almacén
    ...) AS balance_qty_wh
```

Como `stock_move.value`, `is_in`, `is_out`, `product_qty` y `warehouse_id` son
**columnas reales** (almacenadas), la vista las lee directamente sin computar
nada en Python.

### Por qué es rápido

- La agregación corre en C dentro de PostgreSQL, no en el worker Python.
- Con un índice `stock_move(product_id, date)` el *sort* de la window es barato.
- Filtrar por período empuja el `WHERE` a la vista; el saldo corrido sigue
  siendo correcto porque la window recorre la partición completa del producto
  (que es lo que se quiere: saldo acumulado).
- **Cero `INSERT`s**: ver el kardex es un `SELECT`.

### Saldo inicial sin recorrer la historia

El saldo antes de `date_from` se obtiene con **una sola consulta**:

```sql
SELECT DISTINCT ON (product_id) product_id, balance_qty, balance_value
FROM l10n_pe_kardex_line
WHERE company_id = %s AND date < %s [filtros]
ORDER BY product_id, date DESC, id DESC;
```

Devuelve, por producto, el último saldo acumulado previo al período — sin traer
todos los movimientos anteriores al worker.

### Campos que siguen en Python (por lote)

El documento SUNAT (Tabla 10, serie, folio) exige *joins* a `account_move` vía
`sale_line_id`/`purchase_line_id` y un *parsing* con regex del número; el tipo
de operación (Tabla 12) depende de `l10n_pe_operation_type` o del *usage* de la
ubicación. Se resuelven como **campos calculados no almacenados**, evaluados por
lote (con *prefetch*) **solo para las filas que se leen** (una página en
pantalla, o el conjunto del período al exportar). No hay N+1.

### Filas sintéticas solo en memoria

Las filas de **SALDO INICIAL** y **TOTALES** (que SUNAT exige pero no son
movimientos) se construyen como objetos `SimpleNamespace` en el momento de
renderizar el XLSX/PDF. No se almacenan ni se escriben.

## 3. Automatización / segundo plano

Para corridas grandes (todo el año, todos los productos → un XLSX/PDF pesado),
el botón **"Generar en segundo plano"**:

1. Crea un registro persistente `l10n_pe.kardex.report` (estado `pending`) con
   los filtros de la corrida.
2. Despierta el cron `ir_cron_kardex_generate` con `_trigger()` (ejecución casi
   inmediata en otro worker, sin bloquear la UI).
3. El cron procesa los pendientes por lotes (`limit=20`), hace `commit`
   incremental para que el usuario vea el progreso, y re-despierta el cron si
   quedan más.
4. El archivo queda en *Kardex SUNAT · Generados* para descargar; los errores se
   guardan en el registro (estado `error` + mensaje).

Esto no depende de OCA `queue_job`: usa el `ir.cron._trigger()` nativo, portable
a cualquier instalación EE/CE.

### Automatización periódica

El mismo `ir.cron` puede activarse en modo recurrente (p. ej. mensual) para
pre-generar el kardex del período cerrado y dejarlo listo para descarga, o
integrarse con el cierre contable.

## 4. Comparativa

| Aspecto | v1 (transient poblado) | v2 (vista SQL) |
|---|---|---|
| Ver en pantalla | `INSERT` de miles de filas | `SELECT` directo |
| Saldo corrido | Python O(n) | Window function (C) |
| Saldo inicial | API `to_date` por producto | 1 × `DISTINCT ON` |
| Almacenamiento | Tabla transient creciente | Ninguno (vista) |
| Exportar grande | Bloquea la petición | Segundo plano + cron |
| Cuadratura contable | Exacta | Exacta (idéntica) |

## 5. Límites conocidos

- La window function recomputa el acumulado en cada consulta. Para volúmenes
  extremos (cientos de miles de movimientos y muchos productos a la vez) puede
  optimizarse con una **tabla materializada** por período (snapshot del cierre)
  o un índice parcial; la vista actual es el punto óptimo simplicidad/velocidad
  para el rango objetivo (miles/año). **Diseño detallado de esta evolución en
  [`MEJORA_FUTURA_SNAPSHOT.md`](MEJORA_FUTURA_SNAPSHOT.md)** (propuesta, no
  implementada): índice parcial → materialized view → snapshot de cierres, con
  poblado incremental, invalidación por `stale`/lock dates y activación por
  compañía.
- El costo por almacén sigue siendo **aproximado**: Odoo valoriza por compañía.
  El modo consolidado es el contablemente exacto y el que cuadra con el TXT PLE.

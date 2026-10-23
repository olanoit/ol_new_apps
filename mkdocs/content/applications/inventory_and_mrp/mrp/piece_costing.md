---
modulos: [al_mrp_piece_costing]
---

# Costeo de piezas por medida

En una orden de corte, cada pieza que sale (un subproducto con su propio
producto) recibe el costo que le corresponde por su **área**, el **tablero**
del que se corta y sus **metros de tapacanto**, en lugar del reparto en partes
iguales del estándar. Asientos, kárdex y reportes toman ese costo porque el
módulo trabaja sobre el reparto nativo de los subproductos.

## Configuración

1. Instale **Costeo de piezas por medida** (`al_mrp_piece_costing`).
2. En cada producto de tapacanto, marque **Es tapacanto** (pestaña **Información
   general**, grupo **Costeo por medida**). La bolsa de tapacanto se arma por
   esta marca, no por el nombre.
3. En **Inventario ‣ Configuración ‣ Tipos de operación**, abra el tipo de
   fabricación de corte y active **Costeo por medida**: sus órdenes nacen con
   la marca.
4. Las piezas deben tener costo **promedio** o **FIFO** (categoría de producto).

## Conceptos

| Concepto | Qué es |
|---|---|
| Pieza de corte | Producto con área (m²), tapacanto (m), tablero de origen y obra de origen |
| Bolsa de tapacanto | Valor consumido de los productos marcados **Es tapacanto**; se reparte por metros de tapacanto de cada pieza |
| Bolsa del tablero | Valor consumido de cada tablero; se reparte por área solo entre las piezas cortadas de él |
| Bolsa general | Lo demás: mano de obra, costo extra, insumos y tableros sin pieza; se reparte por área entre todas las salidas |
| Producto principal | Recibe el residuo: costo total menos lo asignado a las piezas |
| Retazo | Sobrante recuperable declarado en el corte: sale a su costo fijo (área × costo de la plancha ÷ área de la plancha), que se descuenta de la bolsa de su tablero, y no entra al reparto ([planchas enteras y retazos](../../services/project/construction/planning/production_order.md#tableros-en-planchas-enteras)) |

## Importar el despiece

1. Vaya a **Fabricación ‣ Operaciones ‣ Importar despiece**.
2. Suba el XLSX (una fila por pieza) y elija la **Categoría de las piezas**.
3. Haga clic en **Importar**. Se crea o actualiza un producto por pieza con
   referencia `<obra>-<id_pieza>`.

| Columna | Obligatoria | Uso |
|---|---|---|
| `obra` | Sí | Obra de origen y prefijo de la referencia |
| `id_pieza` | Sí | Identificador de la pieza en la obra |
| `material` | Sí | Código o nombre del tablero en el maestro |
| `largo_mm`, `ancho_mm` | Si falta `area_m2` | Calculan el área |
| `area_m2` | Si faltan largo y ancho | Área de una pieza; con las dos, avisa si difieren más del 2 % |
| `tapacanto_codigo`, `tapacanto_ml` | Con tapacanto | El código debe ser un producto marcado **Es tapacanto** |
| `cantidad` | No | Mínimo 1 |
| `mueble_terminado`, `modulo` | No | Referencia |

Con un solo error no se importa nada: el resumen lista las filas a corregir.

## Producir y revisar el cuadre

Al confirmar, la orden con **Costeo por medida** comprueba que no tenga
componentes de un kit, que cada pieza tenga área y que su tablero esté entre
los componentes. Al cerrarla, la pestaña **Costeo por medida** muestra el
**Costo total de la orden**, la **Suma de las piezas**, la **Diferencia de
cuadre** (en rojo si pasa de una unidad de moneda) y los ajustes manuales de
valor que haya, con el costo de cada pieza.

## Ejemplo

Consumo: tablero blanco S/ 100, tablero roble S/ 200 y 3 m de tapacanto a
S/ 1, más S/ 10 de costo extra: S/ 313.

| Salida | Tablero | Área (m²) | Tapacanto (m) | Costo |
|---|---|---:|---:|---:|
| Lateral | Blanco | 0.50 | 2 | 72.37 |
| Repisa | Blanco | 0.25 | 0 | 35.19 |
| Puerta | Roble | 0.50 | 1 | 204.70 |
| Principal | — | 0.10 | 0 | 0.74 |

El lateral recibe dos tercios del tablero blanco (66.67), dos tercios del
tapacanto (2.00) y su parte de la bolsa general de S/ 10 por área (3.70).

## Casos especiales

| Situación | Qué pasa |
|---|---|
| Entrega parcial | No se admite: cierre la orden con lo producido y lleve lo no cortado a una orden nueva |
| Desarme | Bloqueado: el desarme no reconstruye el costo por pieza; corrija con un ajuste y su asiento |
| Orden subcontratada | Se costea como el estándar |
| Sin costo o sin área | Sigue el cálculo nativo |

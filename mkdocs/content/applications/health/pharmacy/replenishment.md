---
modulos: [al_pharmacy_replenishment]
---

# Faltantes y sugerido de compra

El quiebre de stock es la principal pérdida de una botica: el cliente pide un
producto que no hay, se va y nadie se entera. Las cadenas reponen por consumo
desde su centro de distribución. Con este módulo la botica registra lo que se
pide y no hay, y compra según lo que vende.

## Registrar un faltante en la caja

1. En la caja, abra **Acciones** y pulse **Faltante**.
2. Si hay una línea seleccionada, el producto ya viene puesto. Si el producto
   no existe en el catálogo, escriba la **descripción** («colirio X»).
3. Indique la **cantidad** y el **motivo**: sin stock, no lo trabajamos, precio
   u otro.

El faltante queda con el local, la sesión y el cajero. Se revisan en
**Farmacia ‣ Reposición ‣ Faltantes** y **Análisis de faltantes** (por
producto, local y motivo).

## Sugerido de compra

**Farmacia ‣ Reposición ‣ Sugerido de compra**:

1. Elija el **local**, el **periodo de análisis** (días de venta que se
   promedian) y los **días de cobertura** (para cuántos días se compra).
2. Pulse **Calcular**. Por cada producto farmacéutico:

    | Columna | Qué es |
    |---|---|
    | Venta diaria | Ventas del TPV del local y entregas de pedidos de venta, menos devoluciones, entre los días del periodo |
    | Faltantes | Cantidad de faltantes pendientes del producto |
    | Stock | Existencia del local |
    | Por llegar | Compras y traslados confirmados |
    | Sugerido | Venta diaria × cobertura + faltantes − stock − por llegar, redondeado a la unidad de compra |

3. Corrija el proveedor o la cantidad si hace falta.
4. Pulse **Crear solicitudes de presupuesto** (una por proveedor) o, si hay
   almacén central, **Crear traslado**. Los faltantes de esos productos pasan
   a **Pedido**.

!!! note "Nota"
    El stock incluye los lotes en cuarentena. Los faltantes escritos como texto
    libre no entran en el sugerido porque no tienen producto: revíselos en el
    análisis para decidir si se incorporan al catálogo.

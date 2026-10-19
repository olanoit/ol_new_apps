# Farmacia: faltantes y sugerido de compra (`al_pharmacy_replenishment`)

Entrega E6 de las mejoras de la suite de farmacia
([`docs/farmacia/MEJORAS_PROCESOS.md`](../../docs/farmacia/MEJORAS_PROCESOS.md)).

## Faltantes

Lo que un cliente pide en la caja y no se le puede vender. Sin registro, la
venta se pierde sin rastro y la compra no se entera.

- **En la caja**: botón «Faltante» (en «Acciones»). Propone el producto de la
  línea seleccionada; si el cliente pidió algo que la botica no trabaja, se
  escribe lo que pidió. Cantidad y motivo: sin stock, no lo trabajamos,
  precio u otro.
- Se guarda con el local (el almacén de la caja), la sesión y el cajero.
- **Farmacia ▸ Reposición ▸ Faltantes** y **Análisis de faltantes** (tabla
  dinámica y gráfico por producto, local y motivo).
- Estados: pendiente → pedido (por el sugerido) → atendido, o descartado.

## Sugerido de compra

**Farmacia ▸ Reposición ▸ Sugerido de compra** (compradores).

```
sugerido = venta diaria × días de cobertura + faltantes − stock − por llegar
```

| Término | Origen |
|---|---|
| Venta diaria | Ventas del TPV del local (pagadas, neto de devoluciones) más las entregas a clientes que no salen del TPV (pedidos de venta) menos sus devoluciones, entre los días del periodo |
| Faltantes | Faltantes pendientes del local con producto |
| Stock | Existencias del local (`qty_available` por almacén) |
| Por llegar | Compras confirmadas y traslados hacia el local (`incoming_qty`) |

El resultado se redondea hacia arriba al **múltiplo de compra**: la unidad del
proveedor principal (por ejemplo, «Caja x 10») o, si se compra por unidad, la
presentación de venta más grande. Las líneas son editables (proveedor y
cantidad).

- **Crear solicitudes de presupuesto**: una por proveedor principal, en la
  unidad del proveedor, con la recepción del local.
- **Crear traslado**: desde el almacén central elegido hasta el local,
  confirmado.
- Los faltantes pendientes de esos productos pasan a «pedido» con la
  solicitud o el traslado.

## Límites

- El stock es el disponible en el local, incluidos los lotes en cuarentena
  (la cuarentena se resuelve en la recepción, no en la compra).
- Los faltantes de texto libre no entran al sugerido: no tienen producto.
- No reemplaza las reglas de mínimos y máximos de Odoo: es un cálculo a
  pedido para quien compra.

## Pruebas

`tests/`: cálculo del sugerido (venta del TPV, entregas de pedidos de venta,
stock, entrante y faltantes), solicitudes por proveedor en su unidad,
traslado desde el almacén central y tour del botón «Faltante» en la caja.

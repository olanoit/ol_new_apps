---
modulos: [al_l10n_pe_stock_consumption]
---

# Asiento de consumo a costo

Cuando un material sale del almacén para usarse dentro de la empresa, su valor
pasa de existencias al gasto. Este módulo contabiliza esa salida al costo del
movimiento, en la cuenta de la familia del producto y con su centro de costo. Lo
usan el almacén, que registra la salida, y el área de costos.

Odoo ya genera un asiento para la salida a una ubicación virtual con cuenta,
pero con una sola cuenta por ubicación y sin analítica.

## Configuración

1. En **Inventario ‣ Configuración ‣ Ubicaciones**, cree una ubicación de tipo
   **Ajuste de inventario** con su cuenta de valorización.
2. Marque **Ubicación de consumo**. Puede dejarle un **Centro de costo** por
   defecto.
3. En cada categoría de producto, indique la **Cuenta de consumo** si difiere
   de la cuenta de la ubicación.
4. Para el destino 9/79, configure los
   [asientos de destino](../../finance/fiscal_localizations/peru/destination_entries.md).

## Uso

Haga una transferencia hacia la ubicación de consumo. En cada línea puede
indicar el **Centro de costo**; si lo deja vacío, se usa el de la ubicación. Para
devolver material, haga la transferencia inversa: se revierte el cargo.

Revise lo consumido en **Inventario ‣ Informes ‣ Consumos a costo**.

Salen 4 unidades de un material con costo promedio de S/ 5 hacia el centro
**Planta**:

| Cuenta | Analítica | Debe | Haber |
|---|---|---:|---:|
| 6131 Materiales auxiliares | Planta 100 % | 20,00 | |
| 2511 Materiales auxiliares | | | 20,00 |
| | **Totales** | **20,00** | **20,00** |

## Cuándo se contabiliza

- **Valorización permanente:** un asiento al validar cada movimiento.
- **Valorización periódica:** una línea por cuenta y centro de costo en el
  cierre de valorización de Odoo.

## Tenga en cuenta

- Las mermas y los ajustes de inventario no cambian mientras su ubicación no
  esté marcada.
- Si la transferencia ya tiene proyecto con costos analíticos u obra, el apunte
  analítico lo crea el movimiento. El asiento no repite el centro de costo, y su
  destino sigue el reparto de la cuenta.
- La fabricación no usa este módulo: consulte el costeo de órdenes de fabricación.

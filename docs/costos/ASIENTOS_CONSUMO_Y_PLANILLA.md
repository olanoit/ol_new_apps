# Asiento de consumo a costo y asiento de planilla por centro de costo

Noviembre de 2026. Alcance: Odoo 19, localización peruana.

## 1. Asiento de consumo a costo

Módulo nuevo: `OL-INVENTORY/al_l10n_pe_stock_consumption`.

### Qué ya daba Odoo

| Necesidad | Odoo 19 | Falta |
|---|---|---|
| Salida valorizada al costo | `stock.move.value` | Nada |
| Asiento de salida a ubicación virtual | `stock_account`: `location.valuation_account_id` | Una sola cuenta por ubicación y sin analítica |
| Valorización periódica | Cierre con `_get_location_valuation_vals` | Agrupa por ubicación y categoría, sin analítica |

### Dinámica contable

    61x  Variación de existencias, con centro de costo
        a 2x  Existencias

    9x   Cuenta del centro de costo        (al_account_destinations)
        a 791 Cargas imputables

Las cuentas se configuran; el código no contiene ninguna.

### Reglas

- La marca «Ubicación de consumo» activa el comportamiento. Mermas y ajustes
  de inventario sin la marca siguen como en Odoo.
- Cuenta: la de la categoría; si no tiene, la de la ubicación.
- Centro: el de la línea; si no tiene, el de la ubicación.
- Permanente: un asiento por movimiento, por `_get_account_move_line_vals`.
- Periódica: el cierre retira estas ubicaciones del cálculo nativo y añade
  líneas por cuenta, existencia y centro.

### Límites conocidos

- Un movimiento que ya tiene distribución propia (proyecto con costos
  analíticos, obra) crea su apunte desde el movimiento. El asiento va sin
  analítica para no cargar dos veces, y su destino usa el reparto de la cuenta.
- Solo aplica a ubicaciones de tipo inventario: la fabricación sigue con
  `mrp_account` y `al_l10n_pe_mrp_cost`.
- En valorización permanente continental, el cierre de Odoo trata toda
  variación de la cuenta 20 como 6111/69121, también el consumo. El resultado
  total no cambia, pero sí el reparto entre esas dos cuentas. Falta verificarlo
  con el contador.

## 2. Asiento de planilla por centro de costo

Módulo existente: `OL-PAYROLL/al_hr_pe_account`. No se crea otro: ya tenía el
asiento por lote, la prioridad regla > tareaje > ficha y las cuentas por centro.

### Qué se cambió

| Hueco | Cambio |
|---|---|
| Los abonos a cuentas por pagar llevaban analítica y anulaban el gasto del centro | Solo las cuentas de resultados llevan centro |
| Una línea con varios porcentajes | Opción «Una línea de gasto por centro de costo» |
| Gasto sin centro de costo sin ningún aviso | Aviso en el asistente y opción «Exigir centro de costo» |
| La provisión mensual usaba solo la ficha | Tareaje del periodo y, si no hay, la ficha |
| Claves de varios planes que suman más de 100 % partían mal el importe | Si no suman 100 %, no se parte |

### Fuera de alcance

- El asiento nativo por boleta (diario en la estructura) sigue sin tareaje: el
  flujo peruano es el asiento por lote.
- CTS, gratificación y liquidación usan la ficha: se devengan en varios meses.
- El informe por centro es el analítico nativo de Contabilidad.

## 3. Corrección común en destinos

`al_account_destinations` creaba un apunte analítico en el origen y otro en la
línea 9x, así que el centro de costo se cargaba dos veces. Ahora el asiento de
destino conserva la distribución, pero no crea apunte. La migración
`14.20261103` borra los apuntes duplicados ya existentes: los informes analíticos
de periodos pasados bajan a su valor correcto. Los asientos no cambian.

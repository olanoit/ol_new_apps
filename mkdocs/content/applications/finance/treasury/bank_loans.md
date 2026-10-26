---
modulos: [al_l10n_pe_bank_loan]
---

# Préstamos y pagarés bancarios

El módulo **Préstamos y pagarés bancarios** (`al_l10n_pe_bank_loan`) lleva cada
préstamo o pagaré con su cronograma y su contabilidad: desembolso, intereses del
mes, pago de cuotas, prepagos y saldo de capital. Es parte de la aplicación
[Tesorería](../treasury.md).

## Configuración

*Perú ‣ Configuración ‣ Cuentas de la localización ‣ Préstamos bancarios*. Las
compañías peruanas reciben las cuentas del PCGE:

| Tipo | Capital | Intereses por pagar | Gasto por intereses |
|---|---|---|---|
| Préstamo bancario | 4511 | 45511 | 67311 |
| Pagaré | 4544 | 45544 | 6733 |
| Otra obligación | 4549 | 45549 | 6733 |

El seguro de desgravamen va a 651 y las comisiones y gastos de desembolso a
6391. Agregue una fila por moneda si usa cuentas distintas en dólares.

## Registrar un préstamo

*Tesorería ‣ Financiamiento ‣ Préstamos y pagarés*.

1. Banco, banco de la empresa, capital, moneda y, si corresponde, la
   [línea de crédito](../treasury.md#lineas-de-credito).
2. Condiciones: **TEA**, base de 360 o 365 días, amortización (francés,
   alemán o al vencimiento), frecuencia, número de cuotas, **periodo de
   gracia** (parcial: solo intereses; total: los intereses se capitalizan),
   desembolso y primer vencimiento, **desgravamen** (% mensual sobre el saldo),
   comisión por cuota y gastos de desembolso.
3. **Calcular cronograma**. El interés de cada cuota usa los días reales del
   periodo: `saldo × ((1 + TEA)^(días / base) − 1)`; en el francés la cuota queda
   fija aunque los meses tengan distinta duración. Si el banco entregó un
   cronograma con otros céntimos, corrija las líneas antes de desembolsar. La
   **TCEA** incluye intereses, seguro, comisiones y gastos de desembolso.
4. **Desembolsar**.

## Asientos

| Paso | Debe | Haber |
|---|---|---|
| Desembolso | Banco (cobros pendientes) · 6391 gastos | 4511 capital |
| Devengo de cada mes | 67311 | 45511 |
| Pago de la cuota | 4511 capital · 45511 devengado · 67311 diferencia · 651 · 6391 | Banco (pagos pendientes) |
| Cuota de gracia total | 45511 · 67311 | 4511 (intereses capitalizados) |
| Prepago | 4511 · 45511 / 67311 intereses corridos | Banco (pagos pendientes) |

Los movimientos de banco van a la cuenta de pendientes del diario, como un pago
de Odoo, para conciliarlos con el extracto. Con *Afecto al ITF* se registra
además el ITF de cada movimiento.

- El **devengo** lo hace un proceso diario al cierre del mes anterior, sin
  duplicar; *Devengar intereses* lo hace a la fecha.
- **Pagar cuota** paga la siguiente pendiente con el interés, el seguro y la
  comisión que cobró el banco; la diferencia de interés va al gasto.
- **Prepagar** paga capital más los intereses corridos de la cuota en curso y
  rehace las cuotas pendientes desde esa fecha: *reducir la cuota* (mismas
  cuotas) o *reducir el plazo* (misma cuota).

## Saldos e informes

- **Saldo de capital**, **porción corriente** (capital que vence en los próximos
  12 meses) y **no corriente**, para los estados financieros.
- *Calendario de cuotas*: lo que vence por banco y mes, en lista y tabla
  dinámica.
- Las cuotas pendientes entran al [flujo de caja proyectado](../accounting/cash_forecast.md)
  y el responsable recibe un aviso antes de cada vencimiento.
- En dólares, la diferencia de cambio la calcula la
  [diferencia de cambio](../fiscal_localizations/peru/exchange_differences.md)
  de la suite sobre las cuentas marcadas; el formulario avisa si no lo están.

---
modulos: [al_l10n_pe_financial_reports]
---

# Estados financieros

**Perú ‣ Informes ‣ Estados financieros** reúne los estados financieros peruanos como
informes contables de Odoo: el **Estado de Cambios en el Patrimonio Neto
(formato 3.19)**, calculado desde los asientos con las cuentas del PCGE, y los
accesos al **Balance** y al **Estado de resultados** de Odoo Enterprise en su
variante peruana. Lo usa el contador al cierre del ejercicio o de un periodo
intermedio. El 3.19 sale en pantalla, en PDF y en XLSX, y cuadra con el
patrimonio del Balance a la misma fecha.

No incluye el Estado de Flujos de Efectivo ni la versión por columnas del
3.19. El TXT 3.19 para el PLE lo genera
[Libros electrónicos (PLE)](ple.md#libro-3-inversiones-intangibles-y-patrimonio).

## Conceptos

- La **NIC 1** exige el estado de cambios en el patrimonio entre los estados
  financieros completos.
- El **PCGE** define las cuentas de patrimonio: 50 capital, 51 acciones de
  inversión, 52 capital adicional, 56 y 57 resultados no realizados y
  excedente de revaluación, 58 reservas y 59 resultados acumulados. Está
  vigente el PCGE 2019; el PCGE 2026, aprobado en setiembre de 2026, es
  obligatorio desde el 1/1/2028 y, si el plan cambia, habrá que revisar las
  cuentas de cada línea.
- El **formato 3.19** pertenece al Libro de Inventarios y Balances
  (R.S. 286-2009/SUNAT).

| Término | Significado | Dónde aparece en Odoo |
|---|---|---|
| Saldo inicial | Patrimonio al día anterior al periodo, más la apertura | Primera línea del informe |
| Saldo reexpresado | Saldo inicial + cambios de política + corrección de errores | Línea editable |
| Movimiento | Variación del periodo por rubro | Columna **Movimiento** |
| Diario de apertura o cierre | Naturaleza del diario | **Perú ‣ Configuración ‣ Contabilidad ‣ Diarios** |
| Línea editable | Importe que no sale de asientos (aportes, distribuciones) | Lápiz de la línea |

## Configuración

1. Use el plan contable peruano (PCGE) con las cuentas 50 a 59 para el
   patrimonio. Las cuentas de patrimonio fuera de ese rango salen en «Otras
   variaciones del patrimonio».
2. Marque la **Naturaleza del diario** en **Perú ‣ Configuración ‣
   Contabilidad ‣ Diarios** ([Configuración contable básica](accounting_base.md)):
   **Apertura** para la carga de saldos al empezar a usar Odoo y **Cierre**
   para los asientos de cierre del ejercicio, que el informe excluye de los
   movimientos.

!!! warning "Importante"
    Si al 31/12 se cierra y se reabre todo el balance, ambos asientos van en
    diarios de **Cierre**: el diario de **Apertura** queda solo para la carga
    inicial. Un asiento de cierre en un diario de movimiento duplica el
    resultado.

## Estado de cambios en el patrimonio neto

1. Vaya a **Perú ‣ Informes ‣ Estados financieros ‣ 3.19 Estado de Cambios en el
   Patrimonio Neto** y elija el periodo.
2. Revise el saldo inicial, los movimientos por rubro y el saldo final. El
   resultado del ejercicio sale de las cuentas de resultados del periodo, no de
   la cuenta 59: aparece aunque el ejercicio no esté cerrado.
3. Si hay ajustes sin asiento (cambios de política, corrección de errores,
   aportes), haga clic en el lápiz de la línea y escriba el importe con su
   nota.
4. Compare el saldo final con el patrimonio del **Balance** (**Perú ‣ Informes ‣
   Estados financieros ‣ Balance**) a la misma fecha.
5. Exporte con los botones **PDF** o **XLSX**.

![Estado de cambios en el patrimonio neto](financial_statements/equity-statement.png)

![Líneas editables con importe y nota](financial_statements/editable-lines.png)

### Ejemplo

Saldos al 1/1/2026: capital 50 000 (5011), reserva legal 5 000 (5821) y
resultados acumulados 20 000 (5911), es decir, un **patrimonio inicial de
75 000**. Movimientos del ejercicio:

| Hecho | Cuenta | Debe | Haber |
|---|---|---|---|
| Aumento de capital en efectivo | 1041 Banco | 10 000,00 | |
| | 5011 Capital social | | 10 000,00 |
| Dividendos declarados | 5911 Utilidades acumuladas | 8 000,00 | |
| | 4411 Dividendos por pagar | | 8 000,00 |
| Constitución de reserva legal | 5911 Utilidades acumuladas | 1 200,00 | |
| | 5821 Reserva legal | | 1 200,00 |
| **Totales** | | **19 200,00** | **19 200,00** |

Además, las cuentas de resultados dejan una ganancia de **12 000**. El estado
(columna **Movimiento**) queda así:

| Línea | Importe |
|---|---|
| Saldos al inicio del periodo | 75 000,00 |
| Ganancia (pérdida) neta del ejercicio | 12 000,00 |
| Emisión (reducción) de capital | 10 000,00 |
| Constitución (aplicación) de reservas | 1 200,00 |
| Dividendos y otras variaciones de resultados acumulados | −9 200,00 |
| **Saldos al final del periodo** | **89 000,00** |

75 000 + 12 000 + 10 000 + 1 200 − 9 200 = 89 000, igual al patrimonio del
Balance: capital 60 000 + reserva 6 200 + resultados acumulados 10 800 +
resultado del ejercicio 12 000. La línea de la cuenta 59 suma el dividendo
(−8 000) y el traslado a la reserva (−1 200).

## Reportes

- **Balance** y **Estado de resultados** (Enterprise), en el mismo menú.
- **TXT 3.19** del Libro de Inventarios y Balances, con la captura por rubro de
  la tabla 34, y el resto del Libro 3 (3.8, 3.9, 3.23): ver
  [Libros electrónicos (PLE)](ple.md).
- La [diferencia de cambio](exchange_differences.md) de cierre y los
  [asientos de destino](destination_entries.md) entran en estos estados.

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| El saldo final no cuadra con el Balance | Hay ajustes editables o asientos de cierre en un diario sin naturaleza **Cierre** | Revise las líneas editables y la naturaleza de los diarios |
| El resultado sale duplicado | El asiento de cierre está en un diario de movimiento | Pase el asiento a un diario de naturaleza **Cierre** |

!!! info "Ver también"
    - [NIC 1 — Presentación de estados financieros](https://www.ifrs.org/issued-standards/list-of-standards/ias-1-presentation-of-financial-statements/)
    - [Resolución 002-2019-EF/30 — PCGE 2019 (MEF)](https://mef.gob.pe/contenidos/conta_publ/documentac/Resolucion_CNC002_2019EF30.pdf)
    - [Resolución 002-2026-EF/30 — PCGE 2026 (El Peruano)](https://busquedas.elperuano.pe/dispositivo/NL/2550786-1)
    - [R.S. 286-2009/SUNAT — Libros electrónicos](https://www.sunat.gob.pe/legislacion/superin/2009/rs286.doc)
    - [Odoo: informes contables](https://www.odoo.com/documentation/19.0/es_419/applications/finance/accounting/reporting.html)

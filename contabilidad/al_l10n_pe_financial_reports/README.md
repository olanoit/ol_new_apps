# PE - Reportes financieros (AL)

Módulo que reúne los **estados financieros peruanos** de la suite, definidos
como informes contables de Odoo (`account.report`). Cada informe nuevo va aquí.

| Informe | Dónde |
|---|---|
| 3.19 Estado de Cambios en el Patrimonio Neto | Perú ▸ Estados financieros · Contabilidad ▸ Informes |
| Balance y Estado de resultados (Enterprise, variante peruana) | Perú ▸ Estados financieros |

## 3.19 Estado de Cambios en el Patrimonio Neto

Migrado de `al_l10n_pe_reports` (Odoo 18, `data/financial_report_equity_changes.xml`).
La versión por columnas (`_v2`) estaba desactivada en v18 y no se migró.

Columnas: **Nota**, **Saldo inicial**, **Movimiento** y **Saldo final**.

| Línea | Cálculo |
|---|---|
| Saldos al inicio del periodo | Patrimonio y resultados no distribuidos hasta el día anterior (sin asientos de cierre) + asientos de diarios **Apertura** del periodo |
| Cambios en políticas contables · Corrección de errores | Editables, con nota |
| Saldo inicial reexpresado | Saldo inicial + las dos líneas editables |
| Ganancia (pérdida) neta del ejercicio | Cuentas de resultados del periodo |
| Otro resultado integral | Cuentas 56 y 57 |
| Emisión (reducción) de capital | Cuentas 50 y 52 |
| Emisión (reducción) de acciones de inversión | Cuenta 51 |
| Constitución (aplicación) de reservas | Cuenta 58 |
| Dividendos y otras variaciones de resultados acumulados | Cuenta 59 |
| Aportaciones, distribuciones, subsidiarias | Editables |
| Otras variaciones del patrimonio | Cualquier otra cuenta de patrimonio (p. ej. 8x fuera del cierre) |
| Saldos al final del periodo | Saldo reexpresado + total de cambios |

Los movimientos excluyen los asientos de diarios con naturaleza **Cierre** y
**Apertura** (`l10n_pe_journal_kind` de `al_account_base`). Todo en positivo
(`-sum`), como el Balance.

### Correcciones frente al v18

1. **Signo**: el v18 sumaba las cuentas 5x tal cual y el patrimonio salía en negativo.
2. **Cuentas del PCGE**: el v18 usaba 53 (acciones propias), 54-55 (otro
   resultado integral), que no existen en el PCGE vigente, y la 57 como
   dividendos, cuando es el excedente de revaluación.
3. **Resultado del ejercicio**: el v18 lo tomaba del movimiento de la 59 y
   salía en cero hasta el asiento de cierre; ahora sale de las cuentas de
   resultados y el cierre (diario de naturaleza Cierre) no lo duplica.
4. **Cuadre**: sin ajustes editables, el saldo final es el patrimonio del
   Balance a la misma fecha (lo comprueba `test_closing_matches_the_balance_sheet`).

### Limitación

Una empresa que cierra **todo** el balance al 31/12 y lo reabre el 1/1 debe
registrar ambos asientos en diarios de naturaleza Cierre; el diario de
**Apertura** queda para la carga de saldos al empezar a usar Odoo.

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 --test-tags /al_l10n_pe_financial_reports \
    --stop-after-init --http-port 19797
```

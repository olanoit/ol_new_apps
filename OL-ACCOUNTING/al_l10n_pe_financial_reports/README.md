# PE - Reportes financieros (AL)

Documentación funcional: [Estados financieros](../../mkdocs/content/applications/finance/fiscal_localizations/peru/financial_statements.md)

Módulo que reúne los **estados financieros peruanos** de la suite, definidos
como informes contables de Odoo (`account.report`). Cada informe nuevo va aquí.

| Informe | Dónde |
|---|---|
| 3.19 Estado de Cambios en el Patrimonio Neto | Perú ▸ Informes ▸ Estados financieros · Contabilidad ▸ Informes |
| Balance y Estado de resultados (Enterprise, variante peruana), por centro de costo y sin asientos de cierre | Perú ▸ Informes ▸ Estados financieros |
| Hoja de trabajo (formatos 1 y 2) | Perú ▸ Informes ▸ Estados financieros |
| Cierre del ejercicio (asistente) | Perú ▸ Contabilidad ▸ Cierre del mes |

## Hoja de trabajo

`account.pe.worksheet.report.handler` (`models/account_worksheet_report.py`)
arma las líneas con una consulta agrupada por cuenta sobre
`_get_report_query` (respeta compañías, diarios, filtro analítico y borradores).
Cada informe (`data/report_worksheet.xml`) declara solo sus columnas. Las cuentas
de resultados restan lo anterior al ejercicio, que va a la línea «Resultados de
ejercicios anteriores». Naturaleza: prefijos 60-68, 70-78 y 88; función: el
ajuste de compañía `l10n_pe_ws_function_prefixes` (delegado a la raíz).

## Cierre del ejercicio

`l10n_pe.year.closing.wizard` (`wizard/`) aplica las reglas
`l10n_pe.closing.rule` (`data/l10n_pe_closing_rule_data.xml`, `noupdate`) sobre los
saldos del ejercicio sin diarios de cierre, un asiento en borrador por regla.
Opcionalmente cierra el balance y lo reabre (ambos en el diario de cierre).
`account.move.l10n_pe_closing_date` marca lo generado: solo eso se borra al
rehacer. «Publicar» concilia reapertura y cierre por cuenta, socio y moneda.

## Informes sin asientos de cierre

`account.report.l10n_pe_exclude_closing` añade una condición al `forced_domain`
de las opciones: `journal` excluye los diarios de naturaleza cierre (Estado de
resultados y hoja de trabajo); `balance` solo los asientos generados de cierre y
reapertura del balance (`l10n_pe_closing_step`), así el Balance ve la 59. El
cierre corre en la compañía raíz con `allowed_company_ids` de todas sus
sucursales (la regla de apuntes solo deja ver las activas). Activo en la hoja de
trabajo y en el Balance y el Estado de resultados de `l10n_pe_reports`
(`data/report_variants.xml`). En Odoo 20 el filtro analítico ya no es una
opción de cada reporte (`filter_analytic` se eliminó).

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

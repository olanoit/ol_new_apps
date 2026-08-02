# PE - Cierre de tipo de cambio (AL)

Ajuste mensual por diferencia de cambio de las partidas monetarias en moneda
extranjera, para la localización peruana en Odoo 19 CE.

Migración y refactorización de `al_exchange_rate_closure` (Odoo 18).

## Marco normativo

| Norma | Qué exige |
|---|---|
| **Art. 61 LIR** | La diferencia de cambio de partidas monetarias es **resultado computable** del ejercicio (renta de tercera categoría). No es una provisión reversible. |
| **Art. 34.d Reglamento LIR** | Las partidas que originan **activos** se ajustan al **T.C. promedio ponderado compra** y las que originan **pasivos** al **T.C. promedio ponderado venta** publicados a la **fecha del balance**. |
| **NIC 21** | Las partidas monetarias en moneda extranjera se convierten al tipo de cambio de cierre; las no monetarias medidas al costo se mantienen al tipo de cambio histórico. |

De ahí las tres reglas del módulo: solo cuentas de balance, T.C. distinto
según activo/pasivo, y asiento **definitivo** (no se revierte al día
siguiente, a diferencia de la revaluación multimoneda nativa de Odoo
Enterprise, que trabaja como provisión).

## La fórmula

Para cada grupo (cuenta, o cuenta + socio si se lleva con detalle):

```
ajuste = saldo_ME_acumulado × T.C._cierre − saldo_MN_contabilizado
```

Ambos saldos suman **todos** los apuntes publicados en esa moneda hasta la
fecha de cierre. El acumulado ya contiene:

* los ajustes de los cierres de meses anteriores, y
* las diferencias de cambio **realizadas** que Odoo genera al conciliar un
  cobro o pago con su factura,

y ambos llevan `amount_currency = 0` (mueven soles, no dólares). Por eso el
cálculo es **auto-corrector**: la diferencia que arroja es exactamente la
variación no reconocida desde el último cierre. No hace falta histórico
paralelo de saldos ni recalcular los meses anteriores.

### Ejemplo (comprobado en `tools/exchange_closure_demo.py`)

Factura de venta de US$ 10 000 el 15/06 al T.C. 3.389 → S/ 33 890.

| Cierre | Saldo US$ | T.C. | Saldo S/ | Revaluado | Ajuste |
|---|---|---|---|---|---|
| Junio (compra 3.410) | 10 000 | 3.410 | 33 890 | 34 100 | **+210,00** |
| Cobro de US$ 4 000 el 15/07 al 3.397 | | | −13 588 | | |
| Julio (compra 3.395) | 6 000 | 3.395 | 20 512 | 20 370 | **−142,00** |

En julio el saldo de partida (20 512) ya incluye los 210 de junio: se ajusta
solo el delta, nunca se duplica.

## Uso

1. **Configuración** → *Perú → Configuración → Ajustes*: diario del cierre
   (se recomienda uno dedicado, p. ej. `CTC`). Las cuentas de resultado son
   las nativas de diferencia de cambio de la compañía (676 / 776), las mismas
   que usa Odoo para la diferencia realizada.
2. **Plan contable** → en cada cuenta de balance en moneda extranjera,
   pestaña *Contabilidad*, sección *Cierre de tipo de cambio (PE)*:
   * *Sin detalle*: un apunte de ajuste por cuenta (caja, bancos, préstamos).
   * *Con detalle*: un apunte por socio (cuentas por cobrar y por pagar), para
     poder conciliar el ajuste con el documento.
   * *T.C. a aplicar*: automático (activo → compra, pasivo → venta) o forzado.
3. **Perú → Cierre de tipo de cambio** → nuevo → mes y año → **Traer T.C.**
   → **Calcular** → revisar el detalle y la vista previa → **Contabilizar**.

El botón *Traer T.C.* busca el tipo de cambio de la fecha de balance en
`res.currency.rate`; si no existe intenta descargarlo con
`al_l10n_pe_currency` y, en última instancia, toma el último publicado
dejando constancia en el chatter. El selector *T.C. del día* permite usar el
penúltimo día del mes, por la regla de publicación diferida de SUNAT.

## Distribución analítica

La diferencia de cambio de una factura pertenece al mismo centro de costo que
la factura. El campo *Analítica* del cierre decide de dónde sale:

| Modo | Qué hace |
|---|---|
| **Heredada** (por defecto) | Cada renglón toma la analítica de los apuntes que forman su saldo, ponderada por importe |
| **Fija** | Se aplica a todo el cierre la distribución indicada en el cierre |
| **Sin analítica** | El asiento no genera apuntes analíticos |

Sin analítica en ninguna parte, los tres modos producen el mismo asiento.

### Tres reglas que hacen que salga bien

**1. La analítica va en la línea de resultado, nunca en la de balance.**
Odoo genera el apunte analítico con `amount = -balance`. Si la línea de la
cuenta por cobrar y la de 776 llevaran la misma distribución, sus apuntes
analíticos saldrían con signos opuestos y **se anularían**: el centro de
costo recibiría cero. Por eso solo se distribuye la contrapartida.

**2. Las cuentas de balance heredan del documento.**
Una línea por cobrar o por pagar casi nunca lleva analítica: la llevan las
líneas de ingreso o gasto de su misma factura. Si el apunte no tiene
distribución propia, se toma la de sus hermanas del asiento, ponderada por
importe. Si el asiento mezcla socios, se prefieren las hermanas del mismo
socio.

**3. Los asientos de cierre no se usan como origen.**
Un asiento de cierre agrupa muchas cuentas y socios, y sus líneas de
resultado pertenecen a grupos distintos. Heredar de ellas contagiaría la
analítica de un tercero a todos los demás en el cierre siguiente. Se excluyen
explícitamente: su analítica ya se registró en el mes que le tocaba.

### Combinación ponderada

Dos ventas al mismo cliente, S/ 22 200 al centro Norte y S/ 14 800 al Sur:
el ajuste del cliente se distribuye **60 % Norte / 40 % Sur**.

El denominador es el peso de los apuntes que **sí** traen analítica, no el
total: así, si cada distribución de origen reparte el 100 % de un plan, la
combinada también, y no rompe los planes marcados como *obligatorios*
(`_validate_distribution` exige exactamente 100 %). El residuo del redondeo
se carga a la clave de mayor peso para que la suma no quede en 99,99.

### Contrapartidas

Se abre una línea de resultado por cada distribución analítica distinta: sin
analítica siguen siendo dos líneas (776 y 676); con dos centros de costo
distintos, una por cada uno. La analítica de cada renglón es **editable
mientras el cierre está calculado**, antes de contabilizar.

## Estados

| Estado | Qué permite |
|---|---|
| Borrador | Editar período, moneda y tipos de cambio |
| Calculado | Ver el detalle y la vista previa del asiento; recalcular |
| Contabilizado | Asiento creado y publicado; solo cancelar |
| Cancelado | El asiento queda cancelado; el período puede rehacerse |

## Validaciones

* Un solo cierre vivo por mes, moneda y compañía (los cancelados no cuentan).
* Los cierres deben hacerse en orden cronológico: no se puede procesar un mes
  anterior si ya hay un cierre posterior contabilizado.
* Solo cuentas de activo y pasivo pueden marcarse para el cierre.
* Se exigen diario, ambos tipos de cambio y las cuentas 676/776 antes de
  calcular.
* Un cierre contabilizado no se puede borrar ni volver a borrador sin
  cancelarlo antes.

## Qué cambió respecto de la versión 18

| v18 (`al_exchange_rate_closure`) | v19 (este módulo) | Motivo |
|---|---|---|
| `tc_close_acc_line_all`: histórico de saldos de cada mes anterior, con recálculo mes a mes y su propio `amount_apply` | Eliminado | El saldo acumulado ya lo resuelve. El recálculo duplicaba criterios de signo (las ramas activo/pasivo de `_compute_amount_apply` eran idénticas) y dependía de que existiera T.C. registrado para el fin de cada mes anterior. |
| Ventana `[date_start, date_end]` + `_find_start_date()` recorriendo los meses del año | Saldo acumulado hasta la fecha de cierre | Un apunte con fecha anterior publicado después quedaba fuera del cierre para siempre. |
| Cron `_cancel_reversion_diff_exchange` que cancelaba asientos publicados | Eliminado | Cancelar automáticamente asientos contabilizados es un riesgo contable, y su dominio mezclaba `|` con cinco condiciones (el `|` solo afectaba a las dos primeras). |
| `entry_line_ids` / `account_without_detail_ids`: Many2many **almacenados** con todos los apuntes del año | `_read_group` sobre `account.move.line` | El compute recorría y almacenaba miles de ids por cierre. |
| Búsqueda de apuntes por `account_id.code in [...]` | Por `id` de cuenta | En Odoo 19 `code` es un campo *company-dependent* calculado: filtrar por él es incorrecto en multi-compañía. |
| Diario buscado por el código literal `'CTC'` | Campo de configuración en la compañía | El campo `journal_close_diary_id` existía en v18 pero el código no lo usaba. |
| Dos booleanos `tc_with_detail` / `tc_without_detail` + `@api.constrains` | Un `Selection` | Estados imposibles eliminados por construcción. |
| Contrapartida única neteada | Ganancia y pérdida en líneas separadas | La norma peruana informa por separado la ganancia (776) y la pérdida (676). |
| `analytic_account_id` (Many2one), sin uso en el asiento | `analytic_distribution` heredada del origen, solo en las líneas de resultado | API analítica de Odoo 17+. El v18 declaraba la cuenta analítica pero nunca la pasaba al asiento. |
| `gloss`, `compra`/`venta`, `get_current_rate_pe_sbs_currency` | `l10n_pe_gloss`, `rate_purchase`/`rate_sale`, `l10n_pe_update_date_apis` | Nombres reales de las dependencias v19. |

## Pruebas

```bash
odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_exchange_closure \
    --test-enable --test-tags /al_l10n_pe_exchange_closure --stop-after-init
```

36 tests: cálculo activo/pasivo, con y sin detalle, forzado de T.C.,
acumulado entre meses, partidas saldadas, diferencia realizada absorbida,
recálculo tras cancelar, las validaciones, y la analítica (herencia del
documento, combinación ponderada, no contagio desde el cierre anterior,
apuntes analíticos que no se anulan, y reparto de contrapartidas).

Los tests crean su propia compañía: el cierre valida unicidad de período y
orden cronológico contra los cierres existentes, así que no pueden compartir
compañía con los datos reales de la base.

Comprobación con datos reales sobre la base:

```bash
odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
    < al_l10n_pe_exchange_closure/tools/exchange_closure_demo.py
```

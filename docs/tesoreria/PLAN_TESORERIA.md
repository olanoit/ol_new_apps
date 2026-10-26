# Plan: aplicación Tesorería (AL)

Fecha: 26/10/2026. Origen: [ANALISIS_TESORERIA.md](ANALISIS_TESORERIA.md).

Principios:

- **Sobre lo nativo de Odoo 19**: los pagos son `account.payment` (con su asiento,
  conciliación con el extracto y diferencia de cambio estándar); el pago de
  facturas pasa por `account.payment.register` para que actúen la retención, el
  ITF, el T.C. pactado y el medio de pago de la suite.
- **Movimientos de banco contra la cuenta de pendientes** del diario (pagos o
  cobros pendientes) para conciliarlos con el extracto; sin cuenta de pendientes,
  la cuenta del banco.
- **No duplicar**: el flujo de caja, los depósitos, los cheques, la caja chica y
  el cierre de caja ya existen; la app los reúne en su menú.
- Patrón de la suite: `models.Constraint`, `_check_company_auto`, reglas por
  compañía, `res.groups.privilege`, textos en español, versión `N.AAAAMMDD`,
  OPL-1, página MkDocs con `modulos:`, ficha YAML, README y CHANGELOG.

## Módulos (OL-ACCOUNTING)

| Módulo | Tipo | Depende de |
|---|---|---|
| `al_l10n_pe_treasury` | **Aplicación** «Tesorería» | `al_account_base`, `al_account_payments`, `al_l10n_pe_itf`, `al_l10n_pe_currency`, `al_l10n_pe_cash_forecast`, `al_l10n_pe_term_deposit`, `al_l10n_pe_check`, `al_l10n_pe_cash_closing`, `al_l10n_pe_cash_fund`, `mail` |
| `al_l10n_pe_bank_loan` | Préstamos y pagarés | `al_l10n_pe_treasury` |
| `al_l10n_pe_bank_guarantee` | Cartas fianza | `al_l10n_pe_treasury` |
| `al_l10n_pe_treasury_batch_payment` | Puente (auto_install) | `al_l10n_pe_treasury`, `al_l10n_pe_batch_payment` |

## F1 — `al_l10n_pe_treasury` (aplicación)

**Seguridad.** Privilegio «Tesorería»: *Usuario* (prepara: posición,
transferencias, programaciones; implica `account.group_account_invoice`),
*Aprobador* (aprueba programaciones y transferencias) y *Administrador*
(configuración, líneas de crédito y segunda aprobación; implica
`account.group_account_user`). Reglas por compañía en todos los modelos.

**Menú raíz «Tesorería»** (ícono propio 50 × 50 estilo Odoo 19):

| Primer nivel | Secciones y acciones |
|---|---|
| Posición | Posición diaria · Bancos y cajas · Movimientos de banco |
| Operaciones | Programación de pagos · Transferencias y cambio de moneda · Cheques (espejo) · Cierres de caja (espejo) · Entregas a rendir (espejo) |
| Financiamiento | Líneas de crédito · Préstamos (F2) · Cartas fianza (F3) · Depósitos a plazo (espejo) |
| Planificación | Flujo de caja proyectado (espejo) |
| Configuración | Ajustes · Bancos y cajas · Bancos |

Espejo en **Perú ▸ Tesorería** de las acciones nuevas.

**1. Bancos y cajas** (`account.journal`): tipo de cuenta (corriente, ahorros,
detracciones BN, recaudadora, caja), saldo mínimo, sobregiro autorizado,
restringida (no suma al disponible), responsable.

**2. Posición de tesorería** `l10n_pe.treasury.position` (documento por fecha,
cron diario que guarda la del día) con líneas por diario:
saldo contable (cuenta del diario), saldo del extracto (último saldo final),
cobros en tránsito y pagos en tránsito (pendientes sin conciliar), pagos
programados aprobados sin pagar, saldo mínimo, sobregiro, disponible =
contable + cobros − pagos − programado − mínimo + sobregiro (0 si restringida);
todo en la moneda del diario y en soles al T.C. del día. Totales por moneda.

**3. Transferencias y cambio de moneda** `l10n_pe.treasury.transfer`:
origen, destino, importe enviado y recibido, T.C. pactado (calculado si las
monedas difieren), contraparte (banco o casa de cambio), n.º de operación,
valorización (*al T.C. pactado* o *al T.C. contable con diferencia a 676/776*),
ITF por lado (por defecto exonerado entre cuentas propias). Flujo: borrador →
por aprobar (si supera el importe de Ajustes) → aprobado → realizado (dos
`account.payment` contra la cuenta de transferencias 1051, conciliados entre sí;
la diferencia en soles va a 676/776) → anulado.

**4. Programación de pagos** `l10n_pe.treasury.payment.plan` + líneas:
fecha de pago, diario, moneda; asistente «Proponer» (vencidos hasta una fecha,
proveedores, prioridad, solo aprobados para pago); importe por documento
(parcial). Flujo: borrador → por aprobar → aprobado (1.ª aprobación; 2.ª si el
total ≥ importe de doble aprobación; quien prepara no aprueba) → pagado (un pago
por proveedor con `account.payment.register`) → anulado. Bloquea documentos ya
incluidos en otra programación abierta. Aviso si el total supera el disponible
de la posición.

**5. Líneas de crédito** `l10n_pe.treasury.credit.line`: banco, tipo
(préstamos, cartas fianza, descuento de letras, global), moneda, límite, vigencia,
uso calculado por los módulos que la consumen (`_l10n_pe_credit_usage`), disponible,
aviso de vencimiento.

**6. Bancarización**: Ajustes (no / avisar / bloquear) e importes (S/ 2 000,
US$ 500); al confirmar un pago con medio «efectivo» (tabla 1: 008, 009) o en
diario de caja desde el umbral.

**Pruebas**: posición (contable, tránsito, restringida, programado), transferencia
misma moneda, compra y venta de US$ con T.C. pactado y con diferencia de cambio,
ITF por lado, aprobación (umbral, doble, quien prepara), programación (propuesta,
parcial, pago, bloqueo de duplicados), bancarización, multicompañía y accesos.

## F2 — `al_l10n_pe_bank_loan`

`l10n_pe.bank.loan` + `l10n_pe.bank.loan.line` (cronograma) + cuentas por tipo y
moneda (como en depósitos):

- Tipos: préstamo (4511/45511/67311), pagaré (4544/45544/6733), otro.
- Cronograma: francés (cuota fija), alemán (capital constante), al vencimiento;
  TEA, base 360/365, frecuencia (mensual, bimestral, trimestral, semestral,
  anual), cuotas, periodo de gracia (total: capitaliza; parcial: solo intereses),
  seguro de desgravamen (% mensual sobre el saldo) y comisión fija por cuota;
  TCEA calculada. Importación del cronograma del banco (edición manual de las
  líneas antes de confirmar).
- Desembolso: Banco (cobros pendientes) ↔ 4511, gastos de desembolso a 6391.
- Devengo mensual automático de intereses (cron, idempotente): 67311 ↔ 45511.
- Pago de cuota: 4511 capital + 45511 interés devengado (+ 67311 lo no devengado)
  + 651 seguro + 6391 comisión ↔ Banco (pagos pendientes); ITF opcional.
- Prepago parcial (reduce cuota o plazo) y total; refinanciación = nuevo préstamo.
- Porción corriente (capital de los próximos 12 meses) y no corriente.
- Uso de la línea de crédito; cuotas en el flujo de caja proyectado; aviso antes
  del vencimiento de cada cuota.

## F3 — `al_l10n_pe_bank_guarantee`

`l10n_pe.bank.guarantee`:

- Sentido: **emitida** a pedido de la empresa (consume línea de crédito) o
  **recibida** de un proveedor o cliente.
- Tipo (fiel cumplimiento, adelanto directo, adelanto de materiales, seriedad de
  oferta, pago, aduanera, otra), banco emisor, beneficiario/afianzado, importe,
  moneda, emisión, vencimiento, n.º, contrato o proceso, condiciones (solidaria,
  irrevocable, incondicional, de realización automática).
- Comisión: tasa trimestral con mínimo, cobrada al emitir y renovar (6391 ↔
  Banco); fondo en garantía enlazado de `al_l10n_pe_term_deposit`.
- Cuentas de orden opcionales (0113 ↔ 0114) al emitir y al liberar.
- Flujo: borrador → vigente → renovada / liberada / ejecutada (ejecución:
  asiento contra el beneficiario).
- Avisos: N días antes del vencimiento y, en las recibidas, el plazo de 15 días
  del art. 1898 del Código Civil para requerir al banco.

## F4 — `al_l10n_pe_treasury_batch_payment`

Al pagar una programación con diario de formato TXT, agrupa sus pagos en un lote
(`account.batch.payment`) listo para generar el archivo del banco.

## Estado (26/10/2026)

F1–F5 desarrolladas: 67 pruebas en verde en `test_pe_treasury` (treasury 40, bank_loan 27
con 4 del cálculo puro, bank_guarantee 13, puente 3; el conteo por módulo incluye las clases
comunes). Pendiente: capturas de las fichas y prueba funcional en una base de cliente.

## F5 — Documentación y cierre

- Páginas en `mkdocs/content/applications/finance/treasury*.md` con `modulos:`,
  entrada en `SUMMARY.md`.
- README, CHANGELOG, `static/description/index.html` (fichas), íconos.
- `scripts/gen_addons_table.py --check`; pruebas en `test_pe_treasury`.

# Análisis: aplicación de Tesorería localizada para Perú

Fecha: 26/10/2026. Alcance: Odoo 19 (CE + EE en `ee19`), suite `al_*` de `ol_new_apps`.

## 1. Qué hace un módulo de Tesorería

Patrón común en el software de referencia (Kyriba, SAP S/4HANA Cash Management,
Dynamics 365 *Cash and bank management*) y en los ERP peruanos (Concar, Starsoft
«Caja y Bancos», Exactus, Softland/Ofisis, Defontana, SIGA del MEF):

| Función | Kyriba / SAP / D365 | ERP peruanos | Odoo 19 nativo |
|---|---|---|---|
| Maestro de cuentas bancarias (banco, tipo, CCI, sobregiro) | sí | sí | `account.journal` + `res.partner.bank` (sin sobregiro ni saldo mínimo) |
| Posición bancaria diaria (contable, extracto, en tránsito, disponible) | sí | sí | tablero de diarios (solo saldo contable y del extracto, sin disponible) |
| Programación / calendario de pagos con aprobación | sí | sí (Exactus, Concar «flujo net») | no (EE: pagos por lote, sin aprobación) |
| Transferencias entre cuentas propias | sí | sí | solo vía conciliación con la cuenta de liquidez en tránsito |
| Compra y venta de moneda extranjera con T.C. pactado | sí | sí | no |
| Préstamos y pagarés con cronograma | sí (TRM) | sí | EE `account_loans`: solo moneda de la compañía, sin banco, sin TEA, sin desembolso |
| Líneas de crédito (límite, uso, disponible) | sí | parcial | no |
| Cartas fianza (emitidas por el banco y recibidas) | sí (D365 *letters of guarantee*) | parcial | no |
| Conciliación | sí | sí | sí (EE) |
| Flujo de caja proyectado | sí | sí | no |
| Libro Caja y Bancos (PLE 1.1 / 1.2) | — | sí | EE `l10n_pe_reports` (TXT) |

## 2. Odoo Apps y OCA

- **OCA** (versión 19.0): `account_payment_order` (órdenes de pago SEPA, sin
  aprobación en 19.0), `account_check_deposit`, `account_netting`.
  **No migrados a 19.0:** `account_loan`, `account_payment_order_tier_validation`,
  `account_cash_deposit`. **OCA/l10n-peru 19.0** no tiene tesorería.
- **Apps Store**: flujo proyectado (Aski $199, Pokutsoft $99–109, Bista, Kaizen),
  tesorería operativa genérica (`treasury_management` $108), aprobación de pagos
  (Softhealer, BrowseInfo $28, DevIntelle $17), cartas de garantía orientadas al
  mercado árabe (LucidBrainz $200, `coa_arabian_letters_of_guarantee` $91) y PLE
  1.1/1.2 de Ganemo (676 €). **No hay líneas de crédito ni préstamos bancarios
  localizados para Perú.**
- **EE `account_loans`** (Odoo 19): cronograma importado o calculado, cuentas de
  corto y largo plazo, asientos de la cuota. Limitaciones para Perú: solo en la
  moneda de la compañía (los préstamos en US$ son habituales), sin desembolso al
  banco, sin TEA/TEM ni base de días, sin seguro de desgravamen ni comisiones, sin
  ITF y sin relación con el banco (línea de crédito). Requiere `account_asset`.

## 3. Lo que ya tiene la suite (no se duplica)

| Módulo | Cubre |
|---|---|
| `al_l10n_pe_cash_forecast` | Flujo de caja proyectado con escenario y real |
| `al_l10n_pe_term_deposit` | Depósitos a plazo, fondos en garantía (respaldo de cartas fianza) |
| `al_l10n_pe_check`, `_check_printing` | Cheques de terceros y propios |
| `al_l10n_pe_cash_closing` | Cierre de caja y arqueo |
| `al_l10n_pe_cash_fund` (+ `_expense`) | Entregas a rendir y caja chica |
| `al_l10n_pe_batch_payment` | Archivos TXT de pagos masivos (BCP, BBVA, IBK, Scotiabank, BN) |
| `al_l10n_pe_bank_statement_import`, `_bank_collection` | Extractos y recaudación |
| `al_l10n_pe_itf` | ITF automático en los pagos (exonera cuentas del mismo titular) |
| `al_l10n_pe_currency` | T.C. compra/venta y **T.C. pactado por pago** |
| `al_account_payments` | Medio de pago SUNAT (tabla 1) y n.º de operación |
| `al_l10n_pe_ple` | PLE 1.1 y 1.2 en Excel |
| `al_l10n_pe_account_letter`, `_factoring` | Letras (descuento en banco) y factoring |

Todas cuelgan hoy de **Perú ▸ Tesorería**; no hay una aplicación de Tesorería
que reúna el trabajo diario del tesorero.

## 4. Huecos (lo que se desarrolla)

**Imprescindible**

1. **Posición de tesorería diaria** por cuenta y moneda: saldo contable, saldo del
   último extracto, cobros y pagos en tránsito, saldo mínimo, sobregiro
   autorizado, cuentas restringidas (detracciones del BN), pagos programados
   aprobados y disponible, con equivalente en soles.
2. **Programación de pagos con aprobación**: propuesta por vencimiento,
   proveedor, moneda y prioridad; importe por documento (parcial); aprobación por
   importe (uno o dos niveles, sin que apruebe quien prepara); pago con el
   asistente nativo (así actúan la retención, el ITF, el T.C. pactado y el medio de
   pago de la suite) y lote con archivo TXT si está `al_l10n_pe_batch_payment`.
3. **Transferencias entre cuentas propias y operaciones de cambio** (compra y
   venta de US$) con T.C. pactado: dos pagos enlazados contra la cuenta de
   transferencias de la compañía (1051), diferencia frente al T.C. contable a
   676/776 si se elige valorizar al T.C. del día, ITF solo cuando corresponde.
4. **Préstamos y pagarés bancarios**: cronograma francés, alemán o al vencimiento
   (*bullet*), TEA y base 360/365, periodo de gracia, seguro de desgravamen y
   comisiones por cuota; desembolso (104 ↔ 4511/4544), devengo mensual de
   intereses (67311 ↔ 45511), pago de la cuota, prepago con recálculo, porción
   corriente y no corriente; moneda extranjera; proyección en el flujo de caja.
5. **Cartas fianza** emitidas por el banco a pedido de la empresa (fiel
   cumplimiento, adelanto, seriedad de oferta, etc.) y **recibidas** de terceros:
   beneficiario, importe, vigencia, renovaciones, comisión (6391) e ITF,
   cuentas de orden opcionales (0113/0114), avisos de vencimiento y del plazo de
   15 días del art. 1898 del Código Civil para requerir al fiador.
6. **Bancarización** (TUO Ley 28194, DL 1529): aviso o bloqueo de pagos en
   efectivo desde S/ 2 000 o US$ 500.

**Deseable (incluido)**

7. **Líneas de crédito** por banco: límite, uso (préstamos, cartas fianza),
   disponible y vencimiento.
8. Tablero de tesorería: disponible por banco, deuda por banco, vencimientos a
   30/60/90 días.

**Fuera de alcance**: conectividad H2H con los bancos, conciliación automática
avanzada (es de Odoo EE), arrendamiento financiero 452 (lo cubre
`al_l10n_pe_lease`), coberturas y derivados.

## 5. Normativa considerada

- **ITF** — TUO Ley 28194 (DS 150-2007-EF): 0,005 %, redondeo del art. 13. Las
  transferencias entre cuentas del mismo titular no están gravadas (Informe SUNAT
  143-2010); se puede marcar como afecta si el banco lo cobra.
- **Bancarización** — art. 4 TUO Ley 28194 modificado por DL 1529: medios de pago
  desde S/ 2 000 o US$ 500; sin ellos se pierde el gasto y el crédito fiscal.
- **PCGE 2019** (presente en `l10n_pe`): 1041 cuentas corrientes, 1051
  transferencias (cuenta de transferencias de la compañía), 4511 préstamos de
  instituciones financieras, 4544 pagarés, 45511/45544 costos de financiación por
  pagar, 67311/6733 intereses, 6391 gastos bancarios, 651 seguros, 6412 ITF,
  676/776 diferencia de cambio, 0113/0114 cuentas de orden.
- **Cartas fianza** — Ley 26702 art. 221; Código Civil art. 1898 (liberación del
  fiador si no se le requiere dentro de los 15 días del vencimiento).
- **Operaciones de cambio** — se registra el T.C. pactado; la diferencia con el
  T.C. contable va a 676/776.

## 6. Fuentes

OCA: github.com/OCA/account-financial-tools (18.0 y 19.0), github.com/OCA/bank-payment
(19.0), github.com/OCA/l10n-peru. Apps: apps.odoo.com/apps/modules/19.0/finance_treasury,
…/19.0/sh_payment_dynamic_approval, …/19.0/letters_of_guarantee,
…/18.0/coa_arabian_letters_of_guarantee, …/19.0/ple_cash_book,
…/18.0/account_loan. Referencia: kyriba.com, sap.com (Cash Management), Dynamics
365 Finance *Cash and bank management*; intercom.help/defontana (tesorería),
realsystems.com.pe (Concar), mef.gob.pe (SIGA, módulo de tesorería). Normativa:
sunat.gob.pe/legislacion/itf/ds150_07.htm, Informe SUNAT 143-2010, DL 1529,
PCGE 2019 (gob.pe), Informe SUNAT 2014-054 (carta fianza).

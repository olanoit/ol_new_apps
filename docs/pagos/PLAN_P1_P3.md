# Plan: comprobante de pago (P1) y anticipos / aplicación de documentos (P3)

Fecha: 21/10/2026. Origen: [ANALISIS_PAGOS_INVERAGRO.md](ANALISIS_PAGOS_INVERAGRO.md).
Principio: **sobre el pago nativo de Odoo 19** (`account.payment` con su asiento, conciliación y
diferencia de cambio estándar). Nada de reescribir `_synchronize_*` ni `_prepare_move_line_default_vals`
como hace Inveragro.

## Lo que da Odoo 19 y se aprovecha

| Pieza nativa | Dónde | Uso |
|---|---|---|
| `account.payment.destination_account_id` (almacenado, editable; dominio cuentas por cobrar/pagar) | `addons/account/models/account_payment.py:130, 627` | El anticipo es un pago normal cuya cuenta destino es la 122 / 422 |
| Plan PE: `chart122` «Anticipos de clientes» (`asset_receivable`, conciliable) y `chart422` «Anticipos a proveedores» (`liability_payable`, conciliable) | `addons/l10n_pe/data/template/account.account-pe.csv` | Cuentas por defecto, sin crear nada |
| `reconciled_invoice_ids` / `reconciled_bill_ids` y conciliaciones parciales | `account_payment.py:148` | Detalle de lo pagado en el recibo |
| `account.report_payment_receipt` | `addons/account/views/report_payment_receipt_templates.xml` | Se reemplaza el contenido, se conserva la acción y el envío por correo |
| `name` del pago = nombre del asiento (secuencia del diario) | `account_payment.py:416` | El número contable no se toca; el del recibo va aparte |
| `currency.amount_to_text` | `res.currency` | Monto en letras |
| Suite: `pe.catalog.payment` y nº de operación (`al_account_payments`), TC compra/venta (`al_l10n_pe_currency`), retención (`al_l10n_pe_retention`), detracción (`al_l10n_pe_detraction`), formato común PDF (`al_report_base.report_pe_page`) | OL-ACCOUNTING / OL-TOOLS | Se reutilizan |

## P1 — `al_l10n_pe_payment_receipt` (OL-ACCOUNTING)

**Objetivo:** recibo de ingreso (cobros) y comprobante de egreso (pagos) impreso, numerado con
serie propia, con el formato común de la suite.

1. **Numeración**
   - `account.journal`: `l10n_pe_receipt_in_sequence_id`, `l10n_pe_receipt_out_sequence_id`
     (`ir.sequence`, creadas al activar la opción en el diario: prefijo `RI01-` / `RE01-`, 8 dígitos).
   - `account.payment.l10n_pe_receipt_number` (Char, `copy=False`, índice): se asigna **al
     confirmar** (`action_post`), una sola vez; un pago vuelto a borrador conserva su número
     (sin huecos ni reutilización). Restricción de unicidad por compañía.
   - Transferencias internas: no llevan recibo.
2. **PDF** (`report_pe_page`, A4 y media hoja A5 a elegir en el diario):
   - Cabecera: empresa (RUC), «RECIBO DE INGRESO» / «COMPROBANTE DE EGRESO», número, fecha.
   - Socio con tipo y nº de documento; concepto (`memo`); medio de pago SUNAT, banco y cuenta,
     nº de operación o de cheque; moneda y TC si no es PEN.
   - Monto en números y en letras.
   - Detalle de lo aplicado: comprobante (tipo-serie-número), fecha, total, importe aplicado
     (de las conciliaciones parciales del pago), saldo; retención y detracción si las hay;
     si es anticipo, «Anticipo – queda a cuenta».
   - Firmas «Entregué conforme / Recibí conforme» con nombre y DNI.
3. **Acciones:** imprimir y enviar por correo (plantilla de correo propia); botón en el pago y
   acción en lote desde la lista.
4. **Pruebas:** numeración por diario y sentido, sin número en borrador, sin doble número al
   volver a borrador, detalle con pago parcial y con dos facturas, monto en letras PEN/USD,
   render del PDF (HttpCase o `_render_qweb_html`).

Esfuerzo estimado: 2-3 días con documentación y ficha.

## P3 — `al_l10n_pe_payment_application` (OL-ACCOUNTING)

**Objetivo:** anticipos a proveedores y de clientes sin comprobante, su aplicación a la factura y
el cruce de documentos (compensaciones), con control de saldos pendientes.

### Nota tributaria (va en la documentación)

- **Ventas:** el pago anticipado por la venta de bienes o servicios hace nacer la obligación del
  IGV y exige emitir comprobante (Ley del IGV art. 4; Reglamento de Comprobantes art. 5). Ese caso
  ya lo resuelve el **anticipo de venta con factura** (nativo + `al_l10n_pe_edi_downpayment_discount`).
  La 122 sin comprobante queda para **arras, depósitos o garantías** y cobros **a cuenta** aún no
  identificados con una venta.
- **Compras:** la 422 registra lo pagado al proveedor hasta recibir su comprobante (de anticipo o
  final); es el caso más frecuente.

### 3.1 Anticipo como pago

- `account.payment.l10n_pe_is_advance` (Boolean) y en `account.payment.register` (para cuando se
  paga desde un pedido o sin factura).
- Override de `_compute_destination_account_id`: si es anticipo, la cuenta de anticipos de la
  compañía según tipo de socio y moneda:
  `res.company.l10n_pe_advance_customer_account_id` (def. 122), `..._customer_fc_account_id`
  (opcional, USD), `..._supplier_account_id` (def. 422), `..._supplier_fc_account_id`.
  Ajustes en **Contabilidad PE**.
- Pedido de compra/venta opcional en el anticipo (`l10n_pe_advance_order_ref`) para sugerirlo al
  facturar ese pedido.
- El recibo de P1 muestra «Anticipo».

### 3.2 Aplicación de documentos (asistente único)

`l10n_pe.payment.application` (documento, no transitorio, con historial):

- Cabecera: socio, fecha, diario de aplicaciones (misceláneo, configurable), moneda, tipo:
  **Aplicar anticipo** | **Compensar cobrar/pagar** | **Aplicar nota de crédito** | **Libre**.
- Líneas «a cancelar» y «con qué»: apuntes abiertos conciliables del socio (facturas, anticipos
  122/422, NC, letras no bancarizadas), con importe a aplicar editable (parcial) en la moneda del
  apunte.
- **Validar:** crea un asiento en el diario de aplicaciones que traslada los saldos
  (p. ej. Dr 122 / Cr 121 para aplicar un anticipo de cliente; Dr 421 / Cr 422 para proveedor;
  Dr 421 / Cr 121 para compensar) y concilia cada línea con su apunte original
  (`reconcile()` estándar: la diferencia de cambio la genera Odoo).
- Reglas: total a cancelar = total con qué; mismo socio (o socios del grupo si se marca
  «compensación entre vinculados», con aviso); no aplica letras/facturas negociables en el banco
  (P9); bloqueo de fechas contables; reversión (botón «Revertir»: asiento inverso y desconcilia).
- Botones de acceso: en la **factura** «Anticipos disponibles (n)» si el socio tiene saldo en
  122/422 → abre el asistente con la factura y los anticipos precargados; en el **pago anticipo**
  «Aplicar a factura».

### 3.3 Control

- Lista **Anticipos pendientes** (apuntes de las cuentas de anticipo con saldo, agrupados por socio,
  antigüedad en días, moneda) con filtros clientes/proveedores y vista pivote.
- Aviso en la factura de proveedor al publicarla si el proveedor tiene anticipos sin aplicar.

### 3.4 Pruebas

Anticipo de proveedor PEN aplicado total y parcial; anticipo en USD aplicado a factura en USD con
otro TC (diferencia de cambio nativa); compensación 12 vs 42; NC aplicada a otra factura; reversión;
socio distinto rechazado; documento bancarizado rechazado; multicompañía (check_company,
reglas `company_ids`).

Esfuerzo estimado: 4-6 días con documentación y ficha.

## Entregables comunes

- Seguridad: ACL por modelo, reglas multicompañía, grupos de contabilidad; reversión solo
  administrador de contabilidad.
- Interfaz en español (solo primera mayúscula), `i18n/es.po` si hay mixins.
- Ficha `docs/fichas/<módulo>.yml`, página MkDocs en
  `mkdocs/content/applications/finance/fiscal_localizations/peru/` con `modulos:`, CHANGELOG.
- Pruebas en una base `test_` y validación funcional en `ol_pe_v19` (como el módulo de gratuitas).

## Orden

1. P1 (no depende de P3; P3 lo usa para imprimir el anticipo).
2. P3.1 + P3.3 (anticipo y control).
3. P3.2 (aplicación/cruce).
Después: P2 (pago múltiple) reutiliza el recibo (P1) y la aplicación (P3).

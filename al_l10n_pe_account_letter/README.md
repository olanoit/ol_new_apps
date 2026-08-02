# PE - Letras de cambio y canje (AL)

Gestión de **letras de cambio y canje** para la localización peruana:
canje de comprobantes pendientes, generación masiva de letras, tipos de
letra con enrutamiento contable por moneda, canje individual (cobranza
libre / descuento), refinanciación (individual y masiva) y control de
residuales/redondeo.

Migrado desde `ol_l10n_pe_account_letter` (proyecto Inveragro, Odoo 19) y
refactorizado a fondo para adoptar el namespace `l10n_pe.*` del proyecto,
prefijar los campos que extienden `account.move`/`account.move.line`,
eliminar código muerto/duplicado y usar botones inteligentes + pestañas
condicionales. **Demo/validación funcional:**
[`tools/account_letter_demo_data.py`](tools/account_letter_demo_data.py).

## Qué hace

- **Canje de letras (clientes/proveedores)** (`l10n_pe.letter`): convierte
  comprobantes pendientes (facturas, boletas, notas de débito, liquidaciones
  de cobranza, aperturas) en un canje que reemplaza el saldo por cobrar/pagar
  por una obligación cambiaria. Estados:
  `draft → checked → redeemed → banked` (con `cancel`), con trazabilidad
  automática en el chatter (`mail.thread` + `tracking=True` en `state`).
- **Generación masiva de letras** (`l10n_pe.letter.line`): a partir de un
  canje confirmado, crea N letras repartiendo el saldo (total o parcial)
  según cantidad, fecha de vencimiento y rango de días entre vencimientos.
- **Tipos de letra**: "En cartera", "Cobranza libre", "Descuento" y
  "Protestada", cada uno enrutado a la cuenta contable configurada por
  combinación (tipo de cuenta × tipo de letra × moneda × compañía) en
  `l10n_pe.letter.account.config`.
- **Canje individual de una letra** (cobranza libre o descuento) mediante
  el asistente `l10n_pe.letter.canje.wizard`, generando el asiento y
  conciliando contra el asiento del canje original.
- **Refinanciación de canjes**:
  - Individual (`l10n_pe.letter.refinance.wizard`): refinancia un canje
    generando uno nuevo con la fecha indicada, arrastrando el saldo
    adeudado como línea de origen (tipo de documento `99` — Letra).
  - Masiva (`l10n_pe.letter.refinance.massive.wizard`): refinancia varios
    canjes del mismo socio/diario/moneda/compañía en un único canje hijo.
- **Canje masivo** (`l10n_pe.letter.massive`, botón "Método" con
  `l10n_pe.letter.type.wizard`): agrupa canjes ya canjeados del mismo socio
  en un registro consolidado.
- **Residuales/redondeo** (`l10n_pe.letter.residual`): registra la
  diferencia de redondeo entre el total facturado y el total canjeado.
- **Vinculación de asientos por referencia**: reconecta un canje ya
  canjeado con su asiento contable buscando por `ref` (útil tras
  importaciones o migraciones).
- Extiende `account.move` / `account.move.line` con el estado de canje
  (`l10n_pe_letter_redeemed_state`) y accesos directos al canje relacionado.

## Cambios respecto al módulo original (migración + refactor)

- **Namespace de modelos**: todos los modelos propios pasan de `account.*`
  (genérico, con riesgo de colisión — `account.configuration` en particular
  sonaba a ajuste global de Odoo) al namespace `l10n_pe.*` usado por el
  resto de módulos PE del proyecto (`al_l10n_pe_retention`,
  `al_l10n_pe_detraction`). Ver tabla de modelos abajo.
- **Campos en modelos core prefijados**: los campos añadidos a
  `account.move` (`l10n_pe_letter_id`, `l10n_pe_letter_ids`,
  `l10n_pe_letter_redeemed_state`, `l10n_pe_letter_name`) y a
  `account.move.line` (`l10n_pe_letter_line_id`,
  `l10n_pe_letter_invoice_line_id`, `l10n_pe_letter_id`,
  `l10n_pe_partner_vat`) siguen la convención `l10n_pe_*` del proyecto.
  Se eliminaron `is_redeemed`, `payment_state` y `redeemed_state` de
  `account.move.line`: eran campos muertos (nunca leídos/escritos fuera de
  su propia declaración).
- **Tipo de cambio**: usa las tasas compra/venta SUNAT de
  `al_l10n_pe_currency` (tabla `res.currency.rate` con `rate_purchase` /
  `rate_sale`) en vez del helper multitasa de `ol_l10n_pe_account`
  (no existe en este proyecto).
- **Dependencias eliminadas**: `ol_l10n_pe_account`,
  `ol_l10n_pe_account_withholdings` y `ol_partner_contact_type` no se usaban
  en la lógica del módulo (solo figuraban en el manifest); se reemplazan por
  `al_account_base` + `al_l10n_pe_currency` + `l10n_latam_invoice_document`.
- **Tipo de documento real**: el campo `document_type_id_code` (un
  `Selection` que reproducía a mano códigos SUNAT) se reemplazó por
  `document_type_id`, un `Many2one` a `l10n_latam.document.type` (dominado
  a Perú) — los códigos estándar (01, 03, 08, 54, 91) ya existen como datos
  reales de `l10n_pe`; los códigos internos del módulo (`99` Letra, `00`
  Apertura) se declaran en `data/document_type_letter.xml`.
- **Código muerto eliminado**: 14 campos-sombra de fecha/usuario +
  `_stamp_event()` + pestaña "Registros" (la trazabilidad ya la da el
  chatter, con `tracking=True` en `state`); `is_admin`/`is_user` +
  `_compute_is_group()` (sin uso real, solo `invisible="1"` en la vista);
  campo duplicado `letter_copy_line_ids` (se reemplazó por `letter_line_ids`
  con `readonly`/`create`/`delete` dependientes del estado).
- **Deduplicación de lógica contable**: `action_redeemed`,
  `action_canje_create` y `action_redeemed_refinance` construían de forma
  casi idéntica cada línea de asiento (debe/haber según tipo de cambio);
  ahora comparten el helper privado `_build_letter_move_line_vals`.
- **`l10n_pe.letter.account.config`** (antes `account.configuration`):
  el chequeo de duplicados pasó de `@api.constrains` + `search()` +
  `UserError` a una constraint SQL declarativa (`models.Constraint`, nativa
  de Odoo 19), atómica y sin condición de carrera; se agregó `company_id`
  (multi-compañía) a la combinación única y al dominio de `account_id`.
- **UI**: el asiento contable (`account_id`) se muestra como botón
  inteligente (antes era un campo de texto); las pestañas "Redondeos" y
  "Apuntes contables" solo aparecen cuando hay datos que mostrar.
- **Corrección de un bug pre-existente**: `action_open_massive_refinance_wizard()`
  apuntaba a un xmlid de acción inexistente (`action_account_massive_refinance`)
  y nunca había sido ejercitado por tests/demo; ahora referencia la acción
  real del asistente de refinanciación masiva.
- **Correcciones aplicadas durante la migración** (afectaban el flujo real,
  no solo el estilo):
  - `rest_amount_currency` no tenía `compute=` propio: dependía de que
    `rest_amount` se hubiera leído antes (p.ej. al abrir el formulario), por
    lo que `create_letters()` podía no generar ninguna letra si se llamaba
    sin haber mostrado antes el formulario. Ahora ambos campos comparten el
    mismo compute.
  - `compute_payment_ids` buscaba pagos con el dominio inválido
    `('line_ids.name', '=', ...)` (`account.payment` no tiene `line_ids` en
    v19); se corrigió a `('move_id.line_ids.name', '=', ...)`.
  - Limpieza de parámetros de campo inválidos (`tracking`/`digits` en
    modelos sin `mail.thread` o en `Monetary`) y de un `@api.constrains`
    sobre un campo `related` no almacenable.

## Modelos

| Modelo | Descripción |
|--------|-------------|
| `l10n_pe.letter` | Canje de letras (cabecera). |
| `l10n_pe.letter.line` | Letra individual generada por un canje. |
| `l10n_pe.letter.invoice.line` | Línea de comprobante origen dentro del canje. |
| `l10n_pe.letter.type.wizard` | Selector transitorio para canje masivo por tipo. |
| `l10n_pe.letter.massive` | Canjes masivos por socio (extiende `l10n_pe.letter`). |
| `l10n_pe.letter.residual` | Líneas de redondeo/residual del canje. |
| `l10n_pe.letter.account.config` | Mapeo tipo de cuenta/letra/moneda/compañía → cuenta contable. |
| `l10n_pe.letter.canje.wizard` | Asistente de canje individual (transient). |
| `l10n_pe.letter.refinance.wizard` | Asistente de refinanciación individual (transient). |
| `l10n_pe.letter.refinance.massive.wizard` | Asistente de refinanciación masiva (transient). |
| `l10n_pe.letter.link.summary` | Resumen de vinculación de asientos (transient). |

Extiende también `account.move` y `account.move.line`.

## Menú

Los mismos accesos están duplicados en dos árboles (misma acción, distinto
punto de entrada):

- **Perú ▸ Letras de cambio** (Clientes/Proveedores: canje, canje masivo,
  letras e historial de canje) y **Perú ▸ Configuración ▸ Cuentas de letras**.
- **Contabilidad ▸ Clientes/Proveedores ▸ Letras** (mismos submenús) y
  **Contabilidad ▸ Configuración ▸ Cuentas de letras**.

## Configuración previa

1. **Perú ▸ Configuración ▸ Cuentas de letras** (`l10n_pe.letter.account.config`):
   dar de alta la cuenta contable para cada combinación
   (Por cobrar/Por pagar × tipo de letra × moneda × compañía) que se vaya a
   usar.
2. **Diarios**: crear diarios cuyo nombre contenga "letra" y "cobrar"
   (clientes) o "letra" y "pagar" (proveedores) — es el filtro que usa el
   campo `journal_id` del canje.
3. Cuentas contables llamadas exactamente **"Redondeo"** (tipo *Gasto* y
   tipo *Otros ingresos*) para el asiento de residual/redondeo.

## Dependencias

`mail`, `al_account_base`, `al_l10n_pe_currency`, `l10n_latam_invoice_document`.

## Pruebas

Tests unitarios (`tests/`):

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_account_letter \
  --test-enable --test-tags /al_l10n_pe_account_letter --stop-after-init
```

Validación funcional end-to-end (facturas reales, canje, letras masivas,
cobranza libre/descuento, refinanciación individual y masiva, canje masivo,
flujo de proveedor y vinculación de asientos):

```bash
./odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < tools/account_letter_demo_data.py
```

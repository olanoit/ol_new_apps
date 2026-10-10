# PE - OSE The Factory HKA (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo técnico `al_ose_factory_hka`. Añade **The Factory HKA** a los operadores
de la facturación electrónica peruana de Odoo 19 (`l10n_pe_edi`), junto a IAP,
SUNAT y Estela, y envía y revierte los comprobantes de retención (CRE) de
`al_l10n_pe_retention`. Migrado de los módulos 17.0 `al_ose_factory_hka` y
`al_ose_factory_hka_retention`, unificados aquí.

## Cómo funciona

Factory HKA expone el mismo `billService` SOAP de SUNAT. El módulo solo aporta
sus credenciales y su WSDL; firma, envío, CDR y bajas usan los servicios
comunes de `l10n_pe_edi`, que eligen el método por el nombre del operador:

| Operación | Servicio HKA | Método |
|---|---|---|
| Envío de facturas, boletas y notas | `sendBill` | `_l10n_pe_edi_sign_invoices_factory_hka` |
| Envío de otros documentos (p. ej. CRE) | `sendBill` | `_l10n_pe_edi_sign_service_factory_hka` |
| Consulta del CDR (documento ya registrado) | `getStatusCdr` | `_l10n_pe_edi_get_status_cdr_factory_hka_service` |
| Comunicación de baja (facturas y sus notas) | `sendSummary` / `getStatus` | `_l10n_pe_edi_cancel_invoices_step_1/2_factory_hka` |
| Baja de notas de boleta (resumen diario RC, estado 3) | `sendSummary` / `getStatus` | `_l10n_pe_edi_factory_hka_boleta_summary` |
| CRE (tipo 20) | `sendBill` | `account.payment._l10n_pe_edi_sign_retention` |
| Reversión del CRE (RR) | `sendSummary` / `getStatus` | `account.payment.action_l10n_pe_edi_reverse_retention` / `_check_reversal` |

HKA exige el número con 8 dígitos en el nombre del archivo
(`RUC-01-F001-00000011`); el número del comprobante no cambia.

## Boletas, plazos y observaciones

- **Baja de boletas y sus notas:** SUNAT no las admite en la comunicación de
  baja (RA): se informan en un resumen diario (RC, versión 1.1) con estado 3
  «Anulado», con la fecha de emisión como `ReferenceDate` e identificador
  `RC-AAAAMMDD-N` (guía SUNAT del resumen diario; R.S. 117-2017/SUNAT art.
  17.4, plazo hasta el sétimo día calendario siguiente a su generación). La
  boleta misma solo se anula con nota de crédito, como ya exige `l10n_pe_edi`;
  la nota vinculada a una boleta sí se da de baja, y va en el resumen. Una baja
  no mezcla facturas con documentos de boleta ni fechas de emisión distintas.
- **Plazo de envío de facturas:** si una factura o su nota se envía después del
  tercer día calendario siguiente a la emisión (R.S. 000003-2023/SUNAT), queda
  un aviso en su historial: fuera de plazo no tiene calidad de factura.
- **Observaciones del CDR:** si SUNAT acepta el comprobante con observaciones
  (`cbc:Note`), se listan en el historial para corregir el dato en los
  siguientes.

## Configuración

*Ajustes ▸ Contabilidad ▸ Facturación electrónica peruana*: operador
**The Factory HKA**, usuario, contraseña y WSDL de demostración y producción
(por compañía). Con **Entorno de prueba** se usa el de demostración.

Sin credenciales o sin WSDL de producción el comprobante queda pendiente con
el motivo en la factura: nunca se envía al ambiente de demostración por error.

**Funciones de Factory HKA** (por compañía, activadas por defecto):

| Función | Desactivada |
|---|---|
| Comprobantes de retención (CRE) | El CRE va directo a SUNAT con la clave SOL (que vuelve a mostrarse) |
| Reversión del CRE | Sin botón «Revertir CRE»; solo se ofrece si el CRE va por HKA |

## Reversión del CRE

SUNAT no acepta el tipo 20 en la comunicación de baja (`VoidedDocuments`, RA,
error 2308): el CRE se revierte con un **resumen de reversiones**
(`SummaryDocuments`, plantilla `cre_reversal_summary`) con estado `3` e importe
`0.00`. El `cbc:ID` es `RR-AAAAMMDD-N` sin RUC (error 2220) y el archivo
`RUC-RR-AAAAMMDD-N`; el correlativo sale de la secuencia
`al_ose_factory_hka.reversal_sequence` y se reutiliza en los reintentos.

1. Pago con CRE aceptado ▸ **Motivo de la reversión** ▸ **Revertir CRE**:
   envía el resumen y guarda el ticket (estado «Reversión en proceso»).
2. **Consultar reversión**: pregunta por el ticket; con SUNAT procesando (98)
   se reintenta; aceptada, el CRE queda «Anulado» con el CDR adjunto.

La reversión no toca el asiento del pago.

## Diferencias con la versión 17.0

- Sin código SOAP propio: los servicios comunes de Odoo 19 ya cubren envío,
  CDR y bajas, con sus mensajes de error y reintentos.
- Sin pestaña de depuración con XML, ZIP y respuesta: el EDI de Odoo ya guarda
  el XML firmado y el CDR como adjuntos y muestra el error en la factura.
- La falta de configuración es un error del comprobante, no una excepción que
  detenga el cron del EDI.
- Novedad respecto de 17.0: baja de notas de boleta por resumen diario,
  aviso de plazo de envío y observaciones del CDR.
- El XML, la serie y el PDF del CRE ya no se generan aquí (lo hacía
  `voucher.retention` en 17.0): los resuelve `al_l10n_pe_retention`.

## Pruebas

`tests/test_factory_hka.py` simula el billService de HKA: envío con el WSDL y
el usuario de HKA, nombre del archivo, credenciales faltantes, baja en dos
pasos, consulta del CDR, baja de una nota de boleta por resumen diario (XML
RC), baja mixta rechazada, aviso de plazo y observaciones del CDR.
`tests/test_factory_hka_retention.py`: CRE por HKA o
directo a SUNAT según el ajuste, XML del resumen RR, reversión en dos pasos,
reintento con el mismo correlativo y función desactivada.

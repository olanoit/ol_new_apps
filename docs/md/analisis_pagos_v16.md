# Análisis: pagos en new-inveragro (Odoo 16) frente a la suite

Fecha: 12/10/2026. Fuente v16: `/home/och/odoo/ce16/new/new-inveragro/inveragro_pagos`
(unas 7 500 líneas: `models/`, `models/cuentarendir/`, `wizard/`). Suite:
`al_account_payments`, `al_l10n_pe_detraction`, `al_l10n_pe_retention`,
`al_l10n_pe_currency`, `al_l10n_pe_exchange_closure`, `al_l10n_pe_sire`,
`al_l10n_pe_ple` y el nuevo `al_l10n_pe_cash_fund`.

El desarrollo es *clean-room*: se implementa desde la norma y desde Odoo 19,
no desde el código v16, que solo sirvió para saber qué necesidad cubría.
Las retenciones del IGV se analizaron aparte en
[analisis_retenciones_v16.md](analisis_retenciones_v16.md).

## 1. Proceso de pagos de punta a punta

1. **Fondos para gastos**: el área pide dinero (entrega a rendir) o se abre
   una caja chica; se aprueba y tesorería entrega el dinero.
2. **Gasto y sustento**: el trabajador paga facturas de proveedores y
   movilidad sin comprobante, y rinde cuentas: facturas y planilla de
   movilidad.
3. **Liquidación**: devuelve el saldo, se le reembolsa el exceso o se repone
   la caja chica; el fondo se cierra.
4. **Pagos a proveedores**: pago individual o masivo por archivo del banco,
   con medio de pago SUNAT y número de operación (bancarización).
5. **Detracciones**: depósito en el Banco de la Nación y registro de la
   constancia (individual, masivo o importada de SUNAT).
6. **Retenciones del IGV**: comprobante de retención con el pago.
7. **Tesorería en moneda extranjera**: compra y venta de moneda entre cuentas
   propias al tipo de cambio del banco; diferencia de cambio.
8. **Conciliación**: el número de operación enlaza el pago con el extracto.

## 2. Comparación por etapa

| Etapa | v16 (`inveragro_pagos`) | Suite antes de este análisis | Diferencia | Prioridad |
|---|---|---|---|---|
| Entregas a rendir | `cuentas.rendir.aprobacion` + `account.payment` con líneas propias; carga de documentos por asistente | Nada | Faltaba todo el ciclo | **Alta** |
| Planilla de movilidad | `planilla.lines.movilidad`, Excel con xlsxwriter, **sin tope del 4 % de la RMV** | Nada | Falta la planilla legal y su control | **Alta** |
| Caja chica | `account.petty.cash`: crea un diario por caja (busca por código), aumentos y pagos | Nada | Faltaba el fondo fijo y su reposición | **Alta** |
| Constancias de detracción | Asistente que lee el Excel de SUNAT (`detraccion_upload_file.py`) | Registro individual y depósito masivo (TXT BN) | Faltaba la importación masiva | **Alta** |
| Número de operación | Campo en el pago | Campo y medio de pago SUNAT (`al_account_payments`) | No se podía exigir por diario | **Media** |
| Compra y venta de moneda | Pago con «T.C. en comprobantes» (`custom_date_tc_line`) | Solo transferencias internas nativas, al T.C. del sistema | Faltaba el T.C. del banco y la diferencia | **Media** |
| Pagos masivos a proveedores | Solo Telecrédito BCP (en otro módulo) | Ninguno | Formatos de banco | Media → módulo aparte |
| Fecha del pago | Prohíbe fechas futuras | Comportamiento nativo | Ver § 4 | Baja |
| Plazos de pago en monto fijo | Reescribe `_compute_terms` para montos fijos en moneda de la compañía | Reparto de la detracción en el asiento | Caso cubierto por la detracción | Baja |
| Importación de facturas de compra | `import_in_invoice.py` (Excel propio) | Propuesta del SIRE (`al_l10n_pe_sire`) | El SIRE es la fuente oficial | Baja |
| Pago múltiple con líneas propias | `account.payment.lines` | Pagos agrupados nativos | Específico del cliente | Cliente |
| Reportes de ventas, metas, zonas, catálogo 23 | `sale_meta*`, `res_zone`, `close_sale_report`, `catalog_23` | — | No son pagos | Cliente |

## 3. Mejoras propuestas

Cada una con su fundamento y esfuerzo estimado (días de desarrollo con
pruebas y documentación).

1. **Entregas a rendir con rendición por facturas** — alta, 3 d.
   PCGE 2019, cuenta 1413 «Personal - Entregas a rendir cuenta»: el dinero es
   una cuenta por cobrar al trabajador hasta que la sustenta. La rendición
   debe pagar las facturas del proveedor (no un gasto suelto) para que el PLE
   y el SIRE vean el comprobante pagado. **Hecho** (`al_l10n_pe_cash_fund`).
2. **Planilla de gastos de movilidad** — alta, 1 d.
   Art. 37 inciso a1) del TUO de la Ley del Impuesto a la Renta (tope diario
   por trabajador del 4 % de la RMV) y art. 21 inciso v) de su Reglamento
   (numeración, empresa, periodo, fecha de emisión, fecha, trabajador y
   documento, motivo, destino y monto por desplazamiento, firma). RMV de
   S/ 1 130 por el D.S. 006-2024-TR. **Hecho** (`al_l10n_pe_cash_fund`):
   tope configurable, aviso del exceso no deducible, PDF con los datos
   obligatorios.
3. **Caja chica con reposición** — alta, 1 d.
   Fondo fijo: se repone por lo rendido. Mismo mecanismo que la entrega a
   rendir con una cuenta conciliable propia (la 102 «Fondos fijos» del PCGE
   es de efectivo y no se concilia). **Hecho** (`al_l10n_pe_cash_fund`).
4. **Importación de constancias de detracción** — alta, 1,5 d.
   El número y la fecha de la constancia son los campos 32-33 del PLE 8.1 y
   condicionan el uso del crédito fiscal (D. Leg. 940). La consulta de
   constancias de SUNAT Operaciones en Línea entrega un Excel; importarlo
   evita la digitación. **Hecho** (`al_l10n_pe_detraction` 22): compras y
   ventas, vista previa, registro opcional del depósito.
5. **Número de operación obligatorio por diario** — media, 0,5 d.
   Bancarización (TUO de la Ley 28194): el pago debe sustentarse con el medio
   de pago y su operación; el Libro Caja y Bancos lo pide. **Hecho**
   (`al_account_payments` 8).
6. **Compra y venta de moneda al tipo de cambio del banco** — media, 1,5 d.
   NIC 21: la diferencia entre el tipo de cambio pactado y el de la fecha
   (SUNAT) es ganancia o pérdida por diferencia de cambio (776 / 676).
   **Hecho** (`al_account_payments` 8): dos pagos por la cuenta de
   transferencias y asiento de la diferencia.
7. **Pagos masivos a proveedores con archivo del banco** — media, 5-8 d.
   Formatos BCP, BBVA, Interbank, Scotiabank y Banco de la Nación. Es un
   módulo propio: ver **`al_l10n_pe_batch_payment`** en
   [propuesta_modulos_faltantes.md](propuesta_modulos_faltantes.md).
   **Pendiente (módulo sugerido aparte)**.
8. **Aviso de fecha futura en pagos** — baja, 0,2 d. Un aviso (no un
   bloqueo) cuando la fecha del pago es posterior a hoy. **Pendiente**.
9. **Plazos de pago con monto fijo en moneda extranjera** — baja, 1 d.
   Solo si un cliente lo pide; la detracción ya separa su cuota.
   **Pendiente**.
10. **Importación de facturas de compra** — baja. La propuesta del SIRE
    (`al_l10n_pe_sire`) es la fuente oficial; no se replica el Excel propio.
    **Pendiente / no recomendada**.

## 4. Lo que v16 hace mal y no debe copiarse

- **Importación de constancias**: lee columnas por posición fija, supone años
  de dos dígitos (`2000 + anio`), sale con `return` dentro del bucle tras la
  primera fila, concatena un entero a un texto (`'Fila : ' + i`, que lanza
  `TypeError`), arma un dominio mal formado con un campo inexistente
  (`parter_id.vat`) y busca por nombre sin filtrar compañía ni tipo de
  comprobante. La suite lee las columnas por su encabezado, empareja por RUC y
  serie-número en compras y ventas, filtra por compañía y muestra una vista
  previa.
- **Cuenta de retención buscada por código** (`'401141'`): falla en otro plan
  contable o en multicompañía. La suite usa cuentas configurables por compañía.
- **Prohibir pagos con fecha futura**: impide registrar pagos diferidos o
  programados que el banco ya confirmó; a lo sumo, un aviso.
- **Caja chica que crea diarios** buscándolos por código y con `sudo()` sin
  justificar: duplica diarios y salta la seguridad. La suite usa el diario
  de banco o caja existente y una cuenta conciliable.
- **Planilla de movilidad sin tope ni datos obligatorios** (Excel sin
  documento del trabajador ni control del 4 % de la RMV): no sustenta el gasto
  ante SUNAT.
- **Secuencias buscadas con `sudo()` por código** y **reescritura completa
  de `_compute_terms`**: rompen con cada actualización de Odoo.
- **Estado del fondo sin conciliación**: v16 marca «pagado» por sumas; la
  suite concilia los apuntes de la 1413 y cierra solo con saldo cero.

## 5. Desarrollado

| Módulo | Versión | Qué | Pruebas |
|---|---|---|---|
| `al_l10n_pe_cash_fund` (nuevo, OL-ACCOUNTING) | 1.20261011 | Entregas a rendir y caja chica: entrega, rendición (facturas y movilidad), devolución, reembolso, reposición, cierre conciliado; planilla de movilidad y liquidación en PDF | 7 |
| `al_l10n_pe_detraction` | 22.20261011 | Importar constancias de SUNAT (Excel/CSV) con vista previa y depósito opcional | 73 en total (3 nuevas) |
| `al_account_payments` | 8.20261011 | Número de operación obligatorio por diario; asistente de compra y venta de moneda | 14 en total (3 nuevas) |

Documentación: ficha de cada módulo (`docs/fichas/`), páginas
`applications/finance/accounting/cash_fund.md`,
`fiscal_localizations/peru/detractions.md` y
`fiscal_localizations/peru/payment_methods.md`.

## 6. Pendiente

- **Módulo aparte**: pagos masivos a proveedores (`al_l10n_pe_batch_payment`).
- **Baja prioridad**: aviso de fecha futura, plazos de pago fijos en moneda
  extranjera, importación de compras fuera del SIRE.
- **Específico del cliente** (no se desarrolla en la suite): pago múltiple con
  líneas propias, reportes de ventas, metas, zonas y catálogo 23.
- **Mejora posible de `al_l10n_pe_cash_fund`**: aprobación por niveles (hoy
  aprueba contabilidad) y aviso cuando un mismo día tiene planilla y
  comprobantes de movilidad del mismo trabajador (art. 21 v, numeral 1).

## 7. Segunda revisión (12/10/2026)

Se revisaron todos los desarrollos v16 que heredan `account.payment`. Solo los
de Inveragro son peruanos; los `mblz_*` de Onesta son chilenos (RUT, Banco de
Chile, Santander) y los de BNI, Socialite y Omnia, mexicanos (CFDI, STP).

| Brecha | Resultado |
|---|---|
| Cheques recibidos y diferidos (`dv_account_inbound_check`) | **Desarrollado**: `al_l10n_pe_check` 1.20261012 sobre el nativo `l10n_latam_check` (diarios y cuentas del PCGE, emisor con RUC o DNI, plazo de presentación de la Ley 27287); 9 pruebas |
| Telecrédito BCP completo (`dv_l10n_pe_account_batch_payment_bcp`) | **Desarrollado**: `al_l10n_pe_batch_payment` 3.20261012 (estructura de proveedores con ITF, modalidad y registro 3 por comprobante; un abono por proveedor; cuenta del mismo banco por defecto); 14 pruebas |
| Proyección de cobranza (`payment_projection`) | Pendiente: no lo cubre Odoo ni la suite |
| Respuesta del banco (rechazos del lote) | Pendiente: requiere el formato de cada banco |
| Comprobante de egreso con monto en letras | Pendiente |
| BanBif y Pichincha para proveedores | Pendiente |
| TXT 0621 de retenciones sufridas | No se desarrolla: SUNAT precarga las retenciones de los CRE electrónicos en el 621 |
| CRE sin pago | Ya cubierto por `al_l10n_pe_retention` (mejora 5 de `analisis_retenciones_v16.md`) |

La estructura del archivo BCP se tomó del formato de pago a proveedores de
Telecrédito; el registro 3 solo se envía cuando los comprobantes suman el
abono (sin notas de crédito). Como el resto de formatos, se valida con el
banco antes del primer pago real.

## Fuentes

- [TUO de la Ley del Impuesto a la Renta, capítulo VI (art. 37 a1)](https://www.sunat.gob.pe/legislacion/renta/ley/capvi.pdf)
- [Reglamento de la Ley del Impuesto a la Renta, capítulo VI (art. 21 v)](https://www.sunat.gob.pe/legislacion/renta/regla/cap6.pdf)
- [TUO de la Ley 28194 (bancarización e ITF)](https://www.sunat.gob.pe/legislacion/itf/ds150_07.pdf)
- [PCGE modificado 2019 (MEF)](https://www.mef.gob.pe/contenidos/conta_publ/documentac/PCGE_2019.pdf)
- D.S. 006-2024-TR (RMV S/ 1 130 desde el 1 de enero de 2025).
- Sistema de detracciones: D. Leg. 940 y R.S. 183-2004/SUNAT.

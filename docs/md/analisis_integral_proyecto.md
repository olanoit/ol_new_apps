# Análisis integral del proyecto

Revisión de la suite `ol_new_apps` (Odoo 19) del 12/10/2026, después de las
mejoras de retenciones (1 a 7), pagos (`al_l10n_pe_cash_fund`, detracciones,
pagos) y los módulos nuevos de renta de 4.ª categoría, percepciones y
liquidación de compra. Fuentes: manifiestos, README y CHANGELOG de las 8
áreas, la documentación de `mkdocs/content/`, los análisis de `docs/md/`
(`propuesta_modulos_faltantes.md`, `analisis_pagos_v16.md`,
`analisis_retenciones_v16.md`, `analisis_requerimientos_implementacion.md`),
`docs/planificador/ACEPTACION.md` y los pendientes conocidos del PLE.

## 1. Estado general

La suite cubre la localización peruana de punta a punta: comprobantes
electrónicos (factura, boleta, notas, guía, liquidación de compra, CRE,
comprobante de percepción) con cuatro operadores, libros PLE y registros
SIRE, detracciones, retenciones, percepciones, renta de 4.ª categoría,
tipo de cambio y su cierre, letras, factoring, depósitos, NIIF 16, kárdex,
planillas completas (régimen general y construcción civil), TPV, caja chica
y entregas a rendir, y la gestión de obras. Lo que falta son piezas de
tesorería, de cierre tributario mensual y de compras importadas, más la
validación real con SUNAT/OSE de lo que hoy solo está probado con simulación.

## 2. Huecos y pendientes

### 2.1 Módulos sugeridos aún no hechos

| Qué | Dónde iría | Valor | Esfuerzo | Base |
|---|---|---|---|---|
| Pagos masivos a proveedores con TXT de BCP, BBVA, Interbank, Scotiabank y BN | Nuevo `al_l10n_pe_batch_payment` sobre `account_batch_payment` | Alto: tesorería semanal de cualquier empresa | 5-7 días | Práctica bancaria; los formatos ya están probados en `al_hr_pe_reports` (`hr_multipayment.py`) |
| Validez de comprobantes de proveedores en SUNAT | Nuevo `al_l10n_pe_cpe_validation` | Medio-alto: evita crédito fiscal con comprobantes de baja o inexistentes | 3-5 días | [SUNAT, servicios web](https://orientacion.sunat.gob.pe/node/811) |
| Resumen del 621 y pagos a cuenta del impuesto a la renta | Nuevo `al_l10n_pe_monthly_tax` (antes «`al_l10n_pe_income_tax_advance`») | Medio-alto: cierre tributario mensual | 4-5 días | [SUNAT, impuestos a pagar](https://orientacion.sunat.gob.pe/node/1114) |
| DUA como documento de compra (IGV, percepción y derechos aduaneros, costos en destino) | Nuevo `al_l10n_pe_import_dua` | Medio para importadores | 4-6 días | `l10n_pe_reports` solo enlaza la factura con la DUA |
| Extractos de bancos peruanos con ITF automático | Nuevo `al_l10n_pe_bank_statement_import` | Medio | 3-5 días | Sin formato oficial: cada banco publica el suyo |
| Origen de NC/ND emitidas sobre comprobantes que no están en Odoo | `al_l10n_pe_ple` (y `al_l10n_pe_sire`) | Medio: hoy esas notas salen sin referencia en el 14.1/RVIE | 1 día | Tabla 10 del PLE y estructura del RVIE (campos del comprobante modificado) |

### 2.2 Pendientes de baja prioridad en módulos existentes

| Qué | Módulo | Valor | Esfuerzo | Nota |
|---|---|---|---|---|
| Saldo no aplicado de retenciones y percepciones que se arrastra al mes siguiente en el 621 | `al_l10n_pe_retention`, `al_l10n_pe_perception` | Medio | Se resuelve dentro de `al_l10n_pe_monthly_tax` | Hoy hay resúmenes por periodo sin arrastre |
| Aviso (no bloqueo) de pagos con fecha futura | `al_account_payments` | Bajo | 0,2 días | Pendiente 8 de `analisis_pagos_v16.md` |
| Plazos de pago con monto fijo en moneda extranjera | `al_l10n_pe_currency` | Bajo | 1 día | Pendiente 9 de pagos; caso cubierto por la detracción |
| Importación de facturas de compra fuera del SIRE | — | Bajo | — | El SIRE es la fuente oficial; no se recomienda |
| Archivo `.ps4` de prestadores para la PLAME | `al_l10n_pe_fourth_category` | Bajo | — | Estructura no confirmada en fuente oficial |
| Notas de crédito sobre recibos por honorarios | `al_l10n_pe_fourth_category` | Bajo | 1 día | Poco frecuente; documentado |
| Arrastre del 621 de percepciones | `al_l10n_pe_perception` | Medio | Ver `al_l10n_pe_monthly_tax` | |
| Padrón descargable de agentes de percepción | `l10n_pe_vat_sunat` | — | — | SUNAT no lo publica; se marca desde la ficha RUC |
| TXT del PDT 621 | — | — | — | SUNAT declara con el formulario virtual 621 |
| CDR rechazado en el PLE | `al_l10n_pe_ple` | Bajo | 0,5 días | Pendiente conocido del módulo |
| Anticipos y operaciones gratuitas en la liquidación de compra | `al_l10n_pe_edi_purchase_settlement` | Bajo | 2 días | Fuera del alcance mínimo |

### 2.3 Riesgos de calidad (no son desarrollo)

| Riesgo | Dónde | Qué hace falta |
|---|---|---|
| XML del comprobante de percepción (40), liquidación de compra (04), reversión RR del CRE, código 62 en la factura y NC descontada en el CRE probados solo con simulación | `al_l10n_pe_perception`, `al_l10n_pe_edi_purchase_settlement`, `al_l10n_pe_retention`, `al_l10n_pe_invoice` | Envío al entorno beta de SUNAT o al OSE del cliente con su certificado |
| Encaminamiento IAP de resúmenes RR y del tipo 04 | Mismos | Una prueba real con IAP |
| API del SIRE sin probar contra SUNAT | `al_l10n_pe_sire` | Credenciales SOL del cliente |
| Ficha RUC completa: SUNAT bloquea IP extranjeras; Decolecta `ruc/full` según plan | `l10n_pe_vat_sunat` | Plan de Decolecta o servidor en el Perú |
| Planificador: criterios de MOMEN con datos reales (maestro, ETO, compras, contrato) | `al_construction_planner` | Datos del cliente (`docs/planificador/ACEPTACION.md`) |
| Culqi sin llaves de prueba del cliente | `al_payment_culqi` | Llaves `pk_test`/`sk_test` |

## 3. Recomendaciones para desarrollar ahora

Ordenadas por prioridad. Todas son genéricas para la localización, tienen
base normativa o uso diario y no dependen de datos o credenciales del cliente
para quedar terminadas y probadas (los envíos reales siguen la sección 2.3).

### R1. `al_l10n_pe_batch_payment` — pagos masivos a proveedores (OL-ACCOUNTING)
- **Alcance:** sobre `account.batch.payment` (Enterprise), archivo TXT por
  banco para pagos a proveedores: Telecrédito BCP, BBVA net cash, Interbank,
  Scotiabank y Banco de la Nación; cuenta y CCI del proveedor desde
  `res.partner.bank` (validación de CCI de 20 dígitos y del banco); pagos en
  soles y dólares por separado; neto después de retenciones y detracciones
  (no se paga la detracción por el banco comercial). Los formatos de
  `al_hr_pe_reports/models/hr_multipayment.py` se mueven a una librería común
  en este módulo y planillas la usa (sin cambiar sus archivos).
- **Depende de:** `account_batch_payment`, `al_account_payments`; planillas
  pasa a depender de él para los formatos.
- **Criterios de aceptación:** lote con 3 proveedores en dos bancos genera un
  archivo por banco con los totales y el número de registros correctos;
  rechaza proveedores sin cuenta o CCI inválido; los TXT de planillas siguen
  idénticos (pruebas existentes en verde); multicompañía.
- **Esfuerzo:** 5-7 días.

### R2. `al_l10n_pe_monthly_tax` — resumen del 621 y pagos a cuenta (OL-ACCOUNTING)
- **Alcance:** régimen tributario de la compañía (General, MYPE Tributario,
  Especial) con vigencia; pago a cuenta mensual del impuesto a la renta
  (coeficiente o porcentaje según régimen, con el coeficiente escrito por el
  usuario desde la declaración anual); resumen mensual del 621: IGV
  (débito y crédito desde los registros), retenciones sufridas, percepciones
  sufridas y su arrastre del saldo no aplicado, pago a cuenta de renta y
  saldo a favor del periodo anterior; asiento opcional del pago a cuenta.
- **Depende de:** `al_account_base`; usa `al_l10n_pe_retention` y
  `al_l10n_pe_perception` si están instalados.
- **Criterios de aceptación:** un mes con ventas, compras, una retención y una
  percepción sufridas cuadra con los registros; el saldo no aplicado pasa al
  mes siguiente; el pago a cuenta cambia según el régimen y el coeficiente.
- **Esfuerzo:** 4-5 días.

### R3. `al_l10n_pe_cpe_validation` — validez de comprobantes de proveedores (OL-ACCOUNTING)
- **Alcance:** consulta de validez del comprobante de compra en SUNAT por
  servicio web (credenciales de la API de consulta del contribuyente en
  Ajustes, como las del SIRE): estado (aceptado, anulado, no existe) en la
  factura de proveedor, consulta al publicar (opcional) y en lote desde la
  lista, aviso o bloqueo configurable para comprobantes no válidos.
- **Depende de:** `l10n_pe`, `l10n_pe_vat_sunat` (conexiones).
- **Criterios de aceptación:** con respuestas simuladas, cada estado se
  refleja en la factura; el lote procesa 100 comprobantes en una sola acción;
  sin credenciales avisa sin romper el registro.
- **Esfuerzo:** 3-5 días (la prueba real requiere credenciales del cliente).

### R4. `al_l10n_pe_import_dua` — DUA y costos de importación (OL-ACCOUNTING)
- **Alcance:** DUA (tipo 50) como documento de compra con IGV, percepción y
  derechos aduaneros; enlace con la factura comercial y con la recepción;
  costos en destino (`stock_landed_costs`) desde la DUA y los gastos de
  aduana; su lugar en el registro de compras (SIRE/PLE) sin duplicar la
  factura del exterior (no domiciliado).
- **Depende de:** `l10n_pe_reports`, `stock_landed_costs`,
  `al_l10n_pe_sire`, `al_l10n_pe_perception` (percepción aduanera).
- **Criterios de aceptación:** una importación con factura del exterior, DUA
  y dos gastos reparte el costo en el producto; el IGV de la DUA entra al
  crédito fiscal; la percepción aduanera queda registrada.
- **Esfuerzo:** 4-6 días.

### R5. `al_l10n_pe_ple` — origen de NC/ND fuera de Odoo y CDR rechazado
- **Alcance:** campos del comprobante modificado (tipo, serie, número y
  fecha) escribibles en la nota cuando el original no está en Odoo, usados
  por el PLE 14.1/8.1 y el SIRE; excluir del registro los comprobantes con
  CDR rechazado.
- **Criterios de aceptación:** una NC sobre una factura de 2024 sin registro
  en Odoo sale en el TXT con su referencia; un comprobante rechazado no sale.
- **Esfuerzo:** 1-1,5 días.

### R6. Ajustes rápidos
- `al_account_payments`: aviso (no bloqueo) de pago con fecha futura (0,2 días).

## 4. Lo que no se recomienda desarrollar ahora

| Qué | Por qué |
|---|---|
| `al_l10n_pe_bank_statement_import` | Sin formato oficial: cada banco publica el suyo y cambia; la importación CSV/Excel con mapeo de Odoo 19 ya cubre la carga. Desarrollarlo sin archivos reales del cliente sería adivinar. Se retoma con archivos de muestra |
| TXT del PDT 621 | SUNAT declara con el formulario virtual 621 |
| Archivo `.ps4` | Estructura no confirmada en fuente oficial |
| Padrón de agentes de percepción descargable | SUNAT no lo publica |
| DAOT | Quien lleva registros electrónicos solo presenta la constancia |
| Importación de compras fuera del SIRE | El SIRE es la fuente oficial |
| Créditos de clientes con aprobación por niveles | Se cubre con el límite de crédito nativo y `base_tier_validation`; específico del cliente |
| Plazos en monto fijo en moneda extranjera | Caso marginal cubierto por la detracción |
| Validación real con SUNAT/OSE, SIRE, Decolecta, Culqi, criterios de MOMEN | Requieren credenciales, certificados o datos del cliente (sección 2.3) |

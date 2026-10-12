# Pruebas automáticas en una base nueva con datos de demostración

**Base:** `test_pe_demo` (nueva, con demo) · **Configuración:** `cfg/my/pe.cfg` · **Odoo:** 19.0 CE + EE
**Fecha:** 12/10/2026 · **Objetivo:** que toda la suite propia pase en una base recién creada con
datos de demostración y en una empresa nueva, no solo en la base de desarrollo `ol_pe_v19`.

---

## 1. Creación de la base

```bash
cd /home/och/odoo/ce19
MODS="l10n_pe,$(paste -sd, <lista de módulos>)"
flock /tmp/claude-1000/odoo_test_pe_demo.lock .venv/bin/python odoo-bin -c cfg/my/pe.cfg \
  -d test_pe_demo --db-filter='^test_pe_demo$' --with-demo -i "$MODS" \
  --stop-after-init --workers=0 --http-port=19821 --gevent-port=19822 --max-cron-threads=0

# Ajuste de la base de pruebas (ver § 4.1)
psql -h localhost -U odoo -d postgres -c "ALTER DATABASE test_pe_demo SET enable_nestloop = off"
```

En Odoo 19 la demo ya no se carga por defecto: hace falta `--with-demo`.

Compañías de la base:

| Id | Compañía | Plan | Moneda | Nota |
|---:|---|---|---|---|
| 1 | My Company (San Francisco) | genérico | USD | es `env.company` en las pruebas |
| 2 | My US Company | EE. UU. | USD | |
| 3 | My Company (Chicago) | genérico | USD | |
| 4 | PE Company (`base.demo_company_pe`) | `pe` | PEN | la usan las pruebas de la localización |

### Módulos instalados (57 + `l10n_pe`)

| Área | Módulos |
|---|---|
| OL-ACCOUNTING (26) | al_account_base, al_account_destinations, al_account_move_name_sequence, al_account_payments, al_l10n_pe_account_letter, al_l10n_pe_batch_payment, al_l10n_pe_cash_fund, al_l10n_pe_cpe_validation, al_l10n_pe_currency, al_l10n_pe_detraction, al_l10n_pe_exchange_closure, al_l10n_pe_factoring, al_l10n_pe_financial_reports, al_l10n_pe_fourth_category, al_l10n_pe_import_dua, al_l10n_pe_lease, al_l10n_pe_monthly_tax, al_l10n_pe_multicurrency_revaluation, al_l10n_pe_perception, al_l10n_pe_ple, al_l10n_pe_retention, al_l10n_pe_sire, al_l10n_pe_term_deposit, al_payment_culqi, al_payment_niubiz, l10n_pe_vat_sunat |
| OL-INVOICING (6) | al_l10n_pe_complaints_book, al_l10n_pe_delivery_guide_report, al_l10n_pe_edi_downpayment_discount, al_l10n_pe_edi_purchase_settlement, al_l10n_pe_invoice, al_ose_factory_hka |
| OL-PAYROLL (8) | al_hr_pe, al_hr_pe_account, al_hr_pe_attendance, al_hr_pe_benefits, al_hr_pe_construction, al_hr_pe_import, al_hr_pe_public_holidays, al_hr_pe_reports |
| OL-POS (4) | al_l10n_pe_edi_pos, al_pos_product_view, al_pos_theme, al_pos_vendedor |
| OL-INVENTORY (3) | al_l10n_pe_stock_transfer, al_stock_base, ol_stock_kardex_pe |
| OL-PROJECTS (6) | al_construction_material_request, al_construction_planner, al_project_gantt_ai, al_project_gantt_backend, al_project_gantt_base, al_project_gantt_website |
| OL-TOOLS (4) | al_base_module_info, al_docs_help, al_mcp_server, al_report_base |

Excluidos: `ol_licencia_perpetua` (por indicación), `al_pos_network_printer` (requiere la librería
`python-escpos`, no instalada en el venv). `purchase_request` entra como dependencia.

## 2. Ejecución de las pruebas

Por lotes, con `-u` (las pruebas `at_install` solo corren al actualizar el módulo) y un vigilante
que corta el proceso si el log no avanza en 15 minutos:

```bash
.venv/bin/python odoo-bin -c cfg/my/pe.cfg -d test_pe_demo --db-filter='^test_pe_demo$' \
  -u "$LOTE" --test-enable --test-tags "/mod1,/mod2,…" --stop-after-init --workers=0 \
  --http-port=19821 --gevent-port=19822 --max-cron-threads=0
```

- Lote 1: OL-ACCOUNTING + OL-INVOICING (32 módulos).
- Lote 2: OL-PAYROLL, OL-POS, OL-INVENTORY, OL-PROJECTS y OL-TOOLS (25 módulos).

## 3. Resultado

| Lote | Tests | Fallos | Estado |
|---|---|---|---|
| 1 (repetición, 25 módulos) | 730 | 0 | verde |
| 2 | 1011 | 2 | corregidos (ver §4) |
| 3 | 414 | 1 | corregido; `al_l10n_pe_ple` repetido: 121 tests, 0 fallos |
| **Total** | **2155** | **3** | **todos corregidos** |

Todos los módulos de la suite pasan sus pruebas en una compañía peruana nueva, con los datos de demostración cargados.

## 4. Fallos encontrados, por causa

### 4.1 Cuelgues

| Síntoma | Causa | Corrección |
|---|---|---|
| El proceso quedó 3 h parado tras `al_hr_pe_reports` («Request timed out») | `TestVoucherEncrypt` renderiza el PDF de verdad (`force_report_rendering`); wkhtmltopdf pide los estilos a `report.url`/`web.base.url` y en una base nueva nadie responde ahí | La prueba apunta `report.url` a un puerto cerrado (`http://127.0.0.1:9`): falla al instante y el PDF se genera igual |
| Una consulta sobre `account_account` activa durante más de 15 min en el `setUpClass` de `AccountTestInvoicingCommon` (primero en `al_account_move_name_sequence`, luego en `al_l10n_pe_ple`) | Con solo 4 compañías, la lista de valores frecuentes de `account_account_res_company_rel.res_company_id` las cubre todas y PostgreSQL estima **1 fila** para una compañía nueva, que en realidad tiene unas 1236 cuentas dentro de la transacción de la prueba. Elige bucles anidados cuadráticos o cúbicos (reproducido con `EXPLAIN`). `ANALYZE` no lo corrige, porque las filas nuevas no están confirmadas. En `ol_pe_v19`, con más compañías, la estimación no cae a 1. | Ajuste solo de la base de pruebas: `ALTER DATABASE test_pe_demo SET enable_nestloop = off` (el planificador pasa a uniones *merge*/*hash*). No es un defecto del código: la búsqueda es la de `collect_company_accounting_data` de Odoo. |
| `could not serialize access due to concurrent update` al arrancar | Otro servidor de desarrollo sin `--db-filter` ejecuta sus crons también sobre `test_pe_demo` | Reintentar; o arrancar ese servidor con `--db-filter` |

### 4.2 Defectos reales del código

| Módulo | Fallo | Corrección | Versión |
|---|---|---|---|
| l10n_pe_vat_sunat | La instalación con demo abortaba: `l10n_us_hr_payroll` (se instala solo) carga ciudades de EE. UU. homónimas y chocaba con la restricción SQL global de ciudad única | La unicidad (nombre + departamento) se valida solo en Perú (`@api.constrains`); una migración elimina la restricción SQL; prueba nueva `test_res_city` | 20.20261012 |
| al_construction_material_request | Actualizar el módulo en una base con demo fallaba: el XML demo reescribía los `stock.quant` ya aplicados («Quant's editing is restricted») | El archivo demo es `noupdate="1"` | 11.20261012 |

### 4.3 Pruebas que dependían de la base de desarrollo

La causa común es que en `ol_pe_v19` la compañía activa ya es peruana. En una base demo,
`env.company` es la compañía de EE. UU. (USD, plan genérico): no hay IGV del 18 %, cuentas PCGE,
diarios ni tipos de documento, y la moneda extranjera es el sol.

**Corrección general:** el ayudante nuevo `al_account_base/tests/common.py::use_pe_company(cls)`, que
se llama al inicio de `setUpClass`:

- Si la compañía del usuario ya tiene el plan `pe` (caso `ol_pe_v19`), no hace nada.
- Si no, usa `base.demo_company_pe` o crea una compañía con el plan de Perú.
- Cambia la compañía **del usuario**, no el contexto, igual que `BaseCommon` de Odoo. Con
  `allowed_company_ids` en el contexto, los `with_user()` de las pruebas multicompañía daban
  `AccessError`.
- Le crea un almacén si no lo tiene. La compañía demo de l10n_pe se crea antes que inventario, y
  Odoo solo da almacén a la primera compañía: sin almacén no hay tipos de operación.

Se aplica en: al_account_destinations, al_account_payments, al_l10n_pe_cash_fund, l10n_pe_vat_sunat,
al_l10n_pe_batch_payment, al_l10n_pe_edi_purchase_settlement, al_l10n_pe_retention, al_l10n_pe_sire,
al_l10n_pe_detraction, al_l10n_pe_lease, al_l10n_pe_term_deposit, al_l10n_pe_import_dua,
al_l10n_pe_factoring, al_l10n_pe_currency, al_l10n_pe_delivery_guide_report y al_l10n_pe_ple. Las
clases sobre `AccountTestInvoicingCommon` ya crean su propia compañía y no lo necesitan.

Ajustes puntuales:

| Prueba | Causa | Corrección |
|---|---|---|
| al_construction_material_request `test_full_flow_purchase_via_central` | Esperaba `40,00` (formato es_PE) | Compara con `formatLang(env, 40.0)` |
| al_construction_planner `test_income_calendar` | Esperaba `28/12/2026` (formato es_PE) | Compara con `format_date(env, date(2026, 12, 28))` |
| al_hr_pe_import `test_04_boleta_datos_y_qweb` | Buscaba «Neto a pagar»; la plantilla del formato común dice «NETO A PAGAR» | Compara sin distinguir mayúsculas |
| al_construction_material_request `test_demo_data_100_bags_with_60_available` | Recargaba el XML demo ya cargado, y el setUp desactiva los niveles de aprobación demo | Solo carga el XML si falta; si ya estaba, reactiva los niveles demo |
| al_l10n_pe_delivery_guide_report `test_print_action_targets_own_report` | Sin diseño de documento en la compañía, `report_action` abre antes el asistente de configuración | La prueba fija `external_report_layout_id` |
| al_l10n_pe_retention (menú y número de pago) | En Odoo 19 un pago sin cuenta de pagos pendientes no genera asiento ni concilia; en `ol_pe_v19` estaba configurada a mano | El `setUpClass` asigna una cuenta de pagos pendientes a las líneas de método de pago que no la tienen |
| al_l10n_pe_sire `test_exchange_rates_need_foreign_currency` | Daba por hecho que había ventas del periodo en la base | Crea una venta en soles antes de desplegar las líneas |
| l10n_pe_vat_sunat `test_security_padron` | El `import` del ayudante quedó dentro de un `import (...)` de varias líneas (SyntaxError) | Corregido |

## 5. Datos de demostración

Quince módulos traen ahora datos en la clave `demo` del manifiesto. Solo se cargan en bases con
demostración, en «PE Company» (`base.demo_company_pe`), y se omiten si esa compañía no existe o no
tiene el plan `pe`.

- **Mecanismo:** cada módulo amplía el modelo abstracto `al.pe.demo` (de `al_account_base`) con
  un método `_load_demo_<módulo>`, que su XML demo llama mediante `_demo_load`.
- **Carga segura:** `_demo_load` ejecuta cada ejemplo en su propio punto de guardado. Si uno
  falla, se deshace ese ejemplo, se avisa en el log y la instalación sigue.
- **Sin envíos:** los diarios de venta y compra demo no usan documentos electrónicos, así que
  nada se envía a SUNAT ni al OSE.

Registros comprobados en `test_pe_demo`:

| Módulo | Qué carga |
|---|---|
| al_l10n_pe_account_letter | Canje de cliente CLC00121 en 3 letras (393.33 + 393.33 + 393.34) y de proveedor CLP00122 en 2 letras (1,180.00 c/u), cobradas/pagadas |
| al_l10n_pe_batch_payment | Bancos BCP, BBVA e Interbank con su formato, diario «DEMO BCP soles» y lote enviado de 3 pagos (6,860.75) |
| al_l10n_pe_cpe_validation | Tres comprobantes consultados: válido, observado y no válido |
| al_l10n_pe_detraction | Factura con detracción de 708.00, depósito DEMO-2026-0001 |
| al_l10n_pe_exchange_closure | Cierre de agosto publicado (126.00) y de septiembre calculado (−141.00) |
| al_l10n_pe_factoring | Dos operaciones desembolsadas (18,050.00 y 12,350.00) y una en borrador |
| al_l10n_pe_fourth_category | Tres recibos por honorarios: con retención (160.00), bajo el mínimo y con suspensión |
| al_l10n_pe_import_dua | Importación de diez motobombas: recepción, factura del exterior, agente de aduana y DAM publicada con costo en destino |
| al_l10n_pe_lease | Cuatro contratos: dos en curso, uno exento y uno en borrador |
| al_l10n_pe_monthly_tax | Declaración 621 de 09/2026 calculada |
| al_l10n_pe_perception | Agente de percepción con tres ventas (dos cobradas con su comprobante) y dos percepciones sufridas (proveedor y DAM) |
| al_l10n_pe_retention | Pago con su CRE R001-00000001 (2,360.00) y una retención sufrida (106.20) |
| al_l10n_pe_term_deposit | Cuatro depósitos a plazo abiertos con sus intereses devengados |
| al_l10n_pe_stock_transfer | Cuatro traslados hechos con su motivo SUNAT (04, 02 y 06) |
| al_l10n_pe_edi_purchase_settlement | Liquidación de compra L001-00000001 publicada (11,696.87) |

`al_construction_material_request` y `al_construction_planner` ya traían demo. Se comprobó que carga
bien: 263 registros de requerimiento y 2 obras planificadas.

Además, `al_l10n_pe_lease` rellena ahora por defecto el tipo de activo de la tabla 18 al crear el
activo. Sin él, la exportación del PLE 7.1 fallaba.

## 6. Compatibilidad con `ol_pe_v19`

Los tests modificados se ejecutaron también en `ol_pe_v19`, con un lock y un puerto propios:

| Lote | Tests | Fallos |
|---|---|---|
| Módulos con tests modificados (1) | 783 | 0 |
| Módulos con tests modificados (2) | 499 | 0 |

En `ol_pe_v19` la compañía ya es peruana, así que `use_pe_company` no cambia nada y los tests siguen pasando como antes.

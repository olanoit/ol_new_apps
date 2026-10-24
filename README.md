ol_new_apps
===========

Suite de módulos AL para **Odoo 19** (Community y Enterprise): localización
peruana (contabilidad, tributación, facturación electrónica y planillas),
punto de venta, inventario, proyectos y obras, y herramientas transversales.
Autor: CRISTÓBAL OCH — [altabpo.com](https://www.altabpo.com).

Los módulos están organizados por **área de negocio** (una carpeta
`OL-<ÁREA>` en mayúscula por área), más `OL-THIRD-PARTY/` para las dependencias de otros autores
que se distribuyen con el repositorio.

Áreas del repositorio
---------------------

Cada carpeta tiene su propio `README.md` con qué va y qué no va en ella, y la
tabla de los módulos que contiene.

área | para qué es
--- | ---
[OL-ACCOUNTING](OL-ACCOUNTING/) | App Perú, contabilidad y tributación: tipo de cambio, detracciones, retenciones, PLE, SIRE, estados financieros.
[OL-INVOICING](OL-INVOICING/) | Representaciones impresas y documentos electrónicos: factura, boleta y guía de remisión.
[OL-PAYROLL](OL-PAYROLL/) | Nómina peruana: régimen general y construcción civil, beneficios sociales, asistencia, reportes.
[OL-POS](OL-POS/) | Punto de venta: comprobantes electrónicos desde la caja, vendedor, catálogo, tema y marca blanca.
[OL-INVENTORY](OL-INVENTORY/) | Inventario y existencias: kárdex valorizado.
[OL-PROJECTS](OL-PROJECTS/) | Proyectos y obras: Gantt y requerimientos de materiales de obra.
[OL-INDUSTRIES](OL-INDUSTRIES/) | Paquetes por industria (farmacia, construcción, mobiliario, bodega, restaurante, tienda en línea): instalan y configuran los módulos del rubro.
[OL-HEALTH](OL-HEALTH/) | Salud: suite de farmacias y boticas (presentaciones, receta, buenas prácticas, controlados y DIGEMID).
[OL-TOOLS](OL-TOOLS/) | Utilidades transversales: información de módulos, servidor MCP, licencia.
[OL-THIRD-PARTY](OL-THIRD-PARTY/) | Módulos de otros autores que usa el proyecto, con su autoría y licencia; los cambios locales, anotados en su CHANGELOG.

Documentación
-------------

La documentación sigue el modelo de la de Odoo
([odoo/documentation](https://github.com/odoo/documentation)) y se publica en
[docs.altalatam.com](https://docs.altalatam.com):

- **Documentación para usuarios** (`mkdocs/content/applications/`): cómo
  configurar y usar cada funcionalidad, por área de negocio (Finanzas, Ventas,
  Cadena de suministro, Recursos humanos, Servicios, Ajustes generales).
- **Instalación y mantenimiento**, **Desarrollador** y **Aportando** (pautas
  para escribir una página).
- La referencia técnica de cada módulo, las especificaciones de `docs/` y las
  novedades se generan solas desde el repositorio.

Los módulos no guardan su documentación funcional: su `README.md` enlaza a su
página. Cada página declara los módulos que documenta (`modulos:`), y de ahí
salen la referencia técnica y el botón **?** de Odoo (`al_docs_help`). Uso,
versionado y publicación: [`mkdocs/README.md`](mkdocs/README.md).

```bash
/home/och/odoo/ce19/.venv/bin/mkdocs serve -f mkdocs/mkdocs.yml   # http://127.0.0.1:8000
```

Instalación: addons_path
------------------------

La raíz del repositorio **no** contiene módulos: cada área debe estar en el
`addons_path` del servidor. Para obtener las rutas de un servidor:

```bash
python3 scripts/addons_path.py /ruta/del/clon/ol_new_apps
```

En este entorno (`cfg/my/pe.cfg` y `cfg/my/funcional.cfg`):

```ini
addons_path = ...,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-ACCOUNTING,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-INVOICING,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-PAYROLL,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-POS,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-INVENTORY,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-PROJECTS,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-INDUSTRIES,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-HEALTH,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-TOOLS,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-THIRD-PARTY
```

En Odoo.sh y en los servidores donde `ol_new_apps` es un submódulo (por
ejemplo `democonstruccion` o `newallcenter-dev`) hay que añadir las mismas
diez carpetas al `addons_path`; con solo la raíz, Odoo no encuentra los
módulos.

Estructura
----------

```
OL-ACCOUNTING/ … OL-THIRD-PARTY/   módulos, agrupados por área
docs/                       especificaciones y planes de desarrollo, fichas
                            (generador y capturas), validaciones y datos de prueba
mkdocs/                     documentación (MkDocs + Material, modelo de Odoo):
                            content/ escrito a mano y lo generado desde lo anterior
scripts/                    utilidades del repositorio (ver abajo)
```

Scripts
-------

script | para qué
--- | ---
`scripts/gen_addons_table.py` | Regenera las tablas «Módulos disponibles» de este README y de cada área desde los manifiestos. Con `--check` solo comprueba (y avisa de módulos fuera de un área).
`scripts/addons_path.py` | Imprime las rutas de las áreas para el `addons_path` de un servidor.
`scripts/gen_changelog.py` | Genera el `CHANGELOG.md` de cada módulo desde las `novedades` de su ficha (`docs/fichas/<módulo>.yml`). Con `--check` solo comprueba.
`scripts/areas.py` | Lista de áreas: añadir aquí un área nueva (`OL-<ÁREA>`, en mayúscula) antes de crear su carpeta.
`docs/fichas/generar_fichas.py` | Genera la ficha `static/description/index.html` de cada módulo desde `docs/fichas/<módulo>.yml`.
`docs/validacion/fichas_modulos.py` | Valida las fichas (ASCII, enlace a la ficha completa, pie con versión y licencia).
`docs/validacion/generar_es_po.py` | Genera `i18n/es.po` de un módulo con modelos nuevos (etiquetas heredadas de los mixins).

Convenciones
------------

- **Nombre técnico** con prefijo `al_` (o `l10n_pe_`, `ol_` en módulos
  heredados); un módulo nuevo va en la carpeta de su área.
- **Categoría** del manifiesto: `'<carpeta del área>/Apps'`, por ejemplo
  `'OL-INVENTORY/Apps'` para un módulo de `OL-INVENTORY/`. La subcategoría
  `Apps` hace falta para que el área aparezca en el panel de Aplicaciones:
  Odoo solo lista una categoría raíz si tiene una subcategoría con módulos o
  algún módulo marcado como aplicación. Si el módulo cambia de área, la
  categoría cambia con él. `gen_addons_table.py --check` lo verifica; quedan
  fuera `OL-THIRD-PARTY/` y los módulos con `'Hidden'`.
- **Versión** `N.AAAAMMDD`: contador de versión y fecha.
- **CHANGELOG.md** en cada módulo, una entrada por versión. Se genera desde
  las `novedades` de la ficha con `scripts/gen_changelog.py`; solo los módulos
  sin ficha (terceros y algunas utilidades) lo mantienen a mano.
- **Licencia** OPL-1 en todos los módulos propios. Excepciones, en
  `scripts/areas.py` con su motivo: `al_construction_material_request`
  (LGPL-3, extiende `base_tier_validation`, que es AGPL-3). Los de
  `OL-THIRD-PARTY/` conservan la de su autor.
- **LICENSE** en cada módulo, con el texto de la licencia de su manifiesto.
  `gen_addons_table.py --check` verifica la licencia y los dos archivos.
- **Idioma**: textos de origen en español, con solo la primera letra en
  mayúscula; comentarios también en español.
- **Ficha** del módulo generada desde `docs/fichas/<módulo>.yml`, nunca
  editada a mano.
- **Tests** en la base `ol_pe_v19` (`cfg/my/pe.cfg`).

Módulos disponibles
-------------------

Todos los módulos del repositorio, agrupados por área (la misma tabla que en
el `README.md` de cada área). Se regenera con:

```bash
python3 scripts/gen_addons_table.py
```

[//]: # (addons-all)
### OL-ACCOUNTING

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_account_base](OL-ACCOUNTING/al_account_base/) | 18.20261013 | OPL-1 | Personalizaciones genéricas de la localización contable peruana: glosa en asientos/líneas, menú "Perú" y utilidades compartidas.
[al_account_destinations](OL-ACCOUNTING/al_account_destinations/) | 12.20261012 | OPL-1 | Genera automáticamente el asiento de destino (clase 6 a 9 o viceversa) según los porcentajes configurados por cuenta.
[al_account_move_name_sequence](OL-ACCOUNTING/al_account_move_name_sequence/) | 13.20261008 | OPL-1 | Secuencia ir.sequence OPCIONAL por diario para controlar la numeración (serie-correlativo SUNAT) de los comprobantes.
[al_account_payments](OL-ACCOUNTING/al_account_payments/) | 10.20261012 | OPL-1 | Medio de pago SUNAT (catálogo 1) y número de operación bancaria en pagos y en el asistente de registro de pagos.
[al_l10n_pe_account_letter](OL-ACCOUNTING/al_l10n_pe_account_letter/) | 22.20261018 | OPL-1 | Canje, refinanciación y gestión de letras de cambio para clientes y proveedores (Perú).
[al_l10n_pe_bank_collection](OL-ACCOUNTING/al_l10n_pe_bank_collection/) | 7.20261022 | OPL-1 | Recaudación por ventanilla, agentes y banca por internet: archivo de deudores para el banco, importación de la respuesta, pagos y conciliación automática. Formatos BCP (CREP), BBVA y Scotiabank incluidos y configurables.
[al_l10n_pe_bank_statement_import](OL-ACCOUNTING/al_l10n_pe_bank_statement_import/) | 1.20261021 | OPL-1 | Importa los extractos que descargan los bancos peruanos (Excel, Excel en HTML, CSV o TXT) sin mapear columnas: reconoce la tabla por sus encabezados.
[al_l10n_pe_batch_payment](OL-ACCOUNTING/al_l10n_pe_batch_payment/) | 5.20261018 | OPL-1 | Lotes de pago a proveedores con el archivo TXT de BCP, BBVA, Interbank, Scotiabank y Banco de la Nación: cuenta o CCI del proveedor, controles y totales del archivo.
[al_l10n_pe_cash_closing](OL-ACCOUNTING/al_l10n_pe_cash_closing/) | 1.20261021 | OPL-1 | Cierre diario de cada caja: saldo según libros, cobros y pagos por medio de pago, arqueo por denominación, asiento del faltante o sobrante y bloqueo del día cerrado.
[al_l10n_pe_cash_forecast](OL-ACCOUNTING/al_l10n_pe_cash_forecast/) | 1.20261021 | OPL-1 | Proyección de cobros y pagos por semana o mes desde los saldos de bancos, las cuentas por cobrar y por pagar, cheques, depósitos a plazo y partidas manuales, con escenario editable y comparación con lo real.
[al_l10n_pe_cash_fund](OL-ACCOUNTING/al_l10n_pe_cash_fund/) | 2.20261012 | OPL-1 | Entregas a rendir y cajas chicas a cargo de un responsable: aprobación, entrega, rendición con comprobantes y planilla de movilidad, devolución, reembolso o reposición, con sus asientos.
[al_l10n_pe_check](OL-ACCOUNTING/al_l10n_pe_check/) | 2.20261018 | OPL-1 | Cartera de cheques de terceros y cheques propios sobre el módulo nativo de Odoo: diarios y cuentas del PCGE, emisor con RUC o DNI y plazo de presentación de la Ley de Títulos Valores.
[al_l10n_pe_check_printing](OL-ACCOUNTING/al_l10n_pe_check_printing/) | 1.20261021 | OPL-1 | Imprime los cheques propios sobre la hoja de la chequera del banco, con un formato calibrable por diario: fecha, beneficiario e importe en números y en letras.
[al_l10n_pe_collection](OL-ACCOUNTING/al_l10n_pe_collection/) | 11.20261022 | OPL-1 | Gestión de cobranza: cartera por gestor, gestiones, compromisos de pago, reclamos, cobranza judicial, calificación de riesgo, bloqueo de crédito, intereses, provisión de cobranza dudosa, centrales de riesgo, proyección, metas y estado de cuenta.
[al_l10n_pe_collection_sale](OL-ACCOUNTING/al_l10n_pe_collection_sale/) | 1.20261022 | OPL-1 | No deja confirmar pedidos de venta de clientes con bloqueo de crédito por mora y lo advierte en el pedido.
[al_l10n_pe_cpe_validation](OL-ACCOUNTING/al_l10n_pe_cpe_validation/) | 3.20261018 | OPL-1 | Consulta integrada de comprobantes de pago de SUNAT para las facturas de proveedor: de una en una, en lote o al publicar, con aviso o bloqueo.
[al_l10n_pe_currency](OL-ACCOUNTING/al_l10n_pe_currency/) | 15.20261012 | OPL-1 | Tipo de cambio SUNAT (compra/venta) para USD/PEN desde cuatro fuentes —SUNAT, BCRP, Decolecta y apis.net.pe—, con actualización diaria, registro manual coherente y visualización del T.C. aplicado en facturas en moneda extranjera.
[al_l10n_pe_dashboard](OL-ACCOUNTING/al_l10n_pe_dashboard/) | 1.20261021 | OPL-1 | Tablero de la app Perú: ventas, compras e IGV, comprobantes electrónicos, detracciones, retenciones, percepciones, tesorería y declaraciones.
[al_l10n_pe_detraction](OL-ACCOUNTING/al_l10n_pe_detraction/) | 25.20261018 | OPL-1 | Detracciones SUNAT (SPOT): catálogo 54 administrable con porcentajes y montos mínimos, cálculo automático en facturas, depósito/constancia y enlace con el PLE 8.1.
[al_l10n_pe_exchange_closure](OL-ACCOUNTING/al_l10n_pe_exchange_closure/) | 12.20261018 | OPL-1 | Ajuste mensual por diferencia de cambio de las partidas monetarias en moneda extranjera: T.C. compra para activos y T.C. venta para pasivos (art. 61 LIR / art. 34 Reglamento).
[al_l10n_pe_factoring](OL-ACCOUNTING/al_l10n_pe_factoring/) | 10.20261018 | OPL-1 | Cesión de facturas a un factor con y sin recurso: asientos de cesión, desembolso, devengo de intereses, cobro del factor y recompra, con cuentas del PCGE configurables.
[al_l10n_pe_financial_reports](OL-ACCOUNTING/al_l10n_pe_financial_reports/) | 3.20261012 | OPL-1 | Estados financieros peruanos sobre el motor de informes de Odoo: 3.19 Estado de Cambios en el Patrimonio Neto, junto al Balance y el Estado de resultados, en la app Perú.
[al_l10n_pe_fourth_category](OL-ACCOUNTING/al_l10n_pe_fourth_category/) | 4.20261018 | OPL-1 | Recibos por honorarios: retención del 8 % sobre el tope, suspensión (Formulario 1609), reporte y archivo .4ta para la PLAME y certificado anual.
[al_l10n_pe_import_dua](OL-ACCOUNTING/al_l10n_pe_import_dua/) | 4.20261018 | OPL-1 | La DUA (tipo 50) como documento de compra: IGV e IPM con crédito fiscal, derechos aduaneros, percepción aduanera y costos en destino del producto.
[al_l10n_pe_itf](OL-ACCOUNTING/al_l10n_pe_itf/) | 1.20261021 | OPL-1 | Impuesto a las Transacciones Financieras (0,005 %) registrado al confirmar los pagos y cobros de los diarios bancarios afectos.
[al_l10n_pe_lease](OL-ACCOUNTING/al_l10n_pe_lease/) | 5.20261018 | OPL-1 | Contratos de alquiler como arrendatario según NIIF 16: pasivo a valor presente, derecho de uso con su depreciación, cuotas del arrendador, remedición, terminación anticipada, contratos en dólares e impuesto diferido.
[al_l10n_pe_monthly_tax](OL-ACCOUNTING/al_l10n_pe_monthly_tax/) | 4.20261021 | OPL-1 | Régimen tributario, pago a cuenta del impuesto a la renta y resumen del Formulario Virtual 621 con saldo a favor, percepciones y retenciones.
[al_l10n_pe_multicurrency_revaluation](OL-ACCOUNTING/al_l10n_pe_multicurrency_revaluation/) | 6.20261012 | OPL-1 | Revalúa cada cuenta con el tipo de cambio SUNAT de compra o de venta en el informe de ganancias/pérdidas de moneda no realizadas, y muestra el T.C. aplicado en cada línea.
[al_l10n_pe_payment_application](OL-ACCOUNTING/al_l10n_pe_payment_application/) | 2.20261021 | OPL-1 | Anticipos de clientes (122) y a proveedores (422) como pagos, su aplicación a facturas, compensaciones entre cuentas por cobrar y por pagar y control de anticipos pendientes.
[al_l10n_pe_payment_multi](OL-ACCOUNTING/al_l10n_pe_payment_multi/) | 2.20261021 | OPL-1 | Un solo pago o cobro bancario que cancela documentos de varios socios, entrega anticipos y registra otros pagos sin comprobante.
[al_l10n_pe_payment_receipt](OL-ACCOUNTING/al_l10n_pe_payment_receipt/) | 2.20261021 | OPL-1 | Recibo de ingreso y comprobante de egreso numerados con serie propia por diario, con el detalle de lo pagado, el monto en letras y las firmas.
[al_l10n_pe_payment_term_currency](OL-ACCOUNTING/al_l10n_pe_payment_term_currency/) | 1.20261021 | OPL-1 | Plazos de pago con cuotas de importe fijo en soles que se convierten al tipo de cambio de la factura cuando esta es en dólares u otra moneda.
[al_l10n_pe_perception](OL-ACCOUNTING/al_l10n_pe_perception/) | 4.20261018 | OPL-1 | Régimen de percepciones del IGV: comprobante de percepción electrónico (tipo 40) como agente, percepciones que nos cobran para el F.V. 621 y resumen del F.V. 697.
[al_l10n_pe_ple](OL-ACCOUNTING/al_l10n_pe_ple/) | 26.20261012 | OPL-1 | Completa los libros electrónicos PLE de SUNAT no cubiertos por la localización oficial: Libro 7 (Activos Fijos), 4.1 (Retenciones LIR), 9.1/9.2 (Consignaciones), complementos del Libro 3 (3.8/3.9/3.19/3.23), Libro 10 (Costos) y formatos simplificados (5.2/5.4, 8.3, 14.2). Corrige además el RCE 8.4 y 8.5 del SIRE.
[al_l10n_pe_retention](OL-ACCOUNTING/al_l10n_pe_retention/) | 24.20261018 | OPL-1 | Régimen de Retenciones del IGV (R.S. 037-2002/SUNAT): agente de retención, aplicabilidad con excepciones y retención del 3% en el pago sobre el marco nativo.
[al_l10n_pe_sire](OL-ACCOUNTING/al_l10n_pe_sire/) | 22.20261012 | OPL-1 | Conciliación con el Sistema Integrado de Registros Electrónicos de SUNAT
[al_l10n_pe_term_deposit](OL-ACCOUNTING/al_l10n_pe_term_deposit/) | 5.20261018 | OPL-1 | Depósitos a plazo, fondos en garantía y depósitos en garantía entregados: apertura, devengo mensual de intereses (TEA), vencimiento, cancelación, renovación y liberación con sus asientos.
[al_payment_culqi](OL-ACCOUNTING/al_payment_culqi/) | 2.20261018 | OPL-1 | Culqi como proveedor de pago de Odoo: tarjetas y Yape con Checkout Custom, autenticación 3DS y devoluciones totales o parciales.
[al_payment_izipay](OL-ACCOUNTING/al_payment_izipay/) | 2.20261018 | OPL-1 | Izipay como proveedor de pago de Odoo: formulario emergente de Izipay con tarjetas y cuotas, confirmación por IPN firmada, anulaciones y devoluciones.
[al_payment_niubiz](OL-ACCOUNTING/al_payment_niubiz/) | 3.20261018 | OPL-1 | Niubiz Checkout All-In-One como proveedor de pago: tarjetas, Yape, Plin, Cuotéalo BCP y PagoEfectivo, con anulación y devoluciones.
[al_payment_pagoefectivo](OL-ACCOUNTING/al_payment_pagoefectivo/) | 1.20261022 | OPL-1 | PagoEfectivo como proveedor de pago de Odoo: código de pago (CIP) para pagar en efectivo en agentes y bodegas o desde la banca, confirmado por notificación firmada.
[l10n_pe_vat_sunat](OL-ACCOUNTING/l10n_pe_vat_sunat/) | 22.20261012 | OPL-1 | Consulta y actualización automática de datos de RUC y DNI desde el portal SUNAT, ApiPerú, Apis.net.pe y JSON-PE. Padrón de buenos contribuyentes y agentes de retención con caché diaria.

### OL-INVOICING

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_complaints_book](OL-INVOICING/al_l10n_pe_complaints_book/) | 9.20261013 | OPL-1 | Libro de Reclamaciones físico y virtual conforme al Código del Consumidor y al D.S. 011-2011-PCM: hoja del Anexo I, constancia por correo, plazo de 15 días hábiles, respuesta, SIREC y multicompañía.
[al_l10n_pe_delivery_guide_report](OL-INVOICING/al_l10n_pe_delivery_guide_report/) | 12.20261012 | OPL-1 | Representación impresa propia de la guía de remisión electrónica remitente (SUNAT) para stock.picking.
[al_l10n_pe_edi_downpayment_discount](OL-INVOICING/al_l10n_pe_edi_downpayment_discount/) | 5.20261018 | OPL-1 | Corrige el XML UBL 2.1 de SUNAT con anticipos y descuentos globales: anticipos exonerados e inafectos, un anticipo por comprobante, descuentos de partes no gravadas y notas de crédito sin bloqueos.
[al_l10n_pe_edi_free](OL-INVOICING/al_l10n_pe_edi_free/) | 1.20261021 | OPL-1 | Facturas y boletas con transferencias gratuitas (retiros, bonificaciones, muestras): impuesto gratuito exonerado o inafecto, leyenda 1002, contado y validación de las reglas SUNAT al publicar.
[al_l10n_pe_edi_purchase_settlement](OL-INVOICING/al_l10n_pe_edi_purchase_settlement/) | 4.20261018 | OPL-1 | Liquidación de compra electrónica (tipo 04) a personas naturales sin RUC: XML UBL 2.1 firmado y enviado, retención del IGV y del impuesto a la renta, PDF y reversión.
[al_l10n_pe_invoice](OL-INVOICING/al_l10n_pe_invoice/) | 21.20261018 | OPL-1 | Presentación del comprobante electrónico: QR SUNAT, monto en letras, detalle tributario, detracción, cuotas de crédito, firmas y reportes propios A4 y ticket 80mm.
[al_ose_factory_hka](OL-INVOICING/al_ose_factory_hka/) | 4.20261012 | OPL-1 | The Factory HKA como Operador de Servicios Electrónicos: facturas, boletas, notas, bajas, comprobantes de retención (CRE) y su reversión, con funciones que se activan en Ajustes.
[al_sale_approval](OL-INVOICING/al_sale_approval/) | 2.20261013 | OPL-1 | Las ventas de productos marcados no se confirman sin una solicitud aprobada en Aprobaciones.
[al_website_sale_pe](OL-INVOICING/al_website_sale_pe/) | 1.20261014 | OPL-1 | Checkout de la tienda en línea para Perú: el cliente elige boleta o factura, su RUC o DNI se consulta en SUNAT/RENIEC y llena el nombre y la dirección.

### OL-PAYROLL

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_hr_pe](OL-PAYROLL/al_hr_pe/) | 35.20261012 | OPL-1 | Localización peruana de nómina: tablas PLAME/AFP, campos laborales en hr.version, reglas salariales SUNAT y exportadores PLAME/AFPNet.
[al_hr_pe_account](OL-PAYROLL/al_hr_pe_account/) | 12.20261012 | OPL-1 | Asientos de planilla y beneficios sociales con distribución analítica opcional por compañía.
[al_hr_pe_attendance](OL-PAYROLL/al_hr_pe_attendance/) | 22.20261012 | OPL-1 | Capa peruana sobre planning EE: régimen atípico, monitor de asistencia, tareaje y horas extra.
[al_hr_pe_benefits](OL-PAYROLL/al_hr_pe_benefits/) | 23.20261012 | OPL-1 | CTS, gratificaciones, liquidaciones, renta 5ta, provisiones, subsidios, utilidades, vacaciones, préstamos y quincena.
[al_hr_pe_construction](OL-PAYROLL/al_hr_pe_construction/) | 24.20261012 | OPL-1 | Régimen de construcción civil: tabla salarial por convenio, categorías, BUC, BAE, bonificaciones por condiciones de trabajo, obras y CONAFOVICER.
[al_hr_pe_import](OL-PAYROLL/al_hr_pe_import/) | 11.20261012 | OPL-1 | Framework de importación Excel (openpyxl) con lotes, progreso en vivo y reporte de errores por fila para toda la suite de planillas Perú.
[al_hr_pe_public_holidays](OL-PAYROLL/al_hr_pe_public_holidays/) | 10.20261008 | OPL-1 | Calendario completo de 10 años de días festivos de Peru, listo para Odoo HR. Festivos nacionales y religiosos — aplicados automáticamente al resource.calendar como ausencias.
[al_hr_pe_reports](OL-PAYROLL/al_hr_pe_reports/) | 23.20261012 | OPL-1 | Boleta de pago, certificados, contratos y archivos TXT de pago masivo bancario.

### OL-POS

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_edi_pos](OL-POS/al_l10n_pe_edi_pos/) | 16.20261019 | OPL-1 | Boleta/Factura electrónica desde el punto de venta: selector de tipo de documento, diario por tipo y ticket con formato CPE SUNAT.
[al_l10n_pe_pos_loyalty](OL-POS/al_l10n_pe_pos_loyalty/) | 1.20261019 | OPL-1 | La venta de tarjetas de regalo y recargas del monedero no lleva comprobante y su canje es una forma de pago: la boleta o factura sale con el IGV completo.
[al_pos_network_printer](OL-POS/al_pos_network_printer/) | 4.20261009 | OPL-1 | Imprime tickets y comandas del TPV en impresoras térmicas ESC/POS genéricas conectadas por red, sin IoT Box.
[al_pos_online_payment](OL-POS/al_pos_online_payment/) | 1.20261016 | OPL-1 | Corrige el TPV de Odoo 19 que, tras un cobro en línea, muestra el pago dos veces y un cambio igual al importe pagado.
[al_pos_payment_gateway](OL-POS/al_pos_payment_gateway/) | 6.20261018 | OPL-1 | Cada pasarela (Izipay, Niubiz, Culqi…) como método de pago propio del TPV: el cliente paga con el QR en su teléfono y las devoluciones vuelven a su tarjeta.
[al_pos_pe_partner_lookup](OL-POS/al_pos_pe_partner_lookup/) | 2.20261014 | OPL-1 | En la lista de clientes del TPV, un RUC o DNI que no está registrado se crea en un clic con los datos de SUNAT/RENIEC y queda elegido para la venta.
[al_pos_pe_wallet_qr](OL-POS/al_pos_pe_wallet_qr/) | 1.20261014 | OPL-1 | El QR de cobro de Yape, Plin u otra billetera como método de pago QR del TPV: se muestra en la caja y en la pantalla del cliente, y el cajero confirma el pago.
[al_pos_product_view](OL-POS/al_pos_product_view/) | 7.20261011 | OPL-1 | Chips de filtro por etiqueta de producto sobre el catálogo del TPV y conmutador cuadrícula/lista con filas compactas, popup de información enriquecido y preferencia por cajero.
[al_pos_theme](OL-POS/al_pos_theme/) | 6.20261022 | OPL-1 | Rediseño integral y marca blanca del TPV: tokens de diseño, logo, colores y nombre configurables por caja, sin rastros de Odoo.
[al_pos_vendedor](OL-POS/al_pos_vendedor/) | 4.20261011 | OPL-1 | Vendedor por orden en el TPV: selector en la pantalla de pago, vendedor predeterminado por sesión, vendedor en el ticket y en el análisis de ventas.

### OL-INVENTORY

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_stock_transfer](OL-INVENTORY/al_l10n_pe_stock_transfer/) | 4.20261018 | OPL-1 | Guía de remisión para todos los traslados de la empresa: entre establecimientos (04), compras que recoge (02, 07, 08), devoluciones (06) y exportación (09), y control de los bienes de terceros.
[al_mrp_piece_costing](OL-INVENTORY/al_mrp_piece_costing/) | 2.20261023 | OPL-1 | La orden de corte reparte su costo entre las piezas por área, material de origen y metros de tapacanto, e importa el despiece como productos-pieza.
[al_stock_base](OL-INVENTORY/al_stock_base/) | 4.20261024 | OPL-1 | Página «Logística PE» en las transferencias: un solo lugar para los datos peruanos (guía de remisión, PLE, obra…).
[ol_stock_kardex_pe](OL-INVENTORY/ol_stock_kardex_pe/) | 14.20261012 | OPL-1 | Registro de Inventario Permanente Valorizado (13.1) y en Unidades Físicas (12.1) — formato imprimible SUNAT y kardex interactivo

### OL-PROJECTS

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_construction_attendance](OL-PROJECTS/al_construction_attendance/) | 5.20261021 | LGPL-3 | Sedes de obra con ubicación y horario, quiosco de marcación para personal propio y de contratas, asistencia diaria y costo de la planilla por obra, etapa y partida.
[al_construction_material_request](OL-PROJECTS/al_construction_material_request/) | 25.20261024 | LGPL-3 | El personal de obra pide materiales, se aprueba por niveles y lo disponible sale del almacén central; el faltante va a requerimiento de compra (OCA purchase_request).
[al_construction_planner](OL-PROJECTS/al_construction_planner/) | 45.20261016 | LGPL-3 | Plan de recursos de la obra para cualquier rubro: niveles, etapas, tipos de recurso y recetas configurables, con perfiles de vertical y funciones que se activan por puentes.
[al_construction_planner_approvals](OL-PROJECTS/al_construction_planner_approvals/) | 6.20261021 | LGPL-3 | Plan de recursos y requerimiento de obra aprobados en la aplicación Aprobaciones, con tabla de rutas por tramos y aprobadores por grupo.
[al_construction_planner_approvals_mrp](OL-PROJECTS/al_construction_planner_approvals_mrp/) | 7.20261024 | LGPL-3 | Exceso de la orden de fabricación frente a lo presupuestado: el jefe de producción lo aprueba dentro de su margen y, por encima, va a Aprobaciones.
[al_construction_planner_budget](OL-PROJECTS/al_construction_planner_budget/) | 2.20261016 | LGPL-3 | Presupuesto analítico al aprobar el plan y control de la OC contra el presupuesto.
[al_construction_planner_crew](OL-PROJECTS/al_construction_planner_crew/) | 4.20261016 | LGPL-3 | Asignar cuadrilla con turnos de Planificación, en horas o en días con costo diario por puesto, y horas de la hoja de horas como real.
[al_construction_planner_furniture](OL-PROJECTS/al_construction_planner_furniture/) | 11.20261021 | LGPL-3 | Tipologías de mueble con módulos, piezas, método de unión y lista de materiales, productos por módulo, receta real y despacho a obra, e importación del maestro, del ETO y de la proyección de materiales.
[al_construction_planner_mrp](OL-PROJECTS/al_construction_planner_mrp/) | 10.20261024 | LGPL-3 | Órdenes de fabricación desde el plan, etapa de consumo en la lista de materiales y espera del metrado.
[al_construction_planner_production](OL-PROJECTS/al_construction_planner_production/) | 5.20261019 | LGPL-3 | Accesorios de armado pedidos desde la orden y presupuestado, requerido y consumido en la orden y en el planificador.
[al_construction_planner_purchase](OL-PROJECTS/al_construction_planner_purchase/) | 11.20261024 | LGPL-3 | Compra masiva, requerimiento de obra, abastecimiento de la obra, precios de compra, crear producto y material extra.
[al_construction_planner_sale](OL-PROJECTS/al_construction_planner_sale/) | 4.20261016 | LGPL-3 | Calendario e ingresos, contratos de obra con hitos, entrega semanal, valorización, cobranza y cronograma valorizado.
[al_construction_planner_sale_furniture](OL-PROJECTS/al_construction_planner_sale_furniture/) | 1.20261013 | LGPL-3 | Partidas del contrato por familia de la tipología (cocinas, closets…).
[al_construction_planner_spreadsheet](OL-PROJECTS/al_construction_planner_spreadsheet/) | 3.20261016 | LGPL-3 | Maestro de planificación de la obra como hoja de cálculo de Documentos, con listas de Odoo de referencia y el menú «Enviar al planificador».
[al_construction_planner_subcontract](OL-PROJECTS/al_construction_planner_subcontract/) | 5.20261016 | LGPL-3 | Asignar contrata con su OC de servicio, avance por driver, liquidación semanal y portal de la contrata.
[al_construction_planner_subcontract_purchase](OL-PROJECTS/al_construction_planner_subcontract_purchase/) | 2.20261013 | LGPL-3 | Descuento a la contrata del material extra en su liquidación semanal.
[al_construction_planner_subcontract_sale](OL-PROJECTS/al_construction_planner_subcontract_sale/) | 1.20261023 | LGPL-3 | Adicionales de la contrata desde el cambio de obra y margen de compra por partida.
[al_construction_planner_suite](OL-PROJECTS/al_construction_planner_suite/) | 16.20261023 | LGPL-3 | Instala el planificador con todos sus puentes (perfil mobiliario completo) y reúne las pruebas de integración.
[al_project_gantt_ai](OL-PROJECTS/al_project_gantt_ai/) | 8.20261013 | OPL-1 | Panel de chat opcional para consultar el diagrama de Gantt y recibir propuestas de cambio que el usuario revisa y aplica.
[al_project_gantt_backend](OL-PROJECTS/al_project_gantt_backend/) | 17.20261013 | OPL-1 | Aplicación de Gantt interactivo dentro del backend de Odoo, con menú propio y carga perezosa de la librería.
[al_project_gantt_base](OL-PROJECTS/al_project_gantt_base/) | 18.20261011 | OPL-1 | Capa de datos, mapeo de campos, seguridad y librería Gantt compartidas por las interfaces de Gantt (backend y website).
[al_project_gantt_website](OL-PROJECTS/al_project_gantt_website/) | 12.20261008 | OPL-1 | Página de Gantt en el sitio web, restringida a usuarios internos autenticados.

### OL-INDUSTRIES

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_industry_base](OL-INDUSTRIES/al_industry_base/) | 1.20261017 | OPL-1 | Lo que comparten los paquetes de industria: la localización peruana de la suite y el registro de cada industria, con su actividad CIIU, aplicable por compañía.
[al_industry_construction](OL-INDUSTRIES/al_industry_construction/) | 1.20261017 | LGPL-3 | Constructora lista para planificar y ejecutar obras: plan de recursos por partidas, requerimientos de obra, compras, contratas, cuadrillas, presupuesto, valorización, aprobaciones y planilla de construcción civil.
[al_industry_ecommerce](OL-INDUSTRIES/al_industry_ecommerce/) | 1.20261017 | OPL-1 | Tienda en línea lista para vender: catálogo web, checkout con RUC o DNI y ubigeo, pagos con Culqi, Niubiz o Izipay, boleta y factura electrónica y libro de reclamaciones virtual.
[al_industry_furniture](OL-INDUSTRIES/al_industry_furniture/) | 1.20261017 | LGPL-3 | Fábrica de muebles a medida para obras: tipologías con módulos y piezas, lista de materiales, órdenes de fabricación, metrado, despacho e instalación por torre, piso y departamento.
[al_industry_pharmacy](OL-INDUSTRIES/al_industry_pharmacy/) | 11.20261019 | OPL-1 | Farmacia o botica lista para vender: caja con boleta y factura electrónica, lotes con vencimiento y salida FEFO, datos DIGEMID del producto y libro de reclamaciones.
[al_industry_restaurant](OL-INDUSTRIES/al_industry_restaurant/) | 2.20261017 | OPL-1 | Restaurante listo para atender: salón con mesas, comandas a cocina, división de cuentas y propinas, boleta y factura electrónica desde la caja, cobro con Yape y Plin y libro de reclamaciones.
[al_industry_retail](OL-INDUSTRIES/al_industry_retail/) | 2.20261017 | OPL-1 | Bodega o minimarket listo para vender: caja con boleta y factura electrónica, cobro con Yape y Plin, cliente por RUC o DNI, vendedor por venta, kárdex SUNAT y libro de reclamaciones.

### OL-HEALTH

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_pharmacy_controlled](OL-HEALTH/al_l10n_pe_pharmacy_controlled/) | 3.20261019 | OPL-1 | Listas de fiscalización, receta especial con sus datos y vigencia de 3 días, retención con folio, libros de estupefacientes y psicotrópicos y balance trimestral en PDF y Excel.
[al_l10n_pe_pharmacy_digemid](OL-HEALTH/al_l10n_pe_pharmacy_digemid/) | 5.20261019 | OPL-1 | Precios para el Observatorio de DIGEMID, cumplimiento del 30 % de genéricos (Ley 32033), lista de precios por DCI, reacciones adversas para NotiMED e IGV exonerado de medicamentos oncológicos, para VIH y para diabetes.
[al_l10n_pe_pharmacy_edi](OL-HEALTH/al_l10n_pe_pharmacy_edi/) | 2.20261018 | OPL-1 | Código de unidad del comprobante electrónico (catálogo 03 de SUNAT) para la unidad de cada presentación: caja BX, frasco BO; las demás, el de la unidad del producto.
[al_l10n_pe_prescriber_cmp](OL-HEALTH/al_l10n_pe_prescriber_cmp/) | 3.20261018 | OPL-1 | Abre el portal «Conoce a tu médico» del Colegio Médico del Perú para buscar la colegiatura y registra si el médico está hábil, con fecha y responsable.
[al_pharmacy_base](OL-HEALTH/al_pharmacy_base/) | 4.20261022 | OPL-1 | Maestro farmacéutico: principio activo y equivalentes, registro sanitario, condición de venta, presentaciones con precio propio, turnos del químico farmacéutico y libro de ocurrencias.
[al_pharmacy_care](OL-HEALTH/al_pharmacy_care/) | 1.20261019 | OPL-1 | Tratamientos crónicos por paciente: días cubiertos por cada compra (también de equivalentes), recordatorio de recompra con WhatsApp o correo, adherencia (PDC) y aviso en la caja al elegir al cliente.
[al_pharmacy_insurance](OL-HEALTH/al_pharmacy_insurance/) | 2.20261019 | OPL-1 | Convenios con aseguradoras y empresas: cobertura por producto o categoría, copago, topes por venta y por mes, afiliados, cobro de la parte cubierta en la caja y liquidación mensual a la aseguradora.
[al_pharmacy_loyalty](OL-HEALTH/al_pharmacy_loyalty/) | 1.20261019 | OPL-1 | Puntos y vales para los clientes de la botica sin premiar los medicamentos con receta ni los controlados: no suman puntos ni reciben descuentos o regalos.
[al_pharmacy_pos](OL-HEALTH/al_pharmacy_pos/) | 9.20261022 | OPL-1 | Caja de farmacia: venta por caja, blíster o unidad con su precio, alternativas genéricas primero, receta en la caja, control del químico farmacéutico, lotes disponibles por vencimiento y receta y dispensación registradas al vender.
[al_pharmacy_prescription](OL-HEALTH/al_pharmacy_prescription/) | 3.20261022 | OPL-1 | Receta médica con prescriptor y paciente, dispensación parcial y alternativas, retención con folio, alergias del paciente, libro de recetas y etiqueta de dispensación.
[al_pharmacy_replenishment](OL-HEALTH/al_pharmacy_replenishment/) | 1.20261019 | OPL-1 | Registro de la demanda perdida desde la caja (lo que se pide y no hay) y sugerido de compra por local según la venta diaria, los faltantes, el stock y lo que está por llegar, con solicitudes de presupuesto por proveedor o traslado desde el almacén central.
[al_pharmacy_stock](OL-HEALTH/al_pharmacy_stock/) | 3.20261019 | OPL-1 | Recepción con inspección y registro sanitario vigente, lotes en cuarentena o bloqueados que no se venden, vencimientos, bonificaciones de compra, control de temperatura, alertas sanitarias y actas de baja.
[al_pharmacy_website](OL-HEALTH/al_pharmacy_website/) | 2.20261022 | OPL-1 | Tienda en línea de la botica: genéricos primero en la ficha del producto, receta subida antes de pagar y validada por el químico farmacéutico, controlados solo en el local, recojo en tienda y cadena de frío en la hoja de reparto.

### OL-TOOLS

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_base_module_info](OL-TOOLS/al_base_module_info/) | 2.20261008 | OPL-1 | En Aplicaciones, el botón «Más información» de los módulos con ficha propia abre la ficha completa del módulo.
[al_docs_help](OL-TOOLS/al_docs_help/) | 12.20261023 | OPL-1 | Botón «?» en cada pantalla y asistente de la suite que abre la página que la explica en el sitio de documentación.
[al_mcp_server](OL-TOOLS/al_mcp_server/) | 9.20261013 | OPL-1 | Servidor MCP, Integración con IA, Claude, ChatGPT, Gemini, Grok, Cursor, n8n, LangChain, OAuth 2.0, PKCE, Token Bearer, Token de Acceso Personal, API REST, HTTP Streamable, SSE, Trabajos Asíncronos, Cola en Segundo Plano, Reportes BI, Tabla Dinámica, Series de Tiempo, Análisis de Cohortes, Embudo, Top N, Exportar CSV, Exportar XLSX, Páginas de Portal, Tablero Público, Tarjetas KPI, Generador de Módulos, Generación de Código con IA, LLM, Automatización, Registro de Auditoría, Límite de Tasa, Redis, Caché de Esquema, Tokens con Alcance, Lista de Campos Permitidos, Lista de IP Permitidas, API de Odoo, Conector de Odoo, Asistente de IA, Chatbot, Lenguaje Natural, Actualización Masiva, Creación Masiva, Eliminación Masiva
[al_report_base](OL-TOOLS/al_report_base/) | 2.20261011 | OPL-1 | El formato del comprobante A4 para todos los documentos impresos de la suite: encabezado, pie, estilos y papel.
[ol_licencia_perpetua](OL-TOOLS/ol_licencia_perpetua/) | 1.20260717 | OPL-1 | Override enterprise subscription for testing purposes

### OL-THIRD-PARTY

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_city](OL-THIRD-PARTY/al_l10n_pe_city/) | 3.20261008 | LGPL-3 | Datos de la ciudad
[base_tier_validation](OL-THIRD-PARTY/base_tier_validation/) | 19.0.1.3.1 | AGPL-3 | Implement a validation process based on tiers.
[prt_report_attachment_preview](OL-THIRD-PARTY/prt_report_attachment_preview/) | 19.0.1.0.1 | LGPL-3 | Preview reports and pdf attachments in browser instead of downloading them. Open Report or PDF Attachment in new tab instead of downloading.
[purchase_request](OL-THIRD-PARTY/purchase_request/) | 19.0.1.0.2 | LGPL-3 | Use this module to have notification of requirements of materials and/or external services and keep track of such requirements.
[purchase_tier_validation](OL-THIRD-PARTY/purchase_tier_validation/) | 19.0.1.0.0 | AGPL-3 | Extends the functionality of Purchase Orders to support a tier validation process.
[queue_job](OL-THIRD-PARTY/queue_job/) | 19.0.2.1.0 | LGPL-3 | Job Queue
[//]: # (end addons-all)

Licencias
---------

Los módulos propios usan **OPL-1**, salvo excepciones documentadas en su
manifiesto: `al_construction_material_request` es LGPL-3 porque depende de
`base_tier_validation` (AGPL-3). Los módulos de
`OL-THIRD-PARTY/` conservan la autoría y la licencia de su proyecto de origen.
Revise el `__manifest__.py` de cada módulo.

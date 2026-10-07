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
[OL-TOOLS](OL-TOOLS/) | Utilidades transversales: información de módulos, servidor MCP, licencia.
[OL-THIRD-PARTY](OL-THIRD-PARTY/) | Módulos de otros autores que usa el proyecto, con su autoría y licencia; los cambios locales, anotados en su CHANGELOG.

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
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-TOOLS,
              /home/och/odoo/ce19/myodoo/ol_new_apps/OL-THIRD-PARTY
```

En Odoo.sh y en los servidores donde `ol_new_apps` es un submódulo (por
ejemplo `democonstruccion` o `newallcenter-dev`) hay que añadir las mismas
ocho carpetas al `addons_path`; con solo la raíz, Odoo no encuentra los
módulos.

Estructura
----------

```
OL-ACCOUNTING/ … OL-THIRD-PARTY/   módulos, agrupados por área
docs/                       planes de desarrollo, guías, fichas (generador y
                            capturas), validaciones y datos de prueba
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
[al_account_base](OL-ACCOUNTING/al_account_base/) | 4.20260815 | OPL-1 | Personalizaciones genéricas de la localización contable peruana: glosa en asientos/líneas, menú "Perú" y utilidades compartidas.
[al_account_destinations](OL-ACCOUNTING/al_account_destinations/) | 5.20261007 | OPL-1 | Genera automáticamente el asiento de destino (clase 6 a 9 o viceversa) según los porcentajes configurados por cuenta.
[al_account_move_name_sequence](OL-ACCOUNTING/al_account_move_name_sequence/) | 11.20261007 | OPL-1 | Secuencia ir.sequence OPCIONAL por diario para controlar la numeración (serie-correlativo SUNAT) de los comprobantes.
[al_account_payments](OL-ACCOUNTING/al_account_payments/) | 5.20261007 | OPL-1 | Medio de pago SUNAT (catálogo 1) y número de operación bancaria en pagos y en el asistente de registro de pagos.
[al_l10n_pe_account_letter](OL-ACCOUNTING/al_l10n_pe_account_letter/) | 9.20261007 | OPL-1 | Canje, refinanciación y gestión de letras de cambio para clientes y proveedores (Perú).
[al_l10n_pe_currency](OL-ACCOUNTING/al_l10n_pe_currency/) | 8.20261007 | OPL-1 | Tipo de cambio SUNAT (compra/venta) para USD/PEN desde cuatro fuentes —SUNAT, BCRP, Decolecta y apis.net.pe—, con actualización diaria, registro manual coherente y visualización del T.C. aplicado en facturas en moneda extranjera.
[al_l10n_pe_detraction](OL-ACCOUNTING/al_l10n_pe_detraction/) | 13.20261007 | OPL-1 | Detracciones SUNAT (SPOT): catálogo 54 administrable con porcentajes y montos mínimos, cálculo automático en facturas, depósito/constancia y enlace con el PLE 8.1.
[al_l10n_pe_exchange_closure](OL-ACCOUNTING/al_l10n_pe_exchange_closure/) | 5.20261007 | OPL-1 | Ajuste mensual por diferencia de cambio de las partidas monetarias en moneda extranjera: T.C. compra para activos y T.C. venta para pasivos (art. 61 LIR / art. 34 Reglamento).
[al_l10n_pe_financial_reports](OL-ACCOUNTING/al_l10n_pe_financial_reports/) | 1.20260917 | OPL-1 | Estados financieros peruanos sobre el motor de informes de Odoo: 3.19 Estado de Cambios en el Patrimonio Neto, junto al Balance y el Estado de resultados, en la app Perú.
[al_l10n_pe_multicurrency_revaluation](OL-ACCOUNTING/al_l10n_pe_multicurrency_revaluation/) | 3.20261007 | OPL-1 | Revalúa cada cuenta con el tipo de cambio SUNAT de compra o de venta en el informe de ganancias/pérdidas de moneda no realizadas, y muestra el T.C. aplicado en cada línea.
[al_l10n_pe_ple](OL-ACCOUNTING/al_l10n_pe_ple/) | 9.20261007 | OPL-1 | Completa los libros electrónicos PLE de SUNAT no cubiertos por la localización oficial: Libro 7 (Activos Fijos), 4.1 (Retenciones LIR), 9.1/9.2 (Consignaciones), complementos del Libro 3 (3.8/3.9/3.19/3.23), Libro 10 (Costos) y formatos simplificados (5.2/5.4, 8.3, 14.2). Corrige además el RCE 8.4 y 8.5 del SIRE.
[al_l10n_pe_retention](OL-ACCOUNTING/al_l10n_pe_retention/) | 10.20261007 | OPL-1 | Régimen de Retenciones del IGV (R.S. 037-2002/SUNAT): agente de retención, aplicabilidad con excepciones y retención del 3% en el pago sobre el marco nativo.
[al_l10n_pe_sire](OL-ACCOUNTING/al_l10n_pe_sire/) | 7.20261006 | OPL-1 | Conciliación con el Sistema Integrado de Registros Electrónicos de SUNAT
[al_payment_culqi](OL-ACCOUNTING/al_payment_culqi/) | 1.20261006 | OPL-1 | Culqi como proveedor de pago de Odoo: tarjetas y Yape con Checkout Custom, autenticación 3DS y devoluciones totales o parciales.
[al_payment_niubiz](OL-ACCOUNTING/al_payment_niubiz/) | 1.20261006 | OPL-1 | Niubiz Checkout All-In-One como proveedor de pago: tarjetas, Yape, Plin, Cuotéalo BCP y PagoEfectivo, con anulación y devoluciones.
[l10n_pe_vat_sunat](OL-ACCOUNTING/l10n_pe_vat_sunat/) | 11.20261007 | OPL-1 | Consulta y actualización automática de datos de RUC y DNI desde el portal SUNAT, ApiPerú, Apis.net.pe y JSON-PE. Padrón de buenos contribuyentes y agentes de retención con caché diaria.

### OL-INVOICING

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_complaints_book](OL-INVOICING/al_l10n_pe_complaints_book/) | 1.20261006 | OPL-1 | Libro de Reclamaciones físico y virtual conforme al Código del Consumidor y al D.S. 011-2011-PCM: hoja del Anexo I, constancia por correo, plazo de 15 días hábiles, respuesta, SIREC y multicompañía.
[al_l10n_pe_delivery_guide_report](OL-INVOICING/al_l10n_pe_delivery_guide_report/) | 8.20261007 | OPL-1 | Representación impresa propia de la guía de remisión electrónica remitente (SUNAT) para stock.picking.
[al_l10n_pe_edi_downpayment_discount](OL-INVOICING/al_l10n_pe_edi_downpayment_discount/) | 2.20261007 | OPL-1 | Corrige el XML UBL 2.1 de SUNAT con anticipos y descuentos globales: anticipos exonerados e inafectos, un anticipo por comprobante, descuentos de partes no gravadas y notas de crédito sin bloqueos.
[al_l10n_pe_invoice](OL-INVOICING/al_l10n_pe_invoice/) | 12.20261007 | OPL-1 | Presentación del comprobante electrónico: QR SUNAT, monto en letras, detalle tributario, detracción, cuotas de crédito, firmas y reportes propios A4 y ticket 80mm.

### OL-PAYROLL

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_hr_pe](OL-PAYROLL/al_hr_pe/) | 18.20261007 | OPL-1 | Localización peruana de nómina: tablas PLAME/AFP, campos laborales en hr.version, reglas salariales SUNAT y exportadores PLAME/AFPNet.
[al_hr_pe_account](OL-PAYROLL/al_hr_pe_account/) | 5.20261007 | OPL-1 | Asientos de planilla y beneficios sociales con distribución analítica opcional por compañía.
[al_hr_pe_attendance](OL-PAYROLL/al_hr_pe_attendance/) | 6.20260816 | OPL-1 | Capa peruana sobre planning EE: régimen atípico, monitor de asistencia, tareaje y horas extra.
[al_hr_pe_benefits](OL-PAYROLL/al_hr_pe_benefits/) | 8.20261007 | OPL-1 | CTS, gratificaciones, liquidaciones, renta 5ta, provisiones, subsidios, utilidades, vacaciones, préstamos y quincena.
[al_hr_pe_construction](OL-PAYROLL/al_hr_pe_construction/) | 13.20261007 | OPL-1 | Régimen de construcción civil: tabla salarial por convenio, categorías, BUC, BAE, bonificaciones por condiciones de trabajo, obras y CONAFOVICER.
[al_hr_pe_import](OL-PAYROLL/al_hr_pe_import/) | 5.20261007 | OPL-1 | Framework de importación Excel (openpyxl) con lotes, progreso en vivo y reporte de errores por fila para toda la suite de planillas Perú.
[al_hr_pe_public_holidays](OL-PAYROLL/al_hr_pe_public_holidays/) | 5.20261007 | OPL-1 | Calendario completo de 10 años de días festivos de Peru, listo para Odoo HR. Festivos nacionales y religiosos — aplicados automáticamente al resource.calendar como ausencias.
[al_hr_pe_reports](OL-PAYROLL/al_hr_pe_reports/) | 10.20261007 | OPL-1 | Boleta de pago, certificados, contratos y archivos TXT de pago masivo bancario.

### OL-POS

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_edi_pos](OL-POS/al_l10n_pe_edi_pos/) | 9.20261007 | OPL-1 | Boleta/Factura electrónica desde el punto de venta: selector de tipo de documento, diario por tipo y ticket con formato CPE SUNAT.
[al_pos_network_printer](OL-POS/al_pos_network_printer/) | 1.20261006 | OPL-1 | Imprime tickets y comandas del TPV en impresoras térmicas ESC/POS genéricas conectadas por red, sin IoT Box.
[al_pos_product_view](OL-POS/al_pos_product_view/) | 4.20260925 | OPL-1 | Chips de filtro por etiqueta de producto sobre el catálogo del TPV y conmutador cuadrícula/lista con filas compactas, popup de información enriquecido y preferencia por cajero.
[al_pos_theme](OL-POS/al_pos_theme/) | 1.20261005 | OPL-1 | Rediseño integral y marca blanca del TPV: tokens de diseño, logo, colores y nombre configurables por caja, sin rastros de Odoo.
[al_pos_vendedor](OL-POS/al_pos_vendedor/) | 2.20260721 | OPL-1 | Vendedor por orden en el TPV: selector en la pantalla de pago, vendedor predeterminado por sesión, vendedor en el ticket y en el análisis de ventas.

### OL-INVENTORY

módulo | versión | licencia | resumen
--- | --- | --- | ---
[ol_stock_kardex_pe](OL-INVENTORY/ol_stock_kardex_pe/) | 6.20261006 | OPL-1 | Registro de Inventario Permanente Valorizado (13.1) y en Unidades Físicas (12.1) — formato imprimible SUNAT y kardex interactivo

### OL-PROJECTS

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_construction_material_request](OL-PROJECTS/al_construction_material_request/) | 4.20261001 | LGPL-3 | El personal de obra pide materiales, se aprueba por niveles y lo disponible sale del almacén central; el faltante va a requerimiento de compra (OCA purchase_request).
[al_project_gantt_ai](OL-PROJECTS/al_project_gantt_ai/) | 3.20260817 | OPL-1 | Panel de chat opcional para consultar el diagrama de Gantt y recibir propuestas de cambio que el usuario revisa y aplica.
[al_project_gantt_backend](OL-PROJECTS/al_project_gantt_backend/) | 12.20260818 | OPL-1 | Aplicación de Gantt interactivo dentro del backend de Odoo, con menú propio y carga perezosa de la librería.
[al_project_gantt_base](OL-PROJECTS/al_project_gantt_base/) | 14.20260818 | OPL-1 | Capa de datos, mapeo de campos, seguridad y librería Gantt compartidas por las interfaces de Gantt (backend y website).
[al_project_gantt_website](OL-PROJECTS/al_project_gantt_website/) | 11.20260818 | OPL-1 | Página de Gantt en el sitio web, restringida a usuarios internos autenticados.

### OL-TOOLS

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_base_module_info](OL-TOOLS/al_base_module_info/) | 1.20260914 | OPL-1 | En Aplicaciones, el botón «Más información» de los módulos con ficha propia abre la ficha completa del módulo.
[al_mcp_server](OL-TOOLS/al_mcp_server/) | 5.20261005 | OPL-1 | Servidor MCP, Integración con IA, Claude, ChatGPT, Gemini, Grok, Cursor, n8n, LangChain, OAuth 2.0, PKCE, Token Bearer, Token de Acceso Personal, API REST, HTTP Streamable, SSE, Trabajos Asíncronos, Cola en Segundo Plano, Reportes BI, Tabla Dinámica, Series de Tiempo, Análisis de Cohortes, Embudo, Top N, Exportar CSV, Exportar XLSX, Páginas de Portal, Tablero Público, Tarjetas KPI, Generador de Módulos, Generación de Código con IA, LLM, Automatización, Registro de Auditoría, Límite de Tasa, Redis, Caché de Esquema, Tokens con Alcance, Lista de Campos Permitidos, Lista de IP Permitidas, API de Odoo, Conector de Odoo, Asistente de IA, Chatbot, Lenguaje Natural, Actualización Masiva, Creación Masiva, Eliminación Masiva
[ol_licencia_perpetua](OL-TOOLS/ol_licencia_perpetua/) | 1.20260717 | OPL-1 | Override enterprise subscription for testing purposes

### OL-THIRD-PARTY

módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_city](OL-THIRD-PARTY/al_l10n_pe_city/) | 2.20260730 | LGPL-3 | Datos de la ciudad
[base_tier_validation](OL-THIRD-PARTY/base_tier_validation/) | 19.0.1.3.1 | AGPL-3 | Implement a validation process based on tiers.
[prt_report_attachment_preview](OL-THIRD-PARTY/prt_report_attachment_preview/) | 19.0.1.0.1 | LGPL-3 | Preview reports and pdf attachments in browser instead of downloading them. Open Report or PDF Attachment in new tab instead of downloading.
[queue_job](OL-THIRD-PARTY/queue_job/) | 19.0.2.1.0 | LGPL-3 | Job Queue
[//]: # (end addons-all)

Licencias
---------

Los módulos propios usan **OPL-1**, salvo excepciones documentadas en su
manifiesto: `al_construction_material_request` es LGPL-3 porque depende de
`base_tier_validation` (AGPL-3). Los módulos de
`OL-THIRD-PARTY/` conservan la autoría y la licencia de su proyecto de origen.
Revise el `__manifest__.py` de cada módulo.

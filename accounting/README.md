accounting
==========

**Contabilidad y tributación peruana.**

Para qué es esta carpeta
------------------------

Localización contable y tributaria de Perú sobre Odoo 19: la app **Perú**, plan de cuentas y destinos, numeración de asientos, medios de pago SUNAT, letras, tipo de cambio de compra y venta, detracciones (SPOT), retenciones de IGV, cierre y revaluación por diferencia de cambio, estados financieros, libros electrónicos (PLE) y registros SIRE.

Qué va aquí
-----------

- La app **Perú** (`al_account_base`) y lo que cuelga de ella: configuración contable, catálogos y menús fiscales.
- Obligaciones tributarias: detracciones, retenciones, PLE, SIRE y padrón SUNAT de contactos.
- Tipo de cambio, cierre de diferencia de cambio, revaluación multimoneda y reportes financieros.

Qué no va aquí
--------------

- Representación impresa y documentos electrónicos (factura, boleta, guía) → `invoicing/`.
- Planillas, aunque generen asientos contables → `payroll/`.
- Comprobantes emitidos desde el TPV → `pos/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_account_base](al_account_base/) | 4.20260815 | OPL-1 | Personalizaciones genéricas de la localización contable peruana: glosa en asientos/líneas, menú "Perú" y utilidades compartidas.
[al_account_destinations](al_account_destinations/) | 4.20260828 | OPL-1 | Genera automáticamente el asiento de destino (clase 6 a 9 o viceversa) según los porcentajes configurados por cuenta.
[al_account_move_name_sequence](al_account_move_name_sequence/) | 9.20260828 | OPL-1 | Secuencia ir.sequence OPCIONAL por diario para controlar la numeración (serie-correlativo SUNAT) de los comprobantes.
[al_account_payments](al_account_payments/) | 4.20260828 | OPL-1 | Medio de pago SUNAT (catálogo 1) y número de operación bancaria en pagos y en el asistente de registro de pagos.
[al_l10n_pe_account_letter](al_l10n_pe_account_letter/) | 7.20260901 | OPL-1 | Canje, refinanciación y gestión de letras de cambio para clientes y proveedores (Perú).
[al_l10n_pe_currency](al_l10n_pe_currency/) | 7.20260901 | OPL-1 | Tipo de cambio SUNAT (compra/venta) para USD/PEN desde cuatro fuentes —SUNAT, BCRP, Decolecta y apis.net.pe—, con actualización diaria, registro manual coherente y visualización del T.C. aplicado en facturas en moneda extranjera.
[al_l10n_pe_detraction](al_l10n_pe_detraction/) | 12.20260827 | OPL-1 | Detracciones SUNAT (SPOT): catálogo 54 administrable con porcentajes y montos mínimos, cálculo automático en facturas, depósito/constancia y enlace con el PLE 8.1.
[al_l10n_pe_exchange_closure](al_l10n_pe_exchange_closure/) | 4.20260828 | OPL-1 | Ajuste mensual por diferencia de cambio de las partidas monetarias en moneda extranjera: T.C. compra para activos y T.C. venta para pasivos (art. 61 LIR / art. 34 Reglamento).
[al_l10n_pe_financial_reports](al_l10n_pe_financial_reports/) | 1.20260917 | OPL-1 | Estados financieros peruanos sobre el motor de informes de Odoo: 3.19 Estado de Cambios en el Patrimonio Neto, junto al Balance y el Estado de resultados, en la app Perú.
[al_l10n_pe_multicurrency_revaluation](al_l10n_pe_multicurrency_revaluation/) | 2.20260916 | OPL-1 | Revalúa cada cuenta con el tipo de cambio SUNAT de compra o de venta en el informe de ganancias/pérdidas de moneda no realizadas, y muestra el T.C. aplicado en cada línea.
[al_l10n_pe_ple](al_l10n_pe_ple/) | 8.20260828 | OPL-1 | Completa los libros electrónicos PLE de SUNAT no cubiertos por la localización oficial: Libro 7 (Activos Fijos), 4.1 (Retenciones LIR), 9.1/9.2 (Consignaciones), complementos del Libro 3 (3.8/3.9/3.19/3.23), Libro 10 (Costos) y formatos simplificados (5.2/5.4, 8.3, 14.2). Corrige además el RCE 8.4 y 8.5 del SIRE.
[al_l10n_pe_retention](al_l10n_pe_retention/) | 8.20260828 | OPL-1 | Régimen de Retenciones del IGV (R.S. 037-2002/SUNAT): agente de retención, aplicabilidad con excepciones y retención del 3% en el pago sobre el marco nativo.
[al_l10n_pe_sire](al_l10n_pe_sire/) | 5.20260803 | OPL-1 | Conciliación con el Sistema Integrado de Registros Electrónicos de SUNAT
[l10n_pe_vat_sunat](l10n_pe_vat_sunat/) | 10.20260828 | OPL-1 | Consulta y actualización automática de datos de RUC y DNI desde el portal SUNAT, ApiPerú, Apis.net.pe y JSON-PE. Padrón de buenos contribuyentes y agentes de retención con caché diaria.
[//]: # (end addons)

---
modulos: []
---

# Perú

La suite completa la [localización peruana de Odoo](https://www.odoo.com/documentation/19.0/es_419/applications/finance/fiscal_localizations/peru.html)
(`l10n_pe`, `l10n_pe_edi` y, en Enterprise, `l10n_pe_reports`) con lo que una
empresa peruana necesita en el día a día: los datos de los libros
electrónicos, el tipo de cambio de compra y venta, las detracciones y
retenciones, los registros del SIRE, los libros PLE que faltan, la diferencia
de cambio de cierre, los asientos de destino y la representación impresa de
los comprobantes electrónicos. Todo queda reunido en la aplicación **Perú**,
con su menú y su página de ajustes.

## Módulos

| Módulo | Qué agrega | Página |
|---|---|---|
| `al_account_base` | Aplicación **Perú**, glosa, naturaleza del diario, código SUNAT del banco, establecimiento anexo | [Configuración contable básica](peru/accounting_base.md) |
| `l10n_pe_vat_sunat` | Autocompletado de contactos por RUC o DNI y padrones de SUNAT | [Consulta de RUC y DNI](peru/ruc_dni_lookup.md) |
| `al_account_move_name_sequence` | Series CPE y numeración sin huecos por diario | [Numeración de asientos y series](peru/entry_numbering.md) |
| `al_account_payments` | Catálogo de medios de pago y número de operación en los pagos | [Medios de pago SUNAT](peru/payment_methods.md) |
| `al_l10n_pe_currency` | Tipo de cambio compra y venta de SUNAT y BCRP, elegible en cada comprobante | [Tipo de cambio](peru/exchange_rates.md) |
| `al_l10n_pe_exchange_closure`, `al_l10n_pe_multicurrency_revaluation` | Ajuste de cierre de saldos en moneda extranjera | [Diferencia de cambio](peru/exchange_differences.md) |
| `al_account_destinations` | Asiento de destino de la clase 6 al Elemento 9 | [Asientos de destino](peru/destination_entries.md) |
| `al_l10n_pe_detraction` | Detracciones SPOT en ventas y compras, depósito masivo | [Detracciones (SPOT)](peru/detractions.md) |
| `al_l10n_pe_retention` | Retenciones del IGV, CRE y resumen del PDT 626 | [Retenciones del IGV](peru/withholdings.md) |
| `al_l10n_pe_invoice`, `al_l10n_pe_delivery_guide_report`, `al_l10n_pe_edi_downpayment_discount`, `al_ose_factory_hka` | Comprobante y guía impresos, anticipos y descuentos, operador The Factory HKA | [Facturación electrónica](peru/electronic_invoicing.md) |
| `al_l10n_pe_complaints_book` | Libro de reclamaciones en el sitio web | [Libro de reclamaciones](peru/complaints_book.md) |
| `al_l10n_pe_ple` | Libros PLE que Odoo no genera y formatos simplificados | [Libros electrónicos (PLE)](peru/ple.md) |
| `al_l10n_pe_sire` | Conciliación y envío del RVIE y el RCE | [Registros SIRE](peru/sire.md) |
| `al_l10n_pe_financial_reports` | Estado de cambios en el patrimonio neto (3.19) | [Estados financieros](peru/financial_statements.md) |

`al_account_base` se instala solo como dependencia de los demás. Varios
módulos (detracciones, PLE, revaluación multimoneda, estados financieros)
requieren Odoo Enterprise.

## Configuración

1. Instale la localización peruana de Odoo y el plan contable PCGE en la
   compañía, con su RUC.
2. Instale los módulos de la suite que necesite; la base contable se instala
   sola.
3. Vaya a **Perú ‣ Configuración ‣ Ajustes**: la página reúne un bloque por
   módulo instalado (tipo de cambio, detracciones, retenciones, cierre de
   tipo de cambio, asientos de destino, SIRE, libros PLE…). La configuración
   que depende del RUC se guarda en la compañía raíz y las sucursales la
   heredan.
4. Revise **Perú ‣ Configuración**: las secciones **Contabilidad**,
   **Comprobantes electrónicos**, **Tributos SUNAT**, **Cuentas de la
   localización** y **Consultas RUC / DNI** agrupan los catálogos y datos
   maestros de todos los módulos.

![Menú Configuración de la aplicación Perú](peru/peru-configuration-menu.png)

![Página de ajustes de la aplicación Perú](peru/peru-settings.png)

### Datos maestros

Antes de operar, complete en este orden:

1. Diarios con su naturaleza y, en los de ventas, sus Series CPE
   ([Configuración contable básica](peru/accounting_base.md),
   [Numeración de asientos y series](peru/entry_numbering.md)).
2. Cuentas bancarias con su código SUNAT y la cuenta de detracciones del Banco
   de la Nación.
3. Conexiones de consulta de RUC y DNI con su token
   ([Consulta de RUC y DNI](peru/ruc_dni_lookup.md)).
4. Tipos de cambio del año ([Tipo de cambio](peru/exchange_rates.md)).
5. Productos con su tipo de detracción ([Detracciones](peru/detractions.md)) y
   centros de costo con su cuenta de destino
   ([Asientos de destino](peru/destination_entries.md)).

## Flujo de un mes

1. **Ventas y compras**: los comprobantes llevan su serie, el tipo de cambio
   elegido, la detracción y la retención que correspondan.
2. **Cobros y pagos**: medio de pago y número de operación; depósitos de
   detracciones y comprobantes de retención.
3. **Cierre del mes**: [diferencia de cambio](peru/exchange_differences.md) y
   cuadre de los [asientos de destino](peru/destination_entries.md).
4. **Declaraciones**: [registros SIRE](peru/sire.md),
   [libros PLE](peru/ple.md) y resumen del PDT 626.
5. **Cierre del ejercicio**: [estados financieros](peru/financial_statements.md)
   y libros anuales (activos fijos, costos).

!!! info "Ver también"
    - [Odoo: localización Perú](https://www.odoo.com/documentation/19.0/es_419/applications/finance/fiscal_localizations/peru.html)
    - [Odoo: Contabilidad](https://www.odoo.com/documentation/19.0/es_419/applications/finance/accounting.html)

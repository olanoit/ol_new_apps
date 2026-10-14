# Oportunidades de desarrollo futuro — localización peruana

Análisis del 14/10/2026 de las aplicaciones publicadas en Odoo Apps. Búsquedas:
«peru», «perú», «sunat», «peruvian», «l10n_pe» y «planilla»; 188 apps
distintas, de las cuales unas 90 son de la localización peruana. Se compararon
con la suite y con lo que Odoo 19 trae de serie (Community y Enterprise).

De ese análisis se decidió desarrollar ahora:

1. La tienda en línea peruana.
2. La consulta de RUC/DNI en el TPV.
3. Los cobros con QR (Yape/Plin) y pasarelas en el TPV.

Lo que sigue queda como oportunidad de desarrollo futuro, por prioridad.

## 1. Conector OSE/PSE Nubefact

- **Hueco:** Odoo 19 solo trae como proveedor de facturación electrónica
  Estela (ex-Digiflow), SUNAT directo e IAP de Odoo
  (`ee19/l10n_pe_edi/models/res_company.py`). La suite añade The Factory HKA.
  Nubefact es el PSE/OSE más usado por las pymes peruanas.
- **Mercado:** `l10n_pe_edi_odoofact` (OPeru, v19, gratuito, 1 323
  descargas: el más descargado de la búsqueda), `l10n_pe_edi_picking` (guías
  con Nubefact, 86,16 €), `l10n_pe_edi_ose_endpoint` (endpoint OSE por
  compañía, 42,87 €).
- **Alcance sugerido:** proveedor `nubefact` en `l10n_pe_edi_provider`, con
  la API JSON de Nubefact para comprobantes, bajas y guías de remisión, como
  `al_ose_factory_hka`.
- **Cuándo:** en cuanto haya un cliente con contrato de Nubefact (hacen falta
  su ruta y su token).

## 2. Control de bancarización (Ley 28194)

- **Hueco:** `al_account_payments` registra el medio de pago (catálogo 1),
  pero no avisa de los pagos que, sin medio de pago, hacen perder el gasto y
  el crédito fiscal. El umbral es S/ 2 000 o US$ 500.
- **Mercado:** no hay módulo publicado; es una oportunidad propia.
- **Alcance sugerido:**
  - aviso o bloqueo configurable al registrar pagos en efectivo por encima
    del umbral;
  - reporte de comprobantes no bancarizados del periodo;
  - marca en el Registro de Compras.

## 3. Anticipos contables a proveedores y de clientes (122 / 422)

- **Hueco:** sin flujo propio en la suite; `al_l10n_pe_edi_downpayment_discount`
  solo corrige el XML del CPE. Antes de desarrollar, hay que comprobar cuánto
  cubre Odoo 19 de serie con las cuentas de pagos pendientes por diario.
- **Mercado:** `l10n_pe_advance_payment` (v18, 67,73 €).
- **Alcance sugerido:** anticipo como pago a una cuenta conciliable 122/422 y
  aplicación contra la factura con su asiento.

## 4. Marketplaces: Falabella y Mercado Libre

- **Hueco:** la suite no conecta con marketplaces. Extendrix tiene
  `meli_oerp` (Mercado Libre) fuera de este repositorio.
- **Mercado:** `jjro_falabella` (v20, 267,42 €), `mp_falabella_linio_seller`
  (v20, 120,74 €), `mdv_mercadolibre_connector` (v19, 53,66 €).
- **Alcance sugerido:**
  - pedidos como `sale.order`;
  - envío de stock y precios;
  - comprobante electrónico al despachar.

## 5. Couriers peruanos (Olva, Shalom, Urbano, Marvisur)

- **Hueco:** Odoo solo trae transportistas internacionales (DHL, FedEx, UPS,
  Sendcloud…).
- **Mercado:** `delivery_olva_tracking`, `delivery_urbano_tracking`,
  `delivery_marvisur_tracking`, Shalom (Incorsa, v18, 70 € cada uno). Son
  rastreos **no oficiales**: leen la página pública de cada courier.
- **Alcance sugerido:** `delivery.carrier` con tarifa por zona (ubigeo) y
  rastreo; usar una API oficial donde exista (Olva y Urbano tienen APIs para
  clientes corporativos).

## 6. Tipo de cambio de otras monedas (SBS)

- **Hueco:** `al_l10n_pe_currency` solo actualiza USD/PEN.
- **Mercado:** `pc_currency_rate_live` (v19, gratuito: SUNAT para USD y SBS
  para el resto).
- **Alcance sugerido:** EUR y otras monedas desde la tabla diaria de la SBS,
  con el mismo cron y las mismas protecciones de las tasas manuales. Ojo: la
  SBS bloquea a los clientes que se presentan como Chrome (Incapsula).

## Revisado y descartado

| Grupo | Ejemplos | Motivo |
|---|---|---|
| Mercado Pago | `payment_mercadopago_pe` | Odoo 19 lo trae de serie: `payment_mercado_pago` incluye PE/PEN |
| Ya cubierto por la suite | RUC/DNI, tipo de cambio, PLE, SIRE, kárdex 13.1, tabla 12 por movimiento, asientos destino, retenciones, percepciones, detracciones, 621, libro de reclamaciones, Culqi, Izipay, feriados, tipos de ausencia PLAME, planilla | Equivalentes en la suite |
| Packs «todo en uno» | `dvl_l10n_pe_account`, `l10n_pe_suite`, `l10n_pe_sunat_complete` | Repiten lo que la suite ya tiene |
| Versiones antiguas | módulos 7.0 a 13.0 (Bitodoo, Odoo Peru, ROCKSCRIPTS) | Sin versión vigente; funcionalidad cubierta |
| Genéricos | cancelaciones masivas, seguridad de la base, temas, modo desarrollador | No son de la localización |
| Otros países | planillas de Colombia, Guatemala, Panamá, Costa Rica; e-Meterai de Indonesia | Aparecen por coincidencias de texto |
| Consulta de placas y SOAT | `json_pe_consulta` | Nicho; revisar si un cliente de transporte lo pide |

## Fuente

- Odoo Apps, búsqueda «peru» (9 páginas):
  https://apps.odoo.com/apps/modules/browse/page/1?search=peru
- Extracción repetible: un script con `urllib` lee las tarjetas de cada página
  (nombre técnico, versión, autor, precio, descargas, resumen).

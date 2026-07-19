# PE - Detracciones SPOT (AL)

Capa funcional de **detracciones** (Sistema de Pago de Obligaciones
Tributarias) sobre la localización peruana de Odoo 19.
**Guía funcional para consultores:** [`docs/detracciones.md`](docs/detracciones.md). Complementa el
soporte nativo de `l10n_pe_edi` — que ya emite el bloque «Detraccion» en el
XML UBL a partir del % del producto — con lo que falta para operar el SPOT
de punta a punta.

## Qué hace

- **Catálogo 54 administrable** (Perú ▸ Configuración ▸ Detracciones):
  código, descripción, **porcentaje** y **monto mínimo** por tipo (S/ 700
  general, S/ 400 transporte, 1/2 UIT Anexo 1, sin mínimo para oro/
  minerales/inmuebles). Botón para re-sincronizar los productos vinculados
  cuando SUNAT cambia un porcentaje.
- **Producto**: campo «Tipo de detracción (SPOT)» que completa
  automáticamente los campos nativos (`l10n_pe_withhold_code` /
  `l10n_pe_withhold_percentage`) usados por la factura electrónica.
- **Factura (ventas y compras)** — pestaña **Detracción** visible cuando
  aplica:
  - detección automática: código **dominante** (mayor %) entre los
    productos, y verificación del **monto mínimo** sobre el total con IGV
    en soles;
  - **monto de la detracción redondeado a soles enteros** (regla SUNAT,
    mismo criterio que el XML nativo) y **neto** a cobrar/pagar;
  - al publicar una venta afecta se fija solo el **tipo de operación
    `1001`** si no se eligió un valor 100x (requisito del XML).
- **Reparto contable opcional** (Ajustes ▸ Perú ▸ «Separar detracción en
  el asiento»): la línea por cobrar/pagar se divide **dentro del mismo
  asiento de la factura** — neto en la cuenta del tercero y detracción en
  las cuentas configuradas (por cobrar 121x / por pagar 424x, requeridas
  al activar la opción). Sin segundo asiento; desactivada, comportamiento
  estándar.
- **Depósito y constancia** (botón «Registrar depósito»):
  - compras: registra el pago parcial de la factura por el monto detraído
    desde el diario del banco (depósito propio al BN a nombre del
    proveedor) y lo concilia;
  - ventas: registra el cobro de la detracción depositada por el cliente
    en el diario que representa la cuenta del BN;
  - en ambos casos llena la **constancia** (`l10n_pe_detraction_number` /
    `date` de `l10n_pe_reports`), que alimenta los campos 32-33 del
    **PLE 8.1**.
- Filtros en facturas: «Con detracción» y «Detracción sin constancia».

## Origen y decisiones (análisis del módulo v18)

Basado en `ce18 …/al_l10n_pe_edi_detraction`. Se adoptó su catálogo con
correcciones de datos (027/030/040 al **4 %** oficial; 012/020/022/037 al
**12 %** de la R.S. 071-2018) y se **descartó** el cronograma de pagos con
re-balanceo manual de asientos (complejo y riesgoso): el flujo v19 usa
pagos estándar conciliados. El XML UBL no se toca: lo emite `l10n_pe_edi`.

## Requisitos

- Ventas: cuenta de detracciones del **Banco de la Nación** registrada en
  la compañía (Contactos ▸ pestaña bancos, banco «Banco de la Nación») —
  la usa el XML nativo.
- Productos afectos con su tipo de detracción asignado.

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_detraction \
  --test-enable --test-tags /al_l10n_pe_detraction --stop-after-init
```

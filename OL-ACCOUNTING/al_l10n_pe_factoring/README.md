# PE - Factoring de facturas (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo `al_l10n_pe_factoring`. Registra la cesión de facturas de cliente a un
factor (banco o empresa de factoring), con y sin recurso, sobre las facturas
nativas de Odoo: no duplica la factura ni el cobro. Diseño en
`docs/md/analisis_requerimientos_implementacion.md` (sección 3) y marco en
`docs/md/factoring_en_el_peru_y_prompt_odoo_19.md`.

## Flujo

1. **Operación** (`l10n_pe.factoring`, Perú ▸ Factoring ▸ Operaciones, o
   «Ceder a factoring» en la lista de facturas): factor, modalidad, contrato,
   moneda, % de adelanto y las facturas (`l10n_pe.factoring.line`) con su
   valor nominal, vencimiento y anotación CAVALI.
2. **Ceder facturas**: asiento de cesión; la factura sale de la 1212.
3. **Registrar desembolso**: adelanto, intereses, comisión y gastos; el neto
   entra al banco.
4. Con recurso, **Devengar intereses** cuando corresponda (y al cerrar se
   devenga el resto).
5. **Cobro del factor** (el cliente pagó al factor) o, con recurso,
   **Recompra** (no pagó).

Estados: Borrador → Cedida → Desembolsada → Liquidada / Recomprada; y
Cancelada (solo antes del desembolso: la factura vuelve al cliente).

## Asientos

Cuentas en *Perú ▸ Configuración ▸ Cuentas de la localización ▸ Factoring*,
por modalidad y moneda; se crean solas con el PCGE.

| Cuenta | PCGE |
|---|---|
| Facturas cedidas (sin recurso) | 1214 Facturas en descuento |
| Obligación con el factor (con recurso) | 4512 Préstamos de otras entidades |
| Intereses | 6734 Intereses por documentos vendidos o descontados |
| Intereses diferidos (con recurso, opcional) | 3731 Intereses no devengados |
| Comisiones y gastos | 6391 Gastos bancarios |

Ejemplo: factura de S/ 1 000, adelanto 90 %, intereses 20, comisión 10,
gastos 5.

**Sin recurso** (el factor asume el riesgo; NIIF 9: baja de la cuenta por
cobrar):

| Paso | Debe | Haber |
|---|---|---|
| Cesión | 1214 (factor) 1 000 | 1212 (cliente) 1 000 — concilia la factura: queda pagada |
| Desembolso | Banco 865 · 6734 20 · 6391 15 | 1214 (factor) 900 |
| Cobro del factor | Banco 100 | 1214 (factor) 100 (retenido) |

**Con recurso** (el riesgo sigue en la empresa; NIIF 9: la cuenta por cobrar
**no** se da de baja y el adelanto es una obligación), mismo ejemplo con
intereses diferidos:

| Paso | Debe | Haber |
|---|---|---|
| Cesión | — sin asiento: la factura sigue pendiente en 1212 y se marca «Cedida» | — |
| Desembolso | Banco 865 · 3731 20 · 6391 15 | 4512 (factor) 900 |
| Devengo | 6734 | 3731 |
| Cobro del factor | 4512 900 · Banco 100 | 1212 (cliente) 1 000 — concilia la factura: queda pagada |
| Recompra | 4512 900 | Banco 900 — la factura no cambia (sigue pendiente) |

Así la factura con recurso no aparece pagada mientras el cliente no paga:
sigue en el saldo y el vencimiento del cliente y en sus recordatorios.

Los importes van en la moneda de la operación (la de las facturas) con su
contravalor a la fecha; el céntimo de diferencia va al banco o a la
obligación, como en las letras.

## Proceso genérico cubierto (versión 4)

- **Factura negociable** (Ley 29623 modificada por el DU 013-2020, Título I del
  DU para la factura electrónica): en cada factura cedida se registra la
  conformidad del cliente (expresa, presunta a los 8 días calendario o
  disconformidad, que impide ceder), la fecha de conformidad presunta y el
  número y la fecha de anotación en cuenta en CAVALI. La cesión advierte si la
  factura es al contado (sin plazo de pago).
- **Monto neto pendiente de pago** (R.S. 193-2020/SUNAT): el valor nominal
  propuesto es el saldo sin la detracción (si `al_l10n_pe_detraction` está
  instalado) ni la retención del IGV del 3 % cuando el cliente es agente de
  retención (dato de `l10n_pe_vat_sunat`) y la factura supera S/ 700. Es
  editable.
- **Varias facturas y operaciones** con el mismo factor; cobro por factura o
  global; **cobro parcial** de una factura: lo cobrado cubre primero el
  adelanto y después libera el retenido.
- **Comisión con o sin factura**: sin comprobante va a 6391; si el factor la
  factura (con IGV), se elige su factura de proveedor y el descuento la paga.
- **Moneda extranjera**: las cuentas por cobrar y la 1214 se concilian con la
  diferencia de cambio nativa de Odoo; la obligación con recurso (4512, no
  conciliable) se cancela al cambio histórico del adelanto y la diferencia va
  a las cuentas de diferencia de cambio de la compañía.
- **Impago**: con recurso, recompra del adelanto no cubierto (la factura sigue
  pendiente y su provisión o castigo es el nativo de Odoo); sin recurso, el
  retenido no liberado pasa a pérdida (6741).
- **Reportes**: facturas cedidas (cartera por factor, cliente y vencimiento,
  cobrado y por cobrar), análisis y costo financiero por factor y mes.

### Fuera del alcance (y por qué)

- **Integración con CAVALI/Factrack o con la plataforma de conformidad de
  SUNAT**: requieren credenciales de participante y servicios propios de cada
  entidad; aquí se registran los datos que devuelven.
- **Factura negociable impresa** (tercera copia, constancia de presentación):
  la suite emite comprobantes electrónicos.
- **Desembolsos parciales del factor** sobre una misma operación: se registra
  un desembolso por operación (para desembolsos por partes, una operación por
  tramo).
- **Castigo tributario de la factura recomprada**: se usa la provisión de
  cobranza dudosa nativa; los requisitos del art. 37 de la LIR los evalúa el
  contador.
- **Libros electrónicos**: la cesión no genera comprobante ni cambia el
  Registro de Ventas; sus asientos van al Libro Diario como cualquier asiento.

## Supuestos (pendientes de confirmar con el cliente)

- **Modalidad por operación**: ambas disponibles; el cliente aún no indicó cuál usa.
- **Desembolso único** por operación, con un % de adelanto por factura; el
  resto queda retenido y se libera con los cobros.
- **Intereses por adelantado** (descontados del desembolso). Sin recurso van a
  gasto; con recurso se difieren en 3731 si la cuenta está configurada (si se
  deja vacía, van a gasto).
- **El factor cobra al cliente**: la empresa registra el «Cobro del factor»
  cuando el factor le informa el pago.
- La cesión no genera comprobante ni IGV (la cesión de créditos no está gravada).

## Integración

- Factura de cliente: pestaña **Factoring** en «Facturación PE» (operación,
  estado, factor, modalidad e historial), columna opcional «Factoring» en la
  lista y filtro «Cedidas a factoring».
- Una factura no se cede dos veces (salvo que la operación anterior se cancele
  o se recompre).
- Multicompañía: regla de registro por compañía, `_check_company_auto` y
  `check_company` en los Many2one; compañía de solo lectura.
- Grupos: facturación (crear y operar), solo lectura (auditor) y administrador
  contable (cuentas).

## Pruebas

`tests/test_factoring.py` (19): flujo sin recurso completo (factura pagada,
retenido, asientos cuadrados), con recurso cobrado (obligación, devengo y cierre
de intereses), con recurso recomprado (la factura sigue pendiente), no ceder dos
veces y cancelación, nominal mayor que el saldo, cargos mayores que el adelanto,
creación desde la lista, moneda extranjera, multicompañía, formulario,
conformidad (disconformidad bloquea, presunta a los 8 días), monto neto sin la
retención del cliente agente, cobros parciales con y sin recurso, recompra tras
un cobro parcial, comisión facturada por el factor, pérdida del retenido y
diferencia de cambio de la obligación con recurso.

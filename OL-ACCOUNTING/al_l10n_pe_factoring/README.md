# PE - Factoring de facturas (AL)

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
| Facturas cedidas | 1214 Facturas en descuento |
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

**Con recurso** (el riesgo sigue en la empresa; el adelanto es una
obligación), mismo ejemplo con intereses diferidos:

| Paso | Debe | Haber |
|---|---|---|
| Cesión | 1214 (cliente) 1 000 | 1212 (cliente) 1 000 |
| Desembolso | Banco 865 · 3731 20 · 6391 15 | 4512 (factor) 900 |
| Devengo | 6734 | 3731 |
| Cobro del factor | 4512 900 · Banco 100 | 1214 (cliente) 1 000 |
| Recompra | 4512 900 · 1212 (cliente) 1 000 | Banco 900 · 1214 1 000 — la factura vuelve a quedar pendiente |

Los importes van en la moneda de la operación (la de las facturas) con su
contravalor a la fecha; el céntimo de diferencia va al banco o a la
obligación, como en las letras.

## Supuestos (pendientes de confirmar con el cliente)

- **Modalidad por operación**: ambas disponibles; el cliente aún no indicó cuál usa.
- **Desembolso único** por operación, con un % de adelanto por factura; el
  resto queda retenido y se cobra al liquidar. Si el factor desembolsa por
  partes, se ajustará.
- **Intereses por adelantado** (descontados del desembolso). Sin recurso van a
  gasto; con recurso se difieren en 3731 si la cuenta está configurada (si se
  deja vacía, van a gasto).
- **Comisión y gastos** sin factura del factor. Si el factor factura la comisión
  con IGV (crédito fiscal), conviene registrar esa factura de proveedor aparte
  y dejar aquí la comisión en 0.
- **Moneda**: una por operación, la de sus facturas (soles o dólares).
- **El factor cobra al cliente**: la empresa registra el «Cobro del factor»
  cuando el factor le informa el pago.
- **CAVALI**: solo se guarda el número de anotación; sin integración con su API.
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

`tests/test_factoring.py` (11): flujo sin recurso completo (factura pagada,
retenido, asientos cuadrados), con recurso cobrado (obligación, devengo y cierre
de intereses), con recurso recomprado (factura otra vez pendiente), no ceder dos
veces y cancelación, nominal mayor que el saldo, cargos mayores que el adelanto,
creación desde la lista, moneda extranjera, multicompañía y formulario.

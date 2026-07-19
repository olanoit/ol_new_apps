# Plan de desarrollo — `al_l10n_pe_retention`

> Planificación del módulo de **Régimen de Retenciones del IGV** (R.S.
> 037-2002/SUNAT) para Odoo 19, siguiendo los lineamientos de los módulos
> AL (app única Perú, `al_account_base`, versión `N.AAAAMMDD`, tests en
> `ol_pe_v19`, guía funcional).
> Fecha: 2026-07-19 · Branch: `19.0`.

## 1. Marco normativo (documentación oficial SUNAT)

Fuente: <https://emprender.sunat.gob.pe/principales-impuestos/impuesto-general-las-ventas-igv/regimen-retencion-igv>

- **Tasa**: 3 % del importe total de la operación gravada (R.S. 033-2014).
- **Ámbito**: ventas de bienes, primera venta de inmuebles, servicios y
  contratos de construcción gravados con IGV, cuando el importe supera
  **S/ 700**.
- **Momento**: la retención se efectúa **en cada pago** (en pagos parciales
  se retiene el 3 % de cada cuota), independiente de la fecha de emisión.
- **Excepciones**: proveedores «buenos contribuyentes», operaciones entre
  agentes de retención, boletas sin derecho a crédito fiscal, operaciones
  con **SPOT (detracción)**, operaciones con agentes de percepción, etc.
- **Obligaciones del agente**: emitir **Comprobante de Retención
  Electrónico (CRE)** — obligatorio desde 01/01/2018 —, declarar y pagar
  con el formulario 626, llevar el **Registro del Régimen de
  Retenciones** y usar la cuenta «IGV – Retenciones por pagar» (4011x).
- **Proveedor retenido**: aplica las retenciones sufridas contra su IGV
  por pagar (o pide devolución); las controla en la cuenta 40114.

## 2. Análisis de las versiones existentes

| Fuente | Qué aporta | Qué se descarta |
|---|---|---|
| **v17 `ce17/al/thinksh/al/l10n_pe_retention`** (proceso completo) | Modelo de proceso: retención por pago (parciales incluidos, `_is_final_payment`), `account.retention` (una por pago), **comprobante** `voucher.retention` con líneas/secuencia/PDF/email, asiento de reclasificación conciliado con la factura, configuración compañía (agente, %, mínimo, diarios/cuentas, partner SUNAT) y **doble rol** (compras: retenemos; ventas: nos retienen), flags de partner (agente / buen contribuyente) | Implementación pre-v19: asientos manuales por pago y hooks frágiles en `action_post`; en v19 el cálculo al pagar lo resuelve el framework nativo |
| **v18 `ce18/.../al_l10n_pe_edi_withholding`** (incompleto) | Referencia del **CRE**: plantillas UBL `Retention` y reporte PDF; catálogo de configuración | Flujo incompleto; no genera el proceso contable |
| **Nativo v19 `l10n_account_withholding_tax`** (base elegida) | Retenciones **en el pago**: impuestos con `is_withholding_tax_on_payment` (monto negativo), líneas de retención en el wizard de pago y en el pago, **secuencia propia** del número de retención, asiento integrado al pago | — (es la base; el módulo agrega las reglas peruanas encima) |

Regla de la línea AL: **no duplicar lo nativo** — el módulo configura y
automatiza el framework de Odoo, igual que `al_l10n_pe_detraction` hace
con el SPOT nativo.

## 3. Arquitectura propuesta

```
al_l10n_pe_retention/
├── __manifest__.py        # depends: al_account_base, l10n_account_withholding_tax,
│                          #          l10n_pe (impuestos), l10n_pe_reports (PLE 8.1 marca)
├── models/
│   ├── res_company.py     # agente de retención, tasa (3), mínimo (700),
│   │                      # impuesto de retención (compras), cuenta 4011x,
│   │                      # secuencia CRE (R###-########)
│   ├── res_partner.py     # es agente de retención / buen contribuyente
│   ├── account_move.py    # l10n_pe_retention_applies (computado): agente +
│   │                      # >S/700 + no excepciones (detracción, agente-agente,
│   │                      # buen contribuyente, boleta) + retenciones sufridas (ventas)
│   └── account_payment*.py# inyección automática de la línea de retención
│                          # en el wizard de pago cuando la factura aplica
├── wizards/               # (fases posteriores)
├── report/                # PDF del comprobante de retención (formato v17)
├── data/                  # impuesto retención IGV 3% (is_withholding_tax_on_payment)
│                          # + secuencia R001
├── docs/retenciones.md    # guía funcional (enlazada a la app Perú)
├── tools/                 # datos demo + validación (patrón detracción)
└── tests/
```

## 4. Fases

| Fase | Contenido | Entregable |
|---|---|---|
| **0** ✅ 2026-07-19 | Config + aplicabilidad: campos de compañía/ajustes Perú (agente, tasa, mínimo, impuesto, cuenta), flags de partner, cómputo `l10n_pe_retention_applies` en factura con TODAS las excepciones SUNAT (incl. detracción vía `al_l10n_pe_detraction` si está instalado), indicador visual | Módulo instala; tests de aplicabilidad |
| **1** ✅ 2026-07-19 | Retención en el pago (compras): inyectar la línea de retención nativa al registrar pagos de facturas que aplican (3 % de **cada pago**, redondeo), numeración con secuencia; validar excepciones al vuelo | Pago con retención asentado y numerado; tests de pagos parciales |
| **2** ✅ 2026-07-19 (retenciones sufridas; PDF/email del comprobante pendiente) | Comprobante de Retención (PDF formato SUNAT, basado en v17) + envío por correo + registro «Retenciones sufridas» (ventas: cliente agente nos retiene → asiento a 40114 conciliado) | PDF + flujo ventas; tests |
| **3** ✅ 2026-07-19 (XML base sin firma/envío OSE) | **CRE XML UBL** (plantillas v18 como referencia, infraestructura `l10n_pe_edi`) y estado de envío | XML válido; tests |
| **4** ✅ 2026-07-19 (marca 8.3 + resumen 626; PDF y 8.1 EE pendientes) | Reportes: TXT del **Registro del Régimen de Retenciones**, resumen para F. 626, marca de retención en PLE 8.1/8.3 (campo 26/34) | TXT/consultas; docs |
| **5** ✅ 2026-07-19 | Datos demo + validación integral en `ol_pe_v19` (`pe.cfg`), guía funcional en la app Perú, commit | 100 % validaciones |

## 5. Decisiones de diseño

- **Impuesto nativo** `-3 %` tipo retención (grupo IGV) creado por data,
  asignado en la compañía: el asiento del pago lo hace el framework
  (neto al proveedor + retención a la cuenta 4011x), sin asientos
  manuales ni re-balanceos.
- **Aplicabilidad centralizada** en `account.move` (mismo patrón que
  `l10n_pe_detraction_applies`): agente activo + total > mínimo +
  ninguna excepción; la excepción por SPOT consulta
  `l10n_pe_detraction_applies` solo si el módulo de detracciones está
  instalado (dependencia opcional vía `hasattr`).
- **Ventas (retenciones sufridas)**: modelo ligero de captura del
  comprobante recibido (número R###, fecha, monto) que genera el asiento
  40114 contra el cliente y se concilia — reemplaza el flujo espejo v17.
- **PLE**: el agente marca la retención en el Registro de Compras
  (campo 34 del 8.1 / 26 del 8.3) — integración con los exportadores
  existentes.

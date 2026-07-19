# Guía funcional — SIRE (RVIE / RCE)

> Para el **consultor funcional**. Explica cómo conciliar los registros de
> ventas (RVIE) y compras (RCE) del SIRE de SUNAT con los comprobantes de Odoo.

## Mapa del menú → guía

| Menú | Guía |
| --- | --- |
| Perú → SIRE → Ventas (RVIE) | [guia_sire.md](guia_sire.md) |
| Perú → SIRE → Compras (RCE) | [guia_sire.md](guia_sire.md) |
| Perú → Configuración → SIRE: campos de comparación | [guia_sire.md § Campos de comparación](guia_sire.md#campos-de-comparación) |
| Ajustes → Contabilidad (PE) → API SIRE (SUNAT) | [guia_sire.md § Configuración](guia_sire.md#configuración) |

## Conceptos comunes

- **SIRE**: plataforma de SUNAT que reemplaza al PLE para los registros de
  ventas (14.x) y compras (8.x). SUNAT propone el registro a partir de los CPE;
  el contribuyente acepta, complementa o reemplaza y luego genera el registro.
- **Propuesta**: TXT que SUNAT genera por periodo con todos los comprobantes
  que conoce. El módulo la descarga vía API (ticket asíncrono) o admite el TXT
  exportado a mano desde SOL.
- **CAR SUNAT**: clave única del comprobante (`RUC + tipo + serie + número`).
  Es la llave con la que se cruza la propuesta contra Odoo.
- **Estados de comparación**: `Correcto` (todo cuadra), `No cuadran` (mismo CAR
  con importes/datos distintos — el detalle indica cada campo), `Solo en SIRE`
  (SUNAT lo tiene y Odoo no), `Solo en Sistema` (Odoo lo tiene y SUNAT no).
- **Requisito**: RUC de 11 dígitos en la compañía; facturas con tipo de
  documento SUNAT (l10n_latam) e IGV configurado con afectaciones PE.

Guías de módulos hermanos: [detracciones](../../al_l10n_pe_detraction/docs/),
[retenciones](../../al_l10n_pe_retention/docs/), [PLE](../../al_l10n_pe_ple/docs/).

# PE - Depósitos a plazo y garantías (AL)

Módulo `al_l10n_pe_term_deposit`. Lleva el dinero inmovilizado de la empresa con
su contabilidad: depósitos a plazo, fondos en garantía y depósitos en garantía
entregados (p. ej. el del alquiler de una oficina o un almacén).

Menú *Perú ▸ Tesorería ▸ Depósitos y garantías* (y *Análisis de depósitos*).
Cuentas en *Perú ▸ Configuración ▸ Cuentas de la localización ▸ Depósitos y
garantías*; aviso de vencimiento en *Ajustes ▸ Perú ▸ Depósitos y garantías*.

## Tipos y cuentas (PCGE por defecto)

| Tipo | Cuenta del depósito | Intereses por cobrar | Ingreso |
|---|---|---|---|
| Depósito a plazo | 1062 Depósitos a plazo | 1631 Intereses | 7721 Rendimientos de depósitos |
| Fondo en garantía | 1071 Fondos en garantía | 1631 | 7721 |
| Depósito en garantía entregado | 1643 Depósitos en garantía (alquileres) | 1631 | 7721 |

Se configuran por tipo y moneda (la fila sin moneda vale para todas).

## Intereses

Con la **TEA** y la base de días (360 o 365):
`interés = capital × ((1 + TEA)^(días / base) − 1)`.

- **Devengo mensual automático:** un cron diario devenga hasta el cierre del
  mes anterior; es idempotente (solo registra lo que falta). Botón
  **Devengar intereses** para hacerlo a la fecha.
- Nunca se devenga más allá del vencimiento.

## Flujo y asientos

Ejemplo: depósito de S/ 100 000 al 6 % TEA, base 360, 180 días
(interés del plazo S/ 2 956,30).

| Paso | Debe | Haber |
|---|---|---|
| Abrir | 1062 (banco emisor) 100 000 | Banco 100 000 |
| Devengo de cada mes | 1631 | 7721 |
| Cancelar al vencimiento | Banco 102 956,30 | 1062 100 000 · 1631 2 956,30 |
| Cancelación anticipada (cobra menos) | Banco + 7721 (ajuste) | 1062 · 1631 |
| Renovar capitalizando | 1062 (nuevo) 102 956,30 | 1062 (anterior) 100 000 · 1631 2 956,30 |
| Renovar sin capitalizar | 1062 (nuevo) 100 000 · Banco 2 956,30 | 1062 (anterior) 100 000 · 1631 2 956,30 |
| Liberar garantía (parcial o total) | Banco | 1643 / 1071 |

Estados: Borrador → Vigente → Vencido → Cancelado / Renovado. El cron marca
como vencidos los depósitos al llegar la fecha (o los renueva solos si tienen
**Renovación automática**) y crea una actividad para el responsable unos días
antes (Ajustes ▸ Perú ▸ Aviso de vencimiento, 7 por defecto).

## Supuestos

- Los intereses se calculan sobre el saldo vigente: en una garantía con
  intereses y liberaciones parciales es una aproximación.
- Sin retención de impuestos sobre los intereses ni diferencia de cambio de los
  depósitos en moneda extranjera (cada apunte se convierte a su fecha).
- La renovación reutiliza las cuentas, el banco y la entidad del depósito.

## Pruebas

`tests/test_term_deposit.py`: apertura, interés con TEA y base de días, devengo
mensual idempotente, cron (devengo, aviso y vencimiento), cancelación al
vencimiento y anticipada, renovación con y sin capitalizar, renovación
automática, garantía liberada en dos partes, reglas, asistente y multicompañía.

Datos de demostración: `tools/term_deposit_demo_data.py` (prefijo «DEMO DEP»).

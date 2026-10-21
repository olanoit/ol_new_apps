---
modulos: [al_l10n_pe_payment_term_currency]
---

# Cuota fija en soles

En Odoo, el importe de una cuota fija de un plazo de pago está en la **moneda de la
factura**: un plazo «S/ 1 500 a los 15 días y saldo a 30 días» aplicado a una factura en
dólares pediría **US$ 1 500**. El módulo **Cuota fija en soles**
(`al_l10n_pe_payment_term_currency`) permite pactar esa cuota en soles.

## Configuración

En **Contabilidad ‣ Configuración ‣ Plazos de pago**, abra el plazo y, en la cuota de
importe fijo, marque **En soles**.

## Cómo se calcula

- En una factura en **dólares** (u otra moneda), la cuota marcada vale el importe en soles
  convertido al **tipo de cambio de la propia factura**. La última cuota, el saldo,
  absorbe la diferencia.
- En una factura en **soles** no cambia nada.
- La marca no afecta a la última cuota: siempre es el saldo.

### Ejemplo

Factura de US$ 2 360,00 al tipo de cambio 3,45 con el plazo «S/ 1 500 a los 15 días y
saldo a 30 días»:

| Cuota | US$ | S/ |
|---|---|---|
| 1 (15 días) | 434,78 | 1 500,00 |
| 2 (30 días, saldo) | 1 925,22 | 6 642,00 |

El comprobante electrónico informa las cuotas en dólares, la moneda de la factura, y su
suma es igual al total.

!!! note "Detracciones"
    La cuota de detracción en soles de una factura en dólares la separa el módulo de
    [Detracciones](../fiscal_localizations/peru/detractions.md); no hace falta marcarla
    aquí.

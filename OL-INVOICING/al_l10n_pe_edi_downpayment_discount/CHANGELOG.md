Historial de cambios — PE - Anticipos y descuentos globales en el CPE (AL)
==========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_edi_downpayment_discount.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 2.20261007 — 07/10/2026

- Corregido: un anticipo con una nota de crédito parcial dejaba de citarse en la factura final y SUNAT la rechazaba; solo se excluye el anticipo revertido por completo.
- Vuelve a bloquearse la nota de crédito con cantidad negativa e importe positivo, que SUNAT rechaza (las deducciones de anticipo siguen permitidas).

## 1.20261006 — 06/10/2026

- Primera versión: anticipos exonerados e inafectos (05/06), una referencia por comprobante de anticipo, descuento global de partes no gravadas como descuento de línea y notas de crédito y débito con anticipos o descuentos.

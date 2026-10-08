Historial de cambios — Planillas Perú - Contabilización (AL)
============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_account.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 7.20261008 — 08/10/2026

- Métodos de botón con la convención de Odoo (action_load_provisions, action_open_move_wizard, action_generate_move, action_open_move); el asiento se abre con el ícono de Odoo (fa-bars).

## 6.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.

## 5.20261007 — 07/10/2026

- Corregido: si la nómina estándar ya había contabilizado las boletas una por una, el asiento peruano del lote duplicaba el gasto; ahora lo impide y explica cómo configurarlo.

## 4.20260816 — 27/09/2026

- Los asientos de CTS, gratificación, liquidación y provisiones usan siempre las cuentas de la compañía del documento, aunque la compañía activa sea otra; y configurar los parámetros de una compañía ya no cambia las cuentas de otra.
- El «ajuste por redondeo» solo admite descuadres de céntimos: si falta una cuenta de cargo o de abono, el asiento avisa en lugar de mandar la diferencia a la cuenta de ajuste.
- El asiento del lote solo contabiliza boletas validadas o pagadas y avisa si quedan boletas en borrador.
- El asiento de beneficios sociales se calcula en el momento de generarlo, con los importes vigentes, y puede generarlo el personal de nómina sin permisos contables.

## 18/08/2026

- El menú pasa a llamarse Contabilidad y se ordena al final del flujo de Nómina.

## 2.20260722 — 25/07/2026

- Primera versión en Odoo 19: asiento de planilla por lote por ORM, asientos de beneficios sociales y analítica nativa opcional.

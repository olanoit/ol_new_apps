Historial de cambios — PE - OSE The Factory HKA (AL)
====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_ose_factory_hka.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 1.20261009 — 09/10/2026

- Migrado de 17.0 (al_ose_factory_hka y al_ose_factory_hka_retention, unificados): The Factory HKA como operador de l10n_pe_edi con los servicios comunes de Odoo 19 (envío, consulta del CDR y comunicación de baja); el número del archivo en 8 dígitos; sin credenciales o sin WSDL de producción el comprobante queda pendiente con el motivo.
- Comprobante de retención (CRE) de al_l10n_pe_retention por HKA y su reversión desde el pago (resumen RR: envío del resumen y consulta del ticket).
- Funciones de Factory HKA en Ajustes: CRE por HKA y reversión del CRE, por compañía.

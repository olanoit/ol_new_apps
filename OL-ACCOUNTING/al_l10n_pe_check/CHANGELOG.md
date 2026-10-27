Historial de cambios — PE - Cheques recibidos y girados (AL)
============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_check.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 2.20261018 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 1.20261012 — 12/10/2026

- Diarios «Cheques de terceros» y «Cheques rechazados» y método «Cheques propios» en los bancos, con las cuentas 1033001, 1689001 y 1049001 del PCGE, al cargar el plan peruano o al instalar el módulo.
- Documento del emisor del cheque con RUC (dígito verificador), DNI o carné de extranjería.
- Fecha límite de presentación al cobro (Ley 27287), filtros de cheques vencidos y por cobrar en la semana, y aviso al depositar un cheque diferido o vencido.
- Atajos en la app Perú: Clientes ▸ Cobros ▸ Cheques de terceros y Proveedores ▸ Pagos ▸ Cheques propios.
- Datos de demostración en «PE Company» (solo en bases con datos de demostración): cuatro cheques de terceros y un cheque propio diferido.

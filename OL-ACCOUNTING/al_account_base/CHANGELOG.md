Historial de cambios — PE - Base Contabilidad (AL)
==================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_account_base.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 5.20261007 — 07/10/2026

- Factura: nuevas páginas «Facturación PE» y «Contabilidad PE», cada una con pestañas internas donde los módulos de la localización ponen sus datos (anclas l10n_pe_invoicing_notebook, l10n_pe_accounting_notebook y «Registros electrónicos»). «Contabilidad PE» no se muestra en ventas.

## 4.20260815 — 27/09/2026

- El botón **Restablecer a borrador** ya no aparece en los asientos bloqueados con hash ni en los comprobantes que exigen solicitar la anulación a SUNAT: allí el sistema lo rechazaba igualmente con un error.

## 3.20260815 — 14/09/2026

- Configuración de la app Perú en cinco secciones, con la nueva sección **Contabilidad** de atajos a la configuración nativa.
- Orden del primer nivel de la app: Tipo de cambio, Letras de cambio, Detracciones, Retenciones IGV, SIRE, Libros PLE, Kardex y Configuración.

## 2.20260815 — 18/08/2026

- Naturaleza del diario y exclusión de los libros electrónicos.
- Código SUNAT del banco y establecimiento anexo, con validación de formato.

## 1.20260717 — 19/07/2026

- Glosa en asientos y apuntes, menú raíz Perú y aplicación Perú en Ajustes.

# PE - Base Contabilidad (AL) — Odoo 19

Módulo **base y liviano** del que dependen las demás personalizaciones AL de la
localización contable peruana. Contiene únicamente lo **genérico y compartido**;
la lógica de negocio específica vive en los módulos que dependen de éste.

## Contenido

- **Glosa** (`l10n_pe_gloss`) en `account.move` y `account.move.line` — la
  descripción del asiento que exigen los libros/PLE peruanos. Se muestra junto
  a la referencia y, opcionalmente, por línea.
- **Menú raíz "Perú"** y su rama **Configuración** (con acceso al Plan
  contable). Es el punto de extensión donde otros módulos AL cuelgan sus menús.
- **Utilidad** `account.move.l10n_pe_is_pe()` — indica si el comprobante es de
  una compañía peruana.
- Muestra siempre el botón **"Restablecer a borrador"** en asientos
  cancelados/publicados.

## Depende de

`account`.

## Notas

Reemplaza a la versión previa de `al_account_base`, que arrastraba mucho código
muerto (campos sin uso, páginas y modelos vacíos, toggles sin efecto,
controladores comentados). Esta versión conserva solo lo útil y compartido.

Módulos que dependen de este: `al_account_destinations` (asiento de destino).

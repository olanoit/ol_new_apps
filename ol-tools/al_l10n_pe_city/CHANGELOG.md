Historial de cambios — PE - Datos de la ciudad
==============================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`). Este módulo no tiene ficha
en `docs/fichas/`: el historial se mantiene a mano.

Basado en `l10n_pe_city` de Laxicon Solution (LGPL-3): conserva esa licencia.

## 2.20260730 — 28/09/2026

- Ya no se instala como aplicación: es un módulo de datos.
- Fuera la comprobación de versión de Odoo al instalar (`pre_init_hook`), que el manifiesto ya garantiza.

## 27/08/2026

- Pruebas de los datos: ciudades cargadas, cada una con su departamento peruano, todos los departamentos cubiertos y ciudad obligatoria en las direcciones de Perú.

## 1.20260730 — 02/08/2026

- Primera versión: 421 ciudades del Perú (`res.city`) asociadas a su departamento; en las direcciones de Perú la ciudad se elige de la lista.

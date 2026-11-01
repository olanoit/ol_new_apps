Historial de cambios — Base Tier Validation
===========================================

Módulo de ForgeFlow y la Odoo Community Association (OCA), copiado **sin
modificar** del repositorio OCA/tier-validation (rama 19.0). El historial de
sus autores está en `readme/HISTORY.md`; aquí solo se registran las
incorporaciones a este repositorio.

## 20.0.1.3.2 — 01/11/2026

- Única diferencia con OCA: el ícono del tipo de actividad «Tier Validation Reminder» pasa de `fa-bell` a `notifications` (Odoo 20 usa nombres de Material Symbols), con migración para las bases instaladas.
- Tests adaptados a Odoo 20: corren como superusuario (`_test_user_groups = ()`, porque `BaseCommon` ahora usa un usuario interno común) y limpian la caché de permisos con `ir.access._clear_caches()` (ya no existe `registry.clear_cache()`).

## 19.0.1.3.1 — 01/10/2026

- Incorporado como dependencia de `al_construction_material_request` (aprobación por niveles del requerimiento de obra).

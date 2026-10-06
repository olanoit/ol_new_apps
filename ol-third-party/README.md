ol-third-party
==============

**Módulos de terceros.**

Para qué es esta carpeta
------------------------

Módulos de otros autores incluidos porque un módulo propio depende de ellos o porque el proyecto los usa y no están en los servidores de destino. Conservan su autoría, licencia y ficha. Si llevan cambios locales, estos se anotan como tales en su `CHANGELOG.md`.

Qué va aquí
-----------

- Dependencias directas de módulos propios (p. ej. `base_tier_validation` de OCA para `al_construction_material_request`).
- Utilidades de terceros que el proyecto usa (p. ej. `prt_report_attachment_preview` y `al_l10n_pe_city`, las ciudades del Perú de Laxicon Solution).

Qué no va aquí
--------------

- Cualquier módulo propio → su área.
- Copias adaptadas de un módulo de terceros (cambian de nombre y van a su área, como `al_pos_theme`).

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_city](al_l10n_pe_city/) | 2.20260730 | LGPL-3 | Datos de la ciudad
[base_tier_validation](base_tier_validation/) | 19.0.1.3.1 | AGPL-3 | Implement a validation process based on tiers.
[prt_report_attachment_preview](prt_report_attachment_preview/) | 19.0.1.0.1 | LGPL-3 | Preview reports and pdf attachments in browser instead of downloading them. Open Report or PDF Attachment in new tab instead of downloading.
[//]: # (end addons)

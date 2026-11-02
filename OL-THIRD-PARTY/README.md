OL-THIRD-PARTY
==============

**Módulos de terceros.**

Para qué es esta carpeta
------------------------

Módulos de otros autores incluidos porque un módulo propio depende de ellos o porque el proyecto los usa y no están en los servidores de destino. Conservan su autoría, licencia y ficha. Si llevan cambios locales, estos se anotan como tales en su `CHANGELOG.md`.

Qué va aquí
-----------

- Dependencias directas de módulos propios (p. ej. `base_tier_validation` de OCA para `al_construction_material_request`).
- Utilidades de terceros que el proyecto usa (p. ej. `prt_report_attachment_preview`).

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
[base_tier_validation](base_tier_validation/) | 20.0.1.3.2 | AGPL-3 | Implement a validation process based on tiers.
[prt_report_attachment_preview](prt_report_attachment_preview/) | 20.0.1.0.1 | LGPL-3 | Preview reports and pdf attachments in browser instead of downloading them. Open Report or PDF Attachment in new tab instead of downloading.
[purchase_request](purchase_request/) | 20.0.1.0.3 | LGPL-3 | Use this module to have notification of requirements of materials and/or external services and keep track of such requirements.
[purchase_tier_validation](purchase_tier_validation/) | 20.0.1.0.0 | AGPL-3 | Extends the functionality of Purchase Orders to support a tier validation process.
[queue_job](queue_job/) | 20.0.2.1.0 | LGPL-3 | Job Queue
[//]: # (end addons)

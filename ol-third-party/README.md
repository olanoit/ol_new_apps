ol-third-party
==============

**Módulos de terceros.**

Para qué es esta carpeta
------------------------

Módulos de otros autores incluidos porque un módulo propio depende de ellos y no están en los servidores de destino. Se copian **sin modificar**: conservan su autoría, licencia y ficha.

Qué va aquí
-----------

- Dependencias directas de módulos propios (p. ej. `base_tier_validation` de OCA para `al_construction_material_request`).
- Utilidades de terceros que el proyecto usa tal cual (p. ej. `prt_report_attachment_preview`).

Qué no va aquí
--------------

- Cualquier módulo propio o modificado → su área.
- Copias adaptadas de un módulo de terceros (cambian de nombre y van a su área, como `al_pos_theme`).

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[base_tier_validation](base_tier_validation/) | 19.0.1.3.1 | AGPL-3 | Implement a validation process based on tiers.
[prt_report_attachment_preview](prt_report_attachment_preview/) | 19.0.1.0.1 | LGPL-3 | Preview reports and pdf attachments in browser instead of downloading them. Open Report or PDF Attachment in new tab instead of downloading.
[//]: # (end addons)

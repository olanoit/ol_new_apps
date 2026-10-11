# Convenciones de Odoo 19

Reglas que siguen todos los módulos de la suite, además de las
[pautas de código de Odoo](https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html).

## API de Odoo 19

| Use | En lugar de |
|---|---|
| Vistas `<list>` | `<tree>` |
| `invisible="…"`, `readonly="…"` | `attrs`, `states` |
| `aggregator=` | `group_operator=` |
| `models.Constraint`, `models.Index` | `_sql_constraints` |
| `group_ids`, `res.groups.privilege` | `groups_id`, categorías de grupos |
| `_read_group` | `read_group` |
| `odoo-bin i18n export` | exportación desde la interfaz |
| OWL 2 con `static/src` en los bundles de `assets` | widgets antiguos |

## Datos y seguridad

- **ORM primero.** Si hace falta SQL, `odoo.tools.SQL` con parámetros; nunca
  SQL armado con f-strings, `%` o concatenación.
- **Accesos.** Todo modelo nuevo lleva su línea en `security/ir.model.access.csv`
  y, si tiene compañía, sus reglas por compañía.
- **Multicompañía.** `_check_company_auto = True`, `check_company=True` en las
  relaciones con modelos que tienen compañía y la compañía de solo lectura en
  las vistas. La prueba de control de `al_base_module_info` lo verifica en
  todos los módulos propios.
- **`sudo()`** solo con un comentario que lo justifique y una variable con el
  sufijo `_sudo`.
- **Controladores.** Revise `auth=`, `csrf` y que no expongan registros de
  otros.
- **Campos privados** de `hr.employee` y `res.users`: `groups=` en el campo y
  dentro del `arch` de las vistas heredadas.

## Manifiesto y textos

- Nombre técnico con prefijo `al_`; el módulo va en la carpeta de su área.
- `category`: `'<carpeta del área>/Apps'` (por ejemplo `'OL-INVENTORY/Apps'`).
- `version`: `N.AAAAMMDD`.
- Licencia OPL-1, salvo las excepciones de `scripts/areas.py`.
- Textos de origen en español, con solo la primera letra en mayúscula.
  Comentarios en español.

## Documentación

Todo módulo nuevo documenta su funcionalidad en una página de
[Documentación para usuarios](../applications/index.md), con `modulos:` en
su encabezado, y su `README.md` enlaza a esa página. Ver
[Aportando](../contributing/index.md).

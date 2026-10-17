---
modulos: [al_industry_base]
---

# Paquetes de industria

La carpeta `OL-INDUSTRIES/` reúne los paquetes por rubro, con el mismo modelo
que los paquetes de industria de Odoo (por ejemplo `pharmacy_retail`). Un
paquete casi no tiene código: sus **dependencias** instalan las aplicaciones
del rubro y sus **datos** dejan la base configurada. La guía de uso está en
[Industrias](../applications/industries/index.md).

## Estructura

```text
OL-INDUSTRIES/
├── al_industry_base/            modelo al.industry y menú Industrias
└── al_industry_<rubro>/
    ├── __manifest__.py          application: True, category OL-INDUSTRIES/Apps
    ├── data/
    │   ├── al_industry_data.xml   registro al.industry + <function> al instalar
    │   └── <rubro>_data.xml       grupos, categorías, etiquetas (noupdate)
    ├── demo/<rubro>_demo.xml      productos de ejemplo
    ├── models/                    solo si el rubro necesita campos propios
    ├── static/description/        icon.svg, icon.png e index.html (ficha)
    └── tests/
```

## Qué va en cada archivo

- **Dependencias**: los módulos de Odoo y de la suite del rubro, más
  `al_industry_base`. La funcionalidad vive en su área (`OL-POS/`,
  `OL-PROJECTS/`…); el paquete solo la instala y la configura.
- **`al_industry_data.xml`**: el registro `al.industry` con su `code`, la
  clase CIIU (`ciiu_code`) y, si el rubro usa el planificador de obra,
  `planner_profile_xmlid`. Dentro de `<data noupdate="1">`, la llamada que lo
  aplica a la compañía activa al instalar:

    ```xml
    <function model="al.industry" name="_apply_on_install"
              eval="['al_industry_pharmacy.industry_pharmacy']"/>
    ```

- **`<rubro>_data.xml`**: las opciones de Ajustes que el rubro necesita, como
  `implied_ids` de `base.group_user` (fuera de `noupdate`, como hace Odoo), y
  los datos de partida (categorías de producto, de caja o web y etiquetas)
  dentro de `noupdate`, para que el cliente pueda renombrarlos.

## Qué hace `al.industry`

`al.industry._apply(company)` solo completa lo que falta:

1. Si el RUC de la compañía no tiene actividad económica principal, crea la
   línea con la clase CIIU del catálogo de `l10n_pe_vat_sunat`.
2. Si hay perfil del planificador y la compañía no tiene uno, aplica su
   configuración (`construction.vertical.profile._apply_configuration`): etapas,
   parámetros, planes analíticos y plantilla de niveles. Los puentes no se
   instalan desde aquí porque ya son dependencias del paquete.
3. Anota la compañía en `company_ids`.

El catálogo es global (sin `company_id`), como los perfiles de vertical. Lo que
es de cada compañía queda en la propia compañía; las demás se configuran con
**Aplicar a la compañía activa**, que solo puede usar un administrador.

## Añadir una industria

1. Copie el paquete más parecido a `OL-INDUSTRIES/al_industry_<rubro>/` y
   ajuste el manifiesto: nombre `Industria: <Rubro> (AL)`, versión `1.AAAAMMDD`,
   licencia OPL-1. Si depende del planificador, use LGPL-3 y añada la
   excepción en `scripts/areas.py`.
2. Cambie el `al.industry`: código, CIIU (compruebe que la clase está en
   `l10n_pe.economic.activity.csv`) y perfil del planificador, si aplica.
3. Dibuje el ícono según las [convenciones](conventions.md) y genere el PNG.
4. Escriba las pruebas: el registro, `_apply` en una compañía nueva, los
   grupos y los datos de partida.
5. Escriba la ficha en `docs/fichas/al_industry_<rubro>.yml` y genere la ficha
   y el CHANGELOG. Añada la página del rubro en
   `content/applications/industries/` y en su `SUMMARY.md`, y su fila en el
   `README.md` de la carpeta.
6. Ejecute `python3 scripts/gen_addons_table.py --check`.

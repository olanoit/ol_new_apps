# Instalar la suite

La suite se distribuye como un repositorio con una carpeta por área de negocio.
Funciona sobre Odoo 19 Community y Enterprise; algunos módulos requieren
Enterprise (nómina, presupuestos analíticos, planificación).

## Configuración

### Rutas de los módulos

La raíz del repositorio no contiene módulos: cada área es una ruta del
`addons_path`. Con solo la raíz, Odoo no encuentra los módulos.

1. Clone el repositorio en el servidor, en la rama de la versión de Odoo
   (`19.0`).
2. Obtenga las nueve rutas:

    ```bash
    python3 scripts/addons_path.py /ruta/del/clon/ol_new_apps
    ```

3. Agréguelas al `addons_path` del archivo de configuración de Odoo, después de
   las rutas de Odoo y de Enterprise:

    ```ini
    addons_path = /opt/odoo/addons,
                  /opt/odoo/enterprise,
                  /ruta/ol_new_apps/OL-ACCOUNTING,
                  /ruta/ol_new_apps/OL-INVOICING,
                  /ruta/ol_new_apps/OL-PAYROLL,
                  /ruta/ol_new_apps/OL-POS,
                  /ruta/ol_new_apps/OL-INVENTORY,
                  /ruta/ol_new_apps/OL-PROJECTS,
                  /ruta/ol_new_apps/OL-INDUSTRIES,
                  /ruta/ol_new_apps/OL-TOOLS,
                  /ruta/ol_new_apps/OL-THIRD-PARTY
    ```

4. Reinicie Odoo y, en **Aplicaciones**, haga clic en **Actualizar lista de
   aplicaciones** (modo desarrollador).

!!! note "Nota"
    En Odoo.sh, o donde `ol_new_apps` es un submódulo de otro repositorio, hay
    que agregar las mismas nueve carpetas.

### Dependencias de Python

Algunos módulos usan bibliotecas que no trae Odoo; el manifiesto de cada uno
las declara en `external_dependencies`. Instálelas en el entorno de Python del
servidor antes de instalar el módulo (por ejemplo `openpyxl` para los
importadores de Excel).

## Instalar los módulos

1. Active el modo desarrollador.
2. Vaya a **Aplicaciones** y filtre por la categoría del área (por ejemplo
   **OL-ACCOUNTING**).
3. Instale primero la localización peruana oficial de Odoo (`l10n_pe`,
   `l10n_pe_edi`) si la compañía es peruana, y después los módulos de la suite
   que necesite: cada uno instala sus dependencias.

!!! tip "Consejo"
    El botón **Ver la ficha completa del módulo** de cada tarjeta muestra qué
    hace, con capturas. La documentación funcional de cada uno está en
    [Documentación para usuarios](../applications/index.md).

!!! info "Ver también"
    - [Instalación de Odoo](https://www.odoo.com/documentation/19.0/es_419/administration/on_premise.html)
    - [Actualizar módulos](upgrade.md)

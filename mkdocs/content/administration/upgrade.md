# Actualizar módulos

Cada cambio en un módulo sube su versión. Para que una base lo tome, hay que
actualizar el módulo en esa base y reiniciar Odoo.

## Conceptos

- **Versión** `N.AAAAMMDD`: contador del módulo y fecha del cambio. Odoo la
  muestra como `19.0.N.AAAAMMDD`.
- **Novedades**: el `CHANGELOG.md` de cada módulo y las
  [novedades de la suite](../applications/novedades.md) dicen qué cambió en
  cada versión.

## Actualizar en un servidor

1. Traiga los cambios del repositorio (`git pull` en la rama de la versión).
2. Actualice los módulos que cambiaron en cada base:

    ```bash
    odoo -c <configuración> -d <base> -u <módulo1>,<módulo2> --stop-after-init
    ```

    Agregue `--i18n-overwrite` si cambiaron textos de la interfaz.

3. Reinicie el servicio de Odoo: los cambios de Python y los recursos nuevos
   (JavaScript, estilos) solo se cargan al arrancar.
4. Compruebe que el servicio responde (`/web/health`).

!!! warning "Importante"
    Actualice en una base de prueba antes que en producción. Una actualización
    que falla a mitad puede dejar vistas antiguas activas; el error suele
    señalar otro archivo que el que lo causa.

!!! danger "Advertencia"
    Si los módulos están en una carpeta compartida que los contenedores copian
    al arrancar, todo lo que se escriba ahí como `root` debe quedar legible
    para el usuario de Odoo (`umask 022`). Un archivo sin permiso de lectura
    impide que Odoo arranque.

## Módulos nuevos

Un módulo nuevo aparece en **Aplicaciones** después de **Actualizar lista de
aplicaciones** (o `update_list` en la consola de Odoo). Instalarlo es una
decisión de cada base.

!!! info "Ver también"
    - [Servidores con Docker](servers.md)

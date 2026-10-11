# Servidores con Docker

Las instancias de Odoo de los clientes corren en contenedores Docker en un mismo
servidor. Esta página describe la organización; los datos de acceso no se
publican aquí.

## Organización

| Pieza | Qué es |
|---|---|
| Una instancia por proyecto y entorno | Contenedor `odoo19_<proyecto>_<entorno>` (por ejemplo desarrollo y producción), con sus bases con prefijo propio |
| PostgreSQL | Un contenedor compartido |
| nginx | Un contenedor que recibe todos los dominios, con certificados de Let's Encrypt renovados por un contenedor de certbot |
| Módulos compartidos | Un clon de cada repositorio de módulos montado en todas las instancias; el `addons_path` de cada una incluye las ocho áreas de la suite |
| Documentación | Contenedores propios del [sitio de documentación](documentation_site.md) |

## Comprobar el estado

- Cada instancia expone `/web/health`: responde `200` cuando el servidor está
  listo. No use `/web/login` para comprobarlo.
- Después de actualizar módulos, recree el contenedor de la instancia para
  que cargue el código nuevo.

!!! info "Ver también"
    - [Actualizar módulos](upgrade.md)

# Pruebas

## Probar un módulo

Las pruebas corren en bases de prueba (`test_<proyecto>_<módulo>`) o en la base
de desarrollo autorizada. Crear o borrar una base requiere confirmación.

```bash
.venv/bin/python odoo-bin -c <configuración> -d test_pe_<módulo> -i <módulo> \
  --test-enable --test-tags /<módulo> --stop-after-init --workers=0
```

- `-i` en una base nueva; `-u` en una base donde el módulo ya está instalado.
- Si el módulo no está instalado, `-u` ejecuta 0 pruebas y aun así termina
  bien: revise el resumen `N tests` del registro.
- Si corren varios servidores, use puertos libres (`--http-port`,
  `--gevent-port`).

## Cobertura

```bash
.venv/bin/python -m coverage run --source=<ruta del módulo> --omit='*/tests/*' \
  odoo-bin -c <configuración> -d test_pe_<módulo> -i <módulo> --test-enable \
  --test-tags /<módulo> --stop-after-init --workers=0
.venv/bin/python -m coverage report -m
```

## Controles de toda la suite

- **Multicompañía:** las pruebas de `al_base_module_info` revisan reglas por
  compañía y `check_company` en todos los módulos propios.
- **Etiquetas:** `docs/validacion/etiquetas_espanol.py` debe dar 0.
- **Documentación:** `mkdocs build --strict` sin advertencias.

!!! warning "Importante"
    Un archivo de pruebas que termina en un bucle sobre `dir(...)` no ejecuta
    lo que se le agregue después. Compruebe que el número de pruebas sube.

#!/usr/bin/env python3
"""Regenera las tablas «Módulos disponibles» del repositorio.

Recorre cada carpeta de área (ver ``scripts/areas.py``) buscando subcarpetas
con ``__manifest__.py`` y:

1. reemplaza, en el ``README.md`` de cada área, el bloque entre
   ``[//]: # (addons)`` y ``[//]: # (end addons)`` con la tabla
   módulo/versión/licencia/resumen de esa área;
2. reemplaza, en el ``README.md`` raíz, el bloque entre
   ``[//]: # (addons-all)`` y ``[//]: # (end addons-all)`` con todas las
   tablas agrupadas por área.

Todo se lee del manifiesto; nunca se escribe a mano (mismo patrón que la
herramienta ``oca-gen-addons-table`` de OCA).

Uso:
    python3 scripts/gen_addons_table.py           # actualiza los README
    python3 scripts/gen_addons_table.py --check   # solo comprueba (código 1 si hay cambios
                                                  # pendientes o módulos fuera de un área)
"""
import ast
import sys

from areas import AREAS, NO_AREAS, REPO_ROOT, THIRD_PARTY

START, END = '[//]: # (addons)', '[//]: # (end addons)'
ROOT_START, ROOT_END = '[//]: # (addons-all)', '[//]: # (end addons-all)'


def read_manifest(path):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            return ast.literal_eval(node)
    return {}


def build_table(area_dir, link_prefix=''):
    rows = []
    for module_dir in sorted(area_dir.iterdir()):
        manifest_path = module_dir / '__manifest__.py'
        if not module_dir.is_dir() or not manifest_path.exists():
            continue
        manifest = read_manifest(manifest_path)
        summary = ' '.join((manifest.get('summary') or manifest.get('name') or '').split())
        rows.append((module_dir.name, manifest.get('version', ''),
                     manifest.get('license', ''), summary.replace('|', '\\|')))
    if not rows:
        return '_Todavía no hay módulos en esta carpeta._'
    lines = ['módulo | versión | licencia | resumen', '--- | --- | --- | ---']
    lines += [f'[{name}]({link_prefix}{name}/) | {version} | {license_} | {summary}'
              for name, version, license_, summary in rows]
    return '\n'.join(lines)


def replace_block(text, start, end, body):
    if start not in text or end not in text:
        raise SystemExit(f'Faltan los marcadores {start} / {end}')
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return f'{before}{start}\n{body}\n{end}{after}'


def structure_errors():
    """Módulos en la raíz o en carpetas que no son áreas, y áreas sin README."""
    errors = []
    for path in sorted(REPO_ROOT.iterdir()):
        if not path.is_dir() or path.name.startswith('.') or path.name in NO_AREAS:
            continue
        if (path / '__manifest__.py').exists():
            errors.append(f'{path.name}: módulo en la raíz; muévalo a su área')
        elif path.name not in AREAS:
            errors.append(f'{path.name}/: carpeta que no es un área (ver scripts/areas.py)')
        elif path.name != path.name.lower() or not path.name.startswith('ol-'):
            errors.append(f'{path.name}/: las carpetas de área van en minúscula y con prefijo ol-')
    for area in AREAS:
        if not (REPO_ROOT / area / 'README.md').exists():
            errors.append(f'{area}/README.md: falta')
        if area in THIRD_PARTY:
            continue
        # La categoría del manifiesto es el nombre de la carpeta del área
        # ('Hidden' se respeta: oculta el módulo en Aplicaciones).
        for manifest_path in sorted((REPO_ROOT / area).glob('*/__manifest__.py')):
            category = read_manifest(manifest_path).get('category', '')
            if category not in ('Hidden', area):
                errors.append(f'{area}/{manifest_path.parent.name}: category «{category}», '
                              f'debe ser «{area}»')
    return errors


def main():
    check = '--check' in sys.argv
    errors = structure_errors()
    pending = []
    areas = [REPO_ROOT / a for a in AREAS if (REPO_ROOT / a).is_dir()]
    for area_dir in areas:
        readme = area_dir / 'README.md'
        if not readme.exists():
            continue
        text = readme.read_text(encoding='utf-8')
        new = replace_block(text, START, END, build_table(area_dir))
        if new != text:
            pending.append(f'{area_dir.name}/README.md')
            if not check:
                readme.write_text(new, encoding='utf-8')
    root = REPO_ROOT / 'README.md'
    text = root.read_text(encoding='utf-8')
    body = '\n\n'.join(f'### {d.name}\n\n{build_table(d, link_prefix=f"{d.name}/")}' for d in areas)
    new = replace_block(text, ROOT_START, ROOT_END, body)
    if new != text:
        pending.append('README.md')
        if not check:
            root.write_text(new, encoding='utf-8')
    for error in errors:
        print(f'ERROR {error}')
    if check:
        for p in pending:
            print(f'desfasado {p}')
        sys.exit(1 if pending or errors else 0)
    print(f'Actualizado: {", ".join(pending)}' if pending else 'Sin cambios.')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()

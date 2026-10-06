#!/usr/bin/env python3
"""Genera el ``CHANGELOG.md`` de cada módulo desde la sección ``novedades`` de
su ficha (``docs/fichas/<módulo>.yml``), la misma que alimenta el historial de
``static/description/index.html``. Así el historial se escribe una sola vez.

Los módulos sin ficha (de terceros y algunas utilidades) mantienen su
``CHANGELOG.md`` a mano: el script no los toca.

Uso:
    python3 scripts/gen_changelog.py           # regenera los CHANGELOG.md
    python3 scripts/gen_changelog.py --check   # solo comprueba (sale con 1 si hay desfases)
"""
import ast
import sys

import yaml

from areas import AREAS, REPO_ROOT

FICHAS = REPO_ROOT / 'docs' / 'fichas'


class _Loader(yaml.SafeLoader):
    """Lee los números como texto: ``version: 4.20260810`` no debe perder el
    cero final al convertirse en float."""


_Loader.add_constructor('tag:yaml.org,2002:float', lambda loader, node: loader.construct_scalar(node))
_Loader.add_constructor('tag:yaml.org,2002:int', lambda loader, node: loader.construct_scalar(node))


def read_manifest(path):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            return ast.literal_eval(node)
    return {}


def build(module_dir, ficha):
    manifest = read_manifest(module_dir / '__manifest__.py')
    data = yaml.load(ficha.read_text(encoding='utf-8'), Loader=_Loader)
    entries = data.get('novedades') or []
    versions = {str(e['version']) for e in entries if e.get('version')}
    title = f"Historial de cambios — {manifest.get('name', module_dir.name)}"
    lines = [
        title, '=' * len(title), '',
        'Una entrada por versión publicada, la más reciente arriba; el número es',
        'el `version` de `__manifest__.py` (`N.AAAAMMDD`).', '',
        f'Generado desde `docs/fichas/{ficha.name}` (sección `novedades`) con',
        '`python3 scripts/gen_changelog.py`: no editar a mano.',
    ]
    for index, entry in enumerate(entries):
        version = str(entry.get('version') or '')
        # La entrada más reciente sin número es la versión actual del manifiesto.
        if not version and index == 0 and manifest.get('version') not in versions:
            version = manifest.get('version', '')
        heading = ' — '.join(filter(None, [version, str(entry.get('fecha') or '')]))
        lines += ['', f'## {heading}', '']
        lines += [f'- {" ".join(str(c).split())}' for c in entry.get('cambios') or []]
    return '\n'.join(lines) + '\n'


def main():
    check = '--check' in sys.argv
    pending = []
    for area in AREAS:
        for manifest_path in sorted((REPO_ROOT / area).glob('*/__manifest__.py')):
            module_dir = manifest_path.parent
            ficha = FICHAS / f'{module_dir.name}.yml'
            if not ficha.exists():
                continue
            target = module_dir / 'CHANGELOG.md'
            text = build(module_dir, ficha)
            if not target.exists() or target.read_text(encoding='utf-8') != text:
                pending.append(str(target.relative_to(REPO_ROOT)))
                if not check:
                    target.write_text(text, encoding='utf-8')
    if check and pending:
        for path in pending:
            print(f'DESFASADO {path}')
        sys.exit(1)
    print(f"{len(pending)} CHANGELOG.md {'desfasados' if check else 'actualizados'}.")


if __name__ == '__main__':
    main()

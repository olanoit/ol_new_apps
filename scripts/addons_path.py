#!/usr/bin/env python3
"""Imprime las rutas de las áreas para el ``addons_path`` de un servidor.

Los módulos viven en carpetas por área: cada una debe estar en el
``addons_path`` (la raíz del repositorio ya no contiene módulos).

Uso:
    python3 scripts/addons_path.py                       # rutas de este clon
    python3 scripts/addons_path.py /mnt/extra-addons/ol_new_apps   # base de otro servidor
    python3 scripts/addons_path.py --linea /ruta/base    # en una sola línea, separadas por coma
"""
import sys

from areas import AREAS, REPO_ROOT


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    base = (args[0] if args else str(REPO_ROOT)).rstrip('/')
    paths = [f'{base}/{area}' for area in AREAS]
    if '--linea' in sys.argv:
        print(','.join(paths))
    else:
        print(',\n'.join(paths))


if __name__ == '__main__':
    main()

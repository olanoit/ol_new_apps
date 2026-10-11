#!/usr/bin/env python3
"""Prepara una captura para la documentación, con las pautas de Odoo
(contributing/documentation/content_guidelines): como mucho 933 px de ancho,
PNG con paleta (el equivalente de pngquant) y nombre en minúsculas con
guiones, en la carpeta con el nombre de la página.

Uso:
    python3 mkdocs/scripts/preparar_imagen.py <origen.png> <destino.png> [--ancho 933] [--recorte x,y,ancho,alto]

Ejemplo:
    python3 mkdocs/scripts/preparar_imagen.py \\
        OL-ACCOUNTING/al_l10n_pe_detraction/static/description/screenshots/03-factura.png \\
        mkdocs/content/applications/finance/fiscal_localizations/peru/detractions/invoice-detraction.png
"""
import argparse
import re
from pathlib import Path

from PIL import Image

MAX_WIDTH = 933


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('origen')
    parser.add_argument('destino')
    parser.add_argument('--ancho', type=int, default=MAX_WIDTH)
    parser.add_argument('--recorte', help='x,y,ancho,alto en píxeles del original')
    args = parser.parse_args()

    dest = Path(args.destino)
    if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*\.png', dest.name):
        raise SystemExit('Nombre no válido: %s (minúsculas, números y guiones; .png)' % dest.name)
    image = Image.open(args.origen).convert('RGB')
    if args.recorte:
        x, y, w, h = (int(v) for v in args.recorte.split(','))
        image = image.crop((x, y, x + w, y + h))
    if image.width > args.ancho:
        image = image.resize((args.ancho, round(image.height * args.ancho / image.width)),
                             Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(
        dest, optimize=True)
    print('%s: %dx%d, %.0f KB' % (dest, image.width, image.height, dest.stat().st_size / 1024))


if __name__ == '__main__':
    main()

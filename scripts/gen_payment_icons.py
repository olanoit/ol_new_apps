#!/usr/bin/env python3
"""Íconos de las pasarelas de pago peruanas al estilo de Odoo.

Odoo dibuja dos imágenes por pasarela y las dos sirven de modelo aquí:

* ``static/img/<código>_icon.svg`` (lienzo 50 × 50) y su ``_icon.png`` de
  100 × 100: la marca centrada sobre fondo transparente, como
  ``payment_stripe`` o ``payment_mercado_pago``. Es la imagen del proveedor
  (``image_128``); el ícono del módulo en Aplicaciones es el isotipo de ALTA.
* Una tarjeta de 240 × 160 como las de ``payment/static/img`` (``visa.png``,
  ``paypal.png``): el logo sobre el color de la marca o sobre blanco. La usa
  ``al_pos_payment_gateway`` como imagen del método de pago del TPV
  (``static/img/<código>_pos.png``).

El SVG es la fuente y el PNG se genera con Chromium (Playwright). Culqi usa
el logo vectorial oficial (``culqi_logo.svg``, de culqi.com); Niubiz e Izipay
no publican uno, así que su SVG incrusta el logo en PNG del módulo
(``niubiz_logo.png``, ``izipay_logo.png``).

Uso::

    .venv/bin/python myodoo/ol_new_apps/scripts/gen_payment_icons.py
"""
import base64
import io
import re
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ACCOUNTING = ROOT / 'OL-ACCOUNTING'

NIUBIZ_NAVY = '#0F1B4C'
IZIPAY_RED = '#FF2D46'


def _png_data_uri(image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


def _svg(width, height, body):
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" '
            f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">{body}</svg>\n')


def _culqi_inner(prefix):
    """Contenido del logo oficial de Culqi (116 × 33) con ids propios, para
    poder ponerlo dos veces en distintos SVG sin choques."""
    source = (ACCOUNTING / 'al_payment_culqi/static/img/culqi_logo.svg').read_text()
    inner = re.sub(r'^<svg[^>]*>|</svg>\s*$', '', source.strip())
    return re.sub(r'(clip0|mask\d)_\d+_\d+', lambda m: f'{prefix}_{m.group(1)}', inner)


def _niubiz_white():
    """El logo de Niubiz con las letras en blanco (para el fondo azul); los
    dos puntos verdes se conservan."""
    image = Image.open(ACCOUNTING / 'al_payment_niubiz/static/img/niubiz_logo.png').convert('RGBA')
    pixels = image.load()
    for x in range(image.width):
        for y in range(image.height):
            r, g, b, a = pixels[x, y]
            if a and b > r and b > g and g < 120:  # azul de la marca
                pixels[x, y] = (255, 255, 255, a)
    return image


def build():
    niubiz = Image.open(ACCOUNTING / 'al_payment_niubiz/static/img/niubiz_logo.png').convert('RGBA')
    izipay = Image.open(ACCOUNTING / 'al_payment_izipay/static/img/izipay_logo.png').convert('RGBA')
    nw, nh = niubiz.size
    # Recuadro del logotipo de Izipay dentro de su cuadro de 256 px.
    ix0, iy0, ix1, iy1 = 55, 99, 200, 148
    icx, icy, iw = (ix0 + ix1) / 2, (iy0 + iy1) / 2, ix1 - ix0

    def izipay_image(width, center_x, center_y, logo_width):
        scale = logo_width / iw
        size = izipay.width * scale
        return (f'<image x="{center_x - icx * scale:.2f}" y="{center_y - icy * scale:.2f}" '
                f'width="{size:.2f}" height="{size:.2f}" href="{_png_data_uri(izipay)}"/>')

    def niubiz_image(uri, width, center_x, center_y):
        height = width * nh / nw
        return (f'<image x="{center_x - width / 2:.2f}" y="{center_y - height / 2:.2f}" '
                f'width="{width:.2f}" height="{height:.2f}" href="{uri}"/>')

    def culqi_group(prefix, width, center_x, center_y):
        scale = width / 116
        return (f'<g transform="translate({center_x - width / 2:.3f} {center_y - 33 * scale / 2:.3f}) '
                f'scale({scale:.5f})">{_culqi_inner(prefix)}</g>')

    return {
        # Íconos de 50 × 50 (Odoo: marca centrada, fondo transparente).
        'al_payment_niubiz/static/img/niubiz_icon.svg': _svg(
            50, 50, niubiz_image(_png_data_uri(niubiz), 44, 25, 25)),
        'al_payment_culqi/static/img/culqi_icon.svg': _svg(
            50, 50, culqi_group('icon', 46, 25, 25)),
        # Izipay se reconoce por su cuadro rojo: se conserva, con esquinas
        # redondeadas y el logotipo más grande.
        'al_payment_izipay/static/img/izipay_icon.svg': _svg(
            50, 50, '<clipPath id="r"><rect width="50" height="50" rx="9"/></clipPath>'
                    f'<g clip-path="url(#r)"><rect width="50" height="50" fill="{IZIPAY_RED}"/>'
                    f'{izipay_image(50, 25, 25, 42)}</g>'),
        # Tarjetas de 240 × 160 para el TPV (Odoo: payment/static/img).
        'al_payment_niubiz/static/img/niubiz_pos.svg': _svg(
            240, 160, f'<rect width="240" height="160" fill="{NIUBIZ_NAVY}"/>'
                      f'{niubiz_image(_png_data_uri(_niubiz_white()), 176, 120, 80)}'),
        'al_payment_culqi/static/img/culqi_pos.svg': _svg(
            240, 160, '<rect width="240" height="160" fill="white"/>' + culqi_group('pos', 184, 120, 80)),
        'al_payment_izipay/static/img/izipay_pos.svg': _svg(
            240, 160, f'<rect width="240" height="160" fill="{IZIPAY_RED}"/>{izipay_image(240, 120, 80, 172)}'),
    }


def render(svg_path, png_path, width, height):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
        page.set_content(
            '<html><body style="margin:0;background:transparent">'
            f'<img src="data:image/svg+xml;base64,{base64.b64encode(svg_path.read_bytes()).decode()}" '
            f'width="{width}" height="{height}" style="display:block"></body></html>')
        page.wait_for_timeout(200)
        page.screenshot(path=str(png_path), omit_background=True, clip={
            'x': 0, 'y': 0, 'width': width, 'height': height})
        browser.close()
    Image.open(png_path).save(png_path, optimize=True)


def main():
    for relative, content in build().items():
        svg_path = ACCOUNTING / relative
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(content)
        if svg_path.name.endswith('_icon.svg'):
            render(svg_path, svg_path.with_suffix('.png'), 100, 100)
        else:
            render(svg_path, svg_path.with_suffix('.png'), 240, 160)
        print('generado', svg_path.relative_to(ROOT), '+ png')


if __name__ == '__main__':
    main()

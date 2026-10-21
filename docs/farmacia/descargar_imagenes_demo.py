"""Descarga las fotos de los productos de la demo de farmacia.

Las fotos son reales y vienen de Wikimedia Commons con licencias libres
(dominio público, CC0, CC BY o CC BY-SA); se eligieron sin marcas legibles
cuando fue posible, porque las marcas de la demo son inventadas. La lista,
con autor y licencia, está en ``docs/farmacia/demo_images.json``.

Cada foto se guarda reducida (800 px de lado mayor, JPEG) en el módulo que
declara el producto, junto con un ``CREDITS.md`` con la atribución que exigen
las licencias CC BY y CC BY-SA.

Uso (desde la raíz del repositorio)::

    python3 docs/farmacia/descargar_imagenes_demo.py
"""
import http.client
import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCES = json.loads((Path(__file__).parent / 'demo_images.json').read_text(encoding='utf-8'))
UA = 'AltaLatamPharmacyDemo/1.0 (https://www.altabpo.com; olanoit@gmail.com)'
MAX_SIDE = 800
# Commons solo sirve miniaturas de anchos estándar (960 sí, 800 no).
THUMB_WIDTH = 960

# Módulo que declara cada producto (el resto está en al_pharmacy_base).
MODULES = {
    'product_morphine': 'OL-HEALTH/al_l10n_pe_pharmacy_controlled',
    **{key: 'OL-INDUSTRIES/al_industry_pharmacy' for key in (
        'product_sunscreen', 'product_moisturizer', 'product_toothpaste', 'product_hand_gel', 'product_alcohol',
        'product_diapers', 'product_baby_wipes', 'product_multivitamin', 'product_nutritional_shake',
        'product_thermometer', 'product_bp_monitor', 'product_glucose_strips', 'product_face_masks',
        'product_gauze')},
}
DEFAULT_MODULE = 'OL-HEALTH/al_pharmacy_base'


def module_of(xmlid):
    return MODULES.get(xmlid, DEFAULT_MODULE)


def image_path(xmlid):
    """Ruta relativa al módulo (para el atributo ``file`` de la demo)."""
    return f'static/img/demo/{xmlid}.jpg'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, http.client.HTTPException):
            time.sleep(3 + 5 * attempt)
    raise RuntimeError(f'No se pudo descargar {url}')


def thumb_url(source):
    """Miniatura de Commons del ancho pedido (evita bajar originales de 10 MB)."""
    url = source['url'].split('?', 1)[0]
    if '/commons/' in url and not url.endswith('.svg'):
        name = url.rsplit('/', 1)[1]
        head = url.replace('/commons/', '/commons/thumb/', 1)
        return f'{head}/{THUMB_WIDTH}px-{name}'
    return url


def main():
    credits = {}
    for xmlid, source in SOURCES.items():
        module = module_of(xmlid)
        target = ROOT / module / image_path(xmlid)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            try:
                data = fetch(thumb_url(source))
            except RuntimeError:
                data = fetch(source['url'].split('?', 1)[0])  # imágenes más angostas que MAX_SIDE: no hay miniatura
            image = Image.open(io.BytesIO(data)).convert('RGB')
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            image.save(target, 'JPEG', quality=85, optimize=True)
            time.sleep(0.5)
        credits.setdefault(module, []).append((xmlid, source))
    for module, items in credits.items():
        lines = ['# Créditos de las fotos de la demo', '',
                 'Fotos de Wikimedia Commons, reducidas a 800 px. Se usan según su licencia; '
                 'generadas por `docs/farmacia/descargar_imagenes_demo.py`.', '',
                 '| Archivo | Original | Autor | Licencia |', '|---|---|---|---|']
        for xmlid, source in sorted(items):
            artist = (source['artist'] or 'Desconocido').replace('|', '/').replace('\n', ' ')
            license_text = source['license']
            if source.get('license_url'):
                license_text = f"[{license_text}]({source['license_url']})"
            lines.append(f"| {xmlid}.jpg | [{source['title']}]({source['page']}) | {artist} | {license_text} |")
        (ROOT / module / 'static/img/demo/CREDITS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{len(SOURCES)} fotos en {len(credits)} módulos')


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Enlaces de una página de CAPECO o de la FTCCP que pueden ser la tabla salarial.

Solo decide qué vale la pena descargar. Qué convenio trae un PDF lo dice su
contenido: un enlace que resulte ser otra cosa no se importa.
"""
import re
import unicodedata
from urllib.parse import unquote, urljoin, urlparse, urlunparse

import lxml.html
from requests.utils import requote_uri

WAGE_WORDS = re.compile(r'tablas?\s*salarial|remuneraciones|jornal')
# La cartilla de derechos laborales también trae jornales, pero no es la tabla.
OTHER_WORDS = re.compile(r'cartilla|derechos\s*laborales')
AGREEMENT_WORDS = re.compile(r'(convencion|negociacion)\s*colectiva')
YEAR = re.compile(r'(?<!\d)(20\d{2})(?!\d)')


def _normalize(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[\s_\-.+]+', ' ', text.lower())


def _host(url):
    return (urlparse(url).hostname or '').lower().removeprefix('www.')


def find_links(content, base_url, target_year):
    """Devuelve ``(pdfs, páginas)``, sin repetir y en el orden de la página.

    Un enlace que nombra solo años anteriores a ``target_year`` se descarta. El
    año sale del nombre del archivo y del texto del enlace, no de la ruta: la
    FTCCP guarda sus archivos por fecha de publicación (``2025/12/30/…2026.pdf``).
    Un PDF sin año se conserva; una página sin año no, porque sería el menú.
    """
    if not content or not content.strip():
        return [], []
    tree = lxml.html.fromstring(content)
    pdfs, pages = [], []
    for anchor in tree.iter('a'):
        href = (anchor.get('href') or '').strip()
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        parts = urlparse(urljoin(base_url, href))
        if parts.scheme != 'https':
            continue
        url = requote_uri(urlunparse(parts._replace(fragment='')))
        name = unquote(parts.path.rstrip('/').rsplit('/', 1)[-1])
        label = _normalize('%s %s' % (name, anchor.text_content()))
        years = [int(year) for year in YEAR.findall(label)]
        if years and max(years) < target_year:
            continue
        if parts.path.lower().endswith('.pdf'):
            if WAGE_WORDS.search(label) and not OTHER_WORDS.search(label) and url not in pdfs:
                pdfs.append(url)
        elif (years and AGREEMENT_WORDS.search(label) and _host(url) == _host(base_url)
              and url not in pages):
            pages.append(url)
    return pdfs, pages

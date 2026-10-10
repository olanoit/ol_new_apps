#!/usr/bin/env python3
"""Verifica los enlaces http(s) de uno o varios Markdown (guías funcionales).

Uso: python3 docs/validacion/verificar_enlaces.py OL-*/*/GUIA_FUNCIONAL.md

Un enlace pasa si responde 2xx/3xx (se sigue la redirección). Algunos sitios
del Estado bloquean clientes automáticos: se prueba con cabeceras de
navegador y, si aun así responden 401/403/429, se informan como «bloqueado»
para revisarlos a mano (no cuentan como válidos). Sale con código 1 si hay
enlaces rotos o bloqueados.
"""
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL_RE = re.compile(r'https?://[^\s)\]>"\'`]+')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-PE,es;q=0.9',
}


def check(url):
    url = url.rstrip('.,;:')
    note = ''
    try:
        r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True, stream=True)
    except requests.exceptions.SSLError:
        # Algunos sitios del Estado no envían la cadena intermedia del
        # certificado: los navegadores la completan, requests no. Se reintenta
        # sin validar el certificado solo para saber si la página responde.
        try:
            r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True, stream=True,
                             verify=False)
            note = ' (certificado incompleto: abre en el navegador)'
        except requests.RequestException as exc:
            return url, 'error', type(exc).__name__
    except requests.RequestException as exc:
        return url, 'error', type(exc).__name__
    code = r.status_code
    r.close()
    if code < 400:
        return url, 'ok', '%s%s' % (code, note)
    if code in (401, 403, 429):
        return url, 'bloqueado', code
    return url, 'roto', code


def main(paths):
    urls = {}
    for path in paths:
        with open(path, encoding='utf-8') as fh:
            for url in URL_RE.findall(fh.read()):
                urls.setdefault(url.rstrip('.,;:'), set()).add(path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, sorted(urls)))
    bad = [r for r in results if r[1] != 'ok']
    for url, status, code in results:
        if status != 'ok' or 'certificado' in str(code):
            print('%-9s %-6s %s  (%s)' % (status, code, url, ', '.join(sorted(urls[url]))))
    print('%d enlaces, %d válidos, %d con problemas' % (len(results), len(results) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

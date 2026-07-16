# -*- coding: utf-8 -*-
"""Descarga y caché del padrón SUNAT (buenos contribuyentes /
agentes de retención).

SUNAT publica dos ZIPs grandes (~5-50 MB) con texto pipe-separado:

  * https://ww3.sunat.gob.pe/descarga/BueCont/BueCont_TXT.zip
    (buenos contribuyentes)
  * https://ww1.sunat.gob.pe/descarga/AgentRet/AgenRet_TXT.zip
    (agentes de retención)

La implementación original descargaba **todo el ZIP en cada apertura
de form de partner** — inaceptable a escala. Esta versión expone
``sync(env)`` que descarga una vez, persiste en
``l10n_pe.sunat.padron`` y permite consultas O(log n) por RUC.

El método ``is_good_taxpayer(env, ruc)`` / ``is_retention_agent(env,
ruc)`` consulta la caché. Si no hay datos (primera vez) o están
viejos, devuelve ``False`` y sugiere correr el cron.
"""
import io
import logging
from zipfile import BadZipFile, ZipFile

from . import http

_logger = logging.getLogger(__name__)


URLS = {
    'good_taxpayer':   'https://ww3.sunat.gob.pe/descarga/BueCont/BueCont_TXT.zip',
    'retention_agent': 'https://ww1.sunat.gob.pe/descarga/AgentRet/AgenRet_TXT.zip',
}


def sync(env, kinds=None):
    """Descarga los padrones SUNAT y los persiste en la caché.

    Args:
        env: ``odoo.api.Environment``.
        kinds: lista de claves de ``URLS`` a sincronizar. None = todas.

    Returns:
        dict ``{kind: n_records}`` con el conteo final por padrón.
    """
    kinds = kinds or list(URLS.keys())
    counts = {}
    Padron = env['l10n_pe.sunat.padron'].sudo()
    for kind in kinds:
        url = URLS[kind]
        try:
            rucs = _download_zip(url, service='SUNAT %s' % kind)
        except Exception as exc:
            _logger.exception(
                'No se pudo descargar el padrón %s: %s', kind, exc,
            )
            counts[kind] = 0
            continue

        # Truncar y recargar — más rápido que diff a esta escala.
        Padron.search([('kind', '=', kind)]).unlink()
        if rucs:
            # Crear en bloques para no hinchar la memoria.
            BLOCK = 5000
            for i in range(0, len(rucs), BLOCK):
                Padron.create([
                    {'kind': kind, 'vat': r} for r in rucs[i:i + BLOCK]
                ])
        counts[kind] = len(rucs)
        _logger.info('Padrón "%s" sincronizado: %d RUCs.', kind, len(rucs))
    return counts


def is_good_taxpayer(env, ruc):
    return _has_ruc(env, 'good_taxpayer', ruc)


def is_retention_agent(env, ruc):
    return _has_ruc(env, 'retention_agent', ruc)


def _has_ruc(env, kind, ruc):
    if not ruc:
        return False
    Padron = env['l10n_pe.sunat.padron'].sudo()
    return bool(Padron.search_count(
        [('kind', '=', kind), ('vat', '=', str(ruc).strip())],
    ))


# ---------------------------------------------------------------------- #
# Helpers internos                                                        #
# ---------------------------------------------------------------------- #

def _download_zip(url, service='SUNAT'):
    """Descarga el ZIP, descomprime el primer .txt y devuelve la lista
    de RUCs (primera columna pipe-separada).
    """
    r = http.get(url, service=service, retries=2, timeout=(10, 60))
    if r.status_code != 200:
        raise http.HttpError(
            'SUNAT respondió %s al descargar %s.' % (r.status_code, url),
            status_code=r.status_code, service=service,
        )

    try:
        with ZipFile(io.BytesIO(r.content)) as zf:
            name = zf.filelist[0].filename
            text = zf.read(name).decode('iso-8859-1')
    except BadZipFile as exc:
        raise http.HttpError(
            'ZIP corrupto desde %s' % url, service=service,
        ) from exc

    rucs = []
    for line in text.split('\r'):
        line = line.strip()
        if not line:
            continue
        parts = line.split('|')
        if not parts:
            continue
        ruc = parts[0].strip()
        if len(ruc) == 11 and ruc.isdigit():
            rucs.append(ruc)
    return rucs

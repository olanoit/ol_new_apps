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

# Campo del contacto que refleja cada padrón.
PARTNER_FIELDS = {
    'is_good_taxpayer': 'good_taxpayer',
    'is_retention_agent': 'retention_agent',
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
    # sudo(): el cron y el botón de administración recargan la caché, que
    # solo el administrador puede escribir.
    padron_sudo = env['l10n_pe.sunat.padron'].sudo()
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

        if not rucs:
            # Una descarga «correcta» sin RUCs (formato cambiado, HTML en
            # lugar de ZIP…) no debe vaciar la caché: se conserva la anterior.
            _logger.warning(
                'El padrón %s descargado no trae RUCs; se conserva la caché.',
                kind)
            counts[kind] = 0
            continue

        # Truncar y recargar — más rápido que diff a esta escala.
        padron_sudo.search([('kind', '=', kind)]).unlink()
        # Crear en bloques para no hinchar la memoria.
        BLOCK = 5000
        for i in range(0, len(rucs), BLOCK):
            padron_sudo.create([
                {'kind': kind, 'vat': r} for r in rucs[i:i + BLOCK]
            ])
        counts[kind] = len(rucs)
        _logger.info('Padrón "%s" sincronizado: %d RUCs.', kind, len(rucs))
        _refresh_partners(env, kind, set(rucs))
    return counts


def _refresh_partners(env, kind, rucs):
    """Actualiza la casilla del padrón en los contactos con RUC."""
    field_name = next(f for f, k in PARTNER_FIELDS.items() if k == kind)
    # sudo(): el cron recorre los contactos de todas las compañías.
    partners_sudo = env['res.partner'].sudo().with_context(active_test=False)
    # Los corregidos a mano no se tocan: el padrón puede ir por detrás de la
    # designación de SUNAT (antes se desmarcaban cada noche).
    partners_sudo = partners_sudo.search_fetch(
        [('vat', '!=', False), ('l10n_pe_padron_manual', '=', False)], ['vat', field_name])
    to_true = partners_sudo.filtered(
        lambda p: not p[field_name] and (p.vat or '').strip() in rucs)
    to_false = partners_sudo.filtered(
        lambda p: p[field_name] and (p.vat or '').strip() not in rucs)
    to_true.with_context(l10n_pe_padron_auto=True).write({field_name: True})
    to_false.with_context(l10n_pe_padron_auto=True).write({field_name: False})


def has_data(env, kind):
    """El padrón de ese tipo tiene filas (se descargó alguna vez)."""
    # sudo(): la caché es de solo lectura para todos; sudo evita reglas.
    return bool(env['l10n_pe.sunat.padron'].sudo().search_count(
        [('kind', '=', kind)], limit=1))


def is_good_taxpayer(env, ruc):
    return has_ruc(env, 'good_taxpayer', ruc)


def is_retention_agent(env, ruc):
    return has_ruc(env, 'retention_agent', ruc)


def has_ruc(env, kind, ruc):
    if not ruc:
        return False
    # sudo(): la caché del padrón es pública para consulta.
    padron_sudo = env['l10n_pe.sunat.padron'].sudo()
    return bool(padron_sudo.search_count(
        [('kind', '=', kind), ('vat', '=', str(ruc).strip())], limit=1,
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
    for line in text.splitlines():
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

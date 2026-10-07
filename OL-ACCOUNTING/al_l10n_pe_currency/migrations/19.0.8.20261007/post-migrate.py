# -*- coding: utf-8 -*-
"""Versión 8.

1. El cron del tipo de cambio pasa de diario a horario. El registro es
   ``noupdate``: cambiarlo en el XML solo alcanza a las bases nuevas. Con una
   corrida diaria, si caía antes de que SUNAT publicara, el día entero se
   facturaba con la tasa anterior.
2. Las tasas cargadas desde el BCRP se guardaban con la fecha del cierre SBS,
   un día hábil antes de la fecha en que SUNAT las publica. Se recarga ese
   rango con la equivalencia correcta, sin tocar las tasas manuales. Si el
   BCRP no responde, se deja constancia en el log para recargarlo a mano
   (Perú ▸ Tipo de cambio ▸ Actualizar tipo de cambio, fuente BCRP).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('al_l10n_pe_currency.cron_update_sunat_rate',
                   raise_if_not_found=False)
    if cron:
        cron.write({'interval_number': 1, 'interval_type': 'hours'})

    bcrp_rates = env['res.currency.rate'].search([('ref_origin', '=', 'bcrp')], order='name')
    if not bcrp_rates:
        return
    date_from, date_to = bcrp_rates[0].name, bcrp_rates[-1].name
    loaded = env['res.currency'].l10n_pe_update_range_bcrp(date_from, date_to, keep_manual=True)
    if loaded:
        _logger.info('al_l10n_pe_currency: %s fecha(s) del BCRP recargadas con la fecha '
                     'SUNAT (%s..%s).', loaded, date_from, date_to)
    else:
        _logger.warning('al_l10n_pe_currency: el BCRP no respondió; recargue a mano las '
                        'tasas del %s al %s (fuente BCRP): están un día hábil adelantadas.',
                        date_from, date_to)

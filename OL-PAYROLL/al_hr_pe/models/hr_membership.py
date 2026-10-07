# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import sbs_spp

_logger = logging.getLogger(__name__)


class HrMembership(models.Model):
    """Afiliación previsional (AFP/ONP) con sus tasas vigentes.

    Cambio de diseño vs v18: allí ``company_id`` era requerido y un wizard
    duplicaba las AFP en cada compañía (las tasas divergían y había que
    mantenerlas N veces). Las tasas AFP/ONP las fija la SBS — son
    nacionales — así que en v19 los registros son globales (override por
    compañía posible) y lo único realmente por compañía, la cuenta
    contable, es ``company_dependent``.
    """
    _name = 'hr.membership'
    _description = 'Afiliación (AFP/ONP)'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Entidad', tracking=True, required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: entidad global (tasas SBS compartidas). Con '
             'compañía: override propio.')
    fixed_commision = fields.Float(string='Comisión sobre flujo %', tracking=True)
    mixed_commision = fields.Float(string='Comisión mixta %', tracking=True)
    prima_insurance = fields.Float(string='Prima de seguros %', tracking=True)
    retirement_fund = fields.Float(string='Aporte fondo de pensiones %', tracking=True)
    insurable_remuneration = fields.Float(
        string='Remuneración máxima asegurable', tracking=True,
        help='Tope sobre el que se calcula la prima de seguro (lo publica '
             'la SBS trimestralmente).')
    account_id = fields.Many2one(
        'account.account', string='Cuenta contable',
        company_dependent=True,
        help='Cuenta del pasivo por aportes a esta entidad. Es por '
             'compañía: cada una configura la suya sobre el registro '
             'global.')
    is_afp = fields.Boolean(string='Es AFP', default=False, tracking=True)
    l10n_pe_sbs_period = fields.Char(
        string='Periodo SBS', readonly=True, tracking=True,
        help='Mes de devengue de la tabla de la SBS de la que salen las '
             'tasas actuales (actualización automática diaria).')

    # ------------------------------------------------------------------
    # Tasas desde la SBS
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_apply_sbs_rates(self, data):
        """Escribe las tasas leídas en las AFP globales (las de compañía
        son overrides a propósito y no se tocan). Devuelve las
        actualizadas."""
        updated = self.browse()
        afps = self.search([('is_afp', '=', True), ('company_id', '=', False)])
        for name, values in data['afp'].items():
            # «PRIMA» no debe casar con otras AFP ni con el tramo de
            # jubilados: se compara la última palabra del nombre.
            matches = afps.filtered(
                lambda afp: (afp.name or '').upper().split()[-1:] == [name]
                and 'JUB' not in (afp.name or '').upper())
            vals = {
                'fixed_commision': values['flow_commission'],
                'prima_insurance': values['prima_insurance'],
                'retirement_fund': values['retirement_fund'],
                'insurable_remuneration': values['insurable_remuneration'],
                'l10n_pe_sbs_period': data['period'],
            }
            for afp in matches:
                changed = {key: value for key, value in vals.items()
                           if afp[key] != value}
                if changed:
                    afp.write(changed)
                    updated |= afp
        return updated

    @api.model
    def _cron_l10n_pe_update_sbs_rates(self):
        data = sbs_spp.fetch_sbs_spp()
        if data:
            updated = self._l10n_pe_apply_sbs_rates(data)
            _logger.info('SBS %s: tasas actualizadas en %s AFP.',
                         data['period'], len(updated))

    def action_l10n_pe_update_sbs_rates(self):
        data = sbs_spp.fetch_sbs_spp()
        if not data:
            raise UserError(_(
                'No se pudo leer la tabla de comisiones de la SBS. Inténtelo '
                'más tarde o actualice las tasas a mano.'))
        updated = self._l10n_pe_apply_sbs_rates(data)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Tasas SBS %s', data['period']),
                'message': _('%s AFP actualizadas.', len(updated))
                if updated else _('Las tasas ya estaban al día.'),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

# -*- coding: utf-8 -*-
import logging

from odoo import fields, models
from odoo.exceptions import UserError

from . import cmp_client

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pharmacy_cmp_council = fields.Char(string='Consejo regional')

    def action_pharmacy_check_cmp(self):
        """Consulta el portal del Colegio Médico y actualiza el prescriptor."""
        # Parámetro técnico (URL del portal): lo lee cualquiera que consulte,
        # aunque solo el administrador pueda leer ir.config_parameter.
        config_sudo = self.env['ir.config_parameter'].sudo()
        base_url = config_sudo.get_param('al_l10n_pe_prescriber_cmp.base_url',
                                         cmp_client.DEFAULT_BASE_URL)
        for partner in self:
            code = (partner.pharmacy_prescriber_license or '').strip()
            if not code:
                raise UserError(self.env._('Escriba el número de colegiatura (CMP) de %s.',
                                           partner.name))
            try:
                data = cmp_client.fetch(code, base_url=base_url)
            except cmp_client.CmpError as error:
                _logger.warning('Consulta CMP %s: %s', code, error)
                raise UserError(self.env._(
                    'No se pudo consultar el Colegio Médico: %s. Registre los datos a mano.',
                    error)) from error
            if not data:
                raise UserError(self.env._('El Colegio Médico no tiene la colegiatura %s.', code))
            name = ' '.join(filter(None, (data.get('first_name'), data.get('last_name'))))
            partner.write({
                'name': name.title() if name else partner.name,
                'pharmacy_is_prescriber': True,
                'pharmacy_profession': 'physician',
                'pharmacy_prescriber_license': data.get('code') or code,
                'pharmacy_specialty': ', '.join(data.get('specialties') or []) or partner.pharmacy_specialty,
                'pharmacy_prescriber_status': data.get('status') or partner.pharmacy_prescriber_status,
                'pharmacy_cmp_council': data.get('council') or partner.pharmacy_cmp_council,
                'pharmacy_prescriber_checked': fields.Datetime.now(),
            })
        return True

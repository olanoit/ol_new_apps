# -*- coding: utf-8 -*-
"""Verificación del médico prescriptor en el Colegio Médico del Perú.

El portal «Conoce a tu médico» (https://conoceatumedico.cmp.org.pe, desde
2026) pide iniciar sesión y reCAPTCHA: no admite consultas automáticas. El
botón abre el portal para buscar la colegiatura y el químico farmacéutico
registra el resultado (hábil o inhábil), con fecha y responsable.
"""
from odoo import fields, models
from odoo.exceptions import UserError

DEFAULT_PORTAL_URL = 'https://conoceatumedico.cmp.org.pe/'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pharmacy_cmp_council = fields.Char(string='Consejo regional')
    pharmacy_prescriber_checked_by_id = fields.Many2one('res.users', string='Verificado por',
                                                        readonly=True)

    def action_pharmacy_open_cmp(self):
        self.ensure_one()
        if not (self.pharmacy_prescriber_license or '').strip():
            raise UserError(self.env._('Escriba primero el número de colegiatura (CMP).'))
        # Parámetro técnico (URL del portal): lo lee cualquiera que consulte,
        # aunque solo el administrador pueda leer ir.config_parameter.
        config_sudo = self.env['ir.config_parameter'].sudo()
        url = config_sudo.get_param('al_l10n_pe_prescriber_cmp.portal_url', DEFAULT_PORTAL_URL)
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def _pharmacy_set_cmp_status(self, status):
        if not self.env.user.has_group('al_pharmacy_base.group_pharmacy_pharmacist'):
            raise UserError(self.env._('Solo un químico farmacéutico registra la verificación.'))
        for partner in self:
            if not partner.pharmacy_prescriber_license:
                raise UserError(self.env._('%s no tiene colegiatura.', partner.name))
        self.write({
            'pharmacy_is_prescriber': True,
            'pharmacy_prescriber_status': status,
            'pharmacy_prescriber_checked': fields.Datetime.now(),
            'pharmacy_prescriber_checked_by_id': self.env.user.id,
        })
        return True

    def action_pharmacy_cmp_enabled(self):
        return self._pharmacy_set_cmp_status('enabled')

    def action_pharmacy_cmp_disabled(self):
        return self._pharmacy_set_cmp_status('disabled')

# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import UserError

from ..services import sunat_cpe

POST_MODES = [
    ('none', 'No consultar'),
    ('warn', 'Consultar y avisar'),
    ('block', 'Consultar y bloquear si no es válido'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Las credenciales son del RUC: las sucursales usan las de su compañía raíz.
    l10n_pe_cpe_client_id = fields.Char(
        string='Client ID (consulta de comprobantes)', groups='base.group_system',
        help='Generado en SUNAT Operaciones en Línea ▸ Credenciales de API SUNAT. Vacío: se usa '
             'el del SIRE.')
    l10n_pe_cpe_client_secret = fields.Char(
        string='Client secret (consulta de comprobantes)', groups='base.group_system')
    l10n_pe_cpe_token = fields.Char(groups='base.group_system', copy=False)
    l10n_pe_cpe_token_expiry = fields.Datetime(groups='base.group_system', copy=False)
    l10n_pe_cpe_post_mode = fields.Selection(
        POST_MODES, string='Al publicar una factura de proveedor', default='none', required=True,
        help='Consulta el comprobante en SUNAT al publicarlo: solo avisa en el historial o, '
             'además, impide publicarlo si SUNAT no lo da por válido.')

    def _l10n_pe_cpe_credentials(self):
        """``(client_id, client_secret)`` de la compañía raíz; si no los
        tiene, los del SIRE (al_l10n_pe_sire), sin copiarlos."""
        self.ensure_one()
        # sudo: credenciales técnicas de la compañía (grupo de sistema); las
        # usa la consulta que puede lanzar cualquier usuario de contabilidad.
        root_sudo = self.root_id.sudo()
        client_id = root_sudo.l10n_pe_cpe_client_id
        secret = root_sudo.l10n_pe_cpe_client_secret
        if not (client_id and secret) and 'l10n_pe_sire_client_id' in root_sudo._fields:
            client_id = root_sudo.l10n_pe_sire_client_id
            secret = root_sudo.l10n_pe_sire_client_secret
        if not (client_id and secret):
            raise UserError(self.env._(
                'Configure las credenciales de API SUNAT (client ID y client secret) en '
                'Ajustes ▸ Perú ▸ Consulta de comprobantes.'))
        return client_id, secret

    def _l10n_pe_cpe_get_token(self):
        """Token vigente de la compañía raíz, renovado un minuto antes de vencer."""
        self.ensure_one()
        # sudo: ver _l10n_pe_cpe_credentials.
        root_sudo = self.root_id.sudo()
        now = fields.Datetime.now()
        if root_sudo.l10n_pe_cpe_token and root_sudo.l10n_pe_cpe_token_expiry \
                and root_sudo.l10n_pe_cpe_token_expiry > now:
            return root_sudo.l10n_pe_cpe_token
        client_id, secret = self._l10n_pe_cpe_credentials()
        try:
            token, expires_in = sunat_cpe.get_token(client_id, secret)
        except sunat_cpe.SunatCpeError as exc:
            raise UserError(str(exc)) from exc
        root_sudo.write({
            'l10n_pe_cpe_token': token,
            'l10n_pe_cpe_token_expiry': now + timedelta(seconds=max(expires_in - 60, 60)),
        })
        return token

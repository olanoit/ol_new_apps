from odoo import _, fields, models

POST_CHECK_SELECTION = [
    ('none', 'No validar'),
    ('warn', 'Avisar en el comprobante'),
    ('block', 'Impedir la publicación'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Credenciales y token solo para administradores (como las credenciales
    # SOL de l10n_pe_edi): res.company la lee cualquier usuario interno. La
    # API las lee con sudo() en ``l10n_pe.sire.api``.
    l10n_pe_sire_sol_user = fields.Char(
        string='Usuario SOL (SIRE)', groups='base.group_system',
        help='Usuario secundario SOL autorizado para la API del SIRE. '
             'El nombre de usuario completo se forma como RUC + usuario.')
    l10n_pe_sire_sol_password = fields.Char(
        string='Clave SOL (SIRE)', groups='base.group_system')
    l10n_pe_sire_client_id = fields.Char(
        string='Client ID API SIRE', groups='base.group_system',
        help='Credencial generada en SOL: Empresas → Credenciales de API SUNAT.')
    l10n_pe_sire_client_secret = fields.Char(
        string='Client Secret API SIRE', groups='base.group_system')
    # Caché del token: un periodo encadena media docena de llamadas y no
    # tiene sentido abrir una sesión OAuth para cada una.
    l10n_pe_sire_token = fields.Char(
        string='Token SIRE', copy=False, groups='base.group_system')
    l10n_pe_sire_token_expiry = fields.Datetime(
        string='Caducidad del token SIRE', copy=False,
        groups='base.group_system')
    l10n_pe_sire_post_check = fields.Selection(
        POST_CHECK_SELECTION, string='Validar con las reglas del SIRE al publicar',
        default='warn',
        help='Revisa cada factura, boleta o nota con las mismas reglas que el '
             'registro SIRE (RUC, DNI, serie y número, nota sin documento '
             'modificado, boleta sobre S/ 700 sin cliente, IGV…) en el momento '
             'de publicarla, y no al cerrar el mes.')

    def write(self, vals):
        # Con otras credenciales el token guardado es de la cuenta anterior:
        # se descarta para que la próxima llamada pida uno nuevo.
        if {'l10n_pe_sire_sol_user', 'l10n_pe_sire_sol_password',
                'l10n_pe_sire_client_id', 'l10n_pe_sire_client_secret'} & set(vals):
            vals = dict(vals, l10n_pe_sire_token=False,
                        l10n_pe_sire_token_expiry=False)
        return super().write(vals)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_sire_sol_user = fields.Char(
        related='company_id.l10n_pe_sire_sol_user', readonly=False,
        groups='base.group_system')
    l10n_pe_sire_sol_password = fields.Char(
        related='company_id.l10n_pe_sire_sol_password', readonly=False,
        groups='base.group_system')
    l10n_pe_sire_client_id = fields.Char(
        related='company_id.l10n_pe_sire_client_id', readonly=False,
        groups='base.group_system')
    l10n_pe_sire_client_secret = fields.Char(
        related='company_id.l10n_pe_sire_client_secret', readonly=False,
        groups='base.group_system')
    l10n_pe_sire_post_check = fields.Selection(
        related='company_id.l10n_pe_sire_post_check', readonly=False)

    def action_l10n_pe_sire_test_connection(self):
        """Pide un token nuevo con las credenciales guardadas."""
        self.ensure_one()
        # sudo: credenciales y token son de base.group_system (el botón también).
        company_sudo = self.company_id.sudo().root_id
        company_sudo.write({'l10n_pe_sire_token': False, 'l10n_pe_sire_token_expiry': False})
        self.env['l10n_pe.sire.api']._sire_get_token(company_sudo)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('SUNAT aceptó las credenciales del SIRE de %(company)s; '
                             'el token vence el %(expiry)s.',
                             company=company_sudo.name,
                             expiry=fields.Datetime.context_timestamp(
                                 self, company_sudo.l10n_pe_sire_token_expiry
                             ).strftime('%d/%m/%Y %H:%M')),
            },
        }

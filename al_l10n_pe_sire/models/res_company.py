from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_sire_sol_user = fields.Char(
        string='Usuario SOL (SIRE)',
        help='Usuario secundario SOL autorizado para la API del SIRE. '
             'El nombre de usuario completo se forma como RUC + usuario.')
    l10n_pe_sire_sol_password = fields.Char(string='Clave SOL (SIRE)')
    l10n_pe_sire_client_id = fields.Char(
        string='Client ID API SIRE',
        help='Credencial generada en SOL: Empresas → Credenciales de API SUNAT.')
    l10n_pe_sire_client_secret = fields.Char(string='Client Secret API SIRE')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_sire_sol_user = fields.Char(
        related='company_id.l10n_pe_sire_sol_user', readonly=False)
    l10n_pe_sire_sol_password = fields.Char(
        related='company_id.l10n_pe_sire_sol_password', readonly=False)
    l10n_pe_sire_client_id = fields.Char(
        related='company_id.l10n_pe_sire_client_id', readonly=False)
    l10n_pe_sire_client_secret = fields.Char(
        related='company_id.l10n_pe_sire_client_secret', readonly=False)

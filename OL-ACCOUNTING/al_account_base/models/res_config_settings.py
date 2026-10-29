# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

#: Páginas del sitio de documentación (mkdocs/ del repositorio) a las que
#: llevan los accesos de Ajustes ▸ Perú ▸ Documentación.
DOCS_PAGES = {
    'home': '',
    'guides': 'applications/',
    'news': 'applications/novedades/',
    'accounting': 'applications/finance/fiscal_localizations/peru/',
    'payroll': 'applications/hr/payroll/peru/',
    'technical': 'developer/',
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    al_docs_url = fields.Char(
        string='URL de la documentación',
        config_parameter='al_account_base.docs_url',
        help='Dirección del sitio de documentación de la suite (MkDocs), con su '
             'versión si se publica con mike, p. ej. https://docs.ejemplo.pe/19.0/. '
             'Es la misma para todas las compañías.')

    @api.constrains('al_docs_url')
    def _check_al_docs_url(self):
        for settings in self:
            url = (settings.al_docs_url or '').strip()
            if url and not url.startswith(('http://', 'https://')):
                raise ValidationError(self.env._(
                    'La URL de la documentación debe empezar por http:// o https://.'))

    def action_al_docs_open(self):
        """Abre el sitio de documentación (o una de sus secciones, indicada en
        el contexto con ``al_docs_page``) en una pestaña nueva."""
        url = (self.env['ir.config_parameter'].sudo().get_str('al_account_base.docs_url')
               or '').strip()
        if not url:
            raise UserError(self.env._(
                'Escriba la URL de la documentación y guarde los ajustes.'))
        page = DOCS_PAGES.get(self.env.context.get('al_docs_page'), '')
        return {
            'type': 'ir.actions.act_url',
            'url': url.rstrip('/') + '/' + page,
            'target': 'new',
        }

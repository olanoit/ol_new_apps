# -*- coding: utf-8 -*-
from odoo import api, fields, models

#: Parámetro con la URL del sitio de documentación (lo edita Ajustes ▸ Perú ▸
#: Documentación de al_account_base); sin él, el sitio publicado de la suite.
DOCS_URL_PARAM = 'al_account_base.docs_url'
DOCS_URL_DEFAULT = 'https://docs.altalatam.com/latest/'


class AlDocsHelp(models.Model):
    """Pantalla de Odoo → sección de la guía funcional que abre su botón «?».

    Los registros los genera ``scripts/gen_docs_help.py`` desde el código de
    cada módulo y las páginas de la documentación que lo declaran
    (``modulos:``); los que se crean a mano (sin identificador externo) no se
    pisan al actualizar."""
    _name = 'al.docs.help'
    _description = 'Ayuda contextual'
    _order = 'module, key'

    key = fields.Char(
        string='Pantalla', required=True, index=True,
        help='Modelo de la vista o del asistente (p. ej. account.move) o «tag» de la '
             'acción de cliente.')
    kind = fields.Selection(
        [('model', 'Modelo'), ('tag', 'Acción de cliente')], string='Tipo',
        required=True, default='model')
    name = fields.Char(string='Descripción')
    module = fields.Char(
        string='Módulo', required=True,
        help='Módulo dueño de la guía; la ayuda solo se muestra si está instalado.')
    path = fields.Char(
        string='Ruta en la documentación', required=True,
        help='Ruta relativa al sitio, con el ancla de la sección: '
             'applications/services/project/construction/planning/import_master/')
    section = fields.Char(string='Sección')
    url = fields.Char(string='Enlace', compute='_compute_url')
    active = fields.Boolean(string='Activo', default=True)

    _key_unique = models.Constraint('UNIQUE(key)', 'Cada pantalla tiene una sola ayuda.')

    @api.model
    def _docs_base_url(self):
        # sudo: el parámetro del sistema lo leen todos los usuarios internos que
        # ven el botón «?»; solo es la URL pública del sitio, no un secreto.
        params_sudo = self.env['ir.config_parameter'].sudo()
        url = (params_sudo.get_param(DOCS_URL_PARAM) or DOCS_URL_DEFAULT).strip()
        return url.rstrip('/') + '/'

    @api.depends('path')
    def _compute_url(self):
        base = self._docs_base_url()
        for help_line in self:
            help_line.url = base + (help_line.path or '').lstrip('/')

    @api.model
    def get_help_map(self):
        """Mapa para el cliente web: ``{pantalla: {url, section}}`` de las
        ayudas activas cuyo módulo está instalado."""
        base = self._docs_base_url()
        installed = set(self.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))
        # sudo de ir.module.module arriba: los usuarios internos no leen la
        # lista de módulos; solo se usa para filtrar.
        return {
            line['key']: {'url': base + line['path'].lstrip('/'), 'section': line['section'] or ''}
            for line in self.search_read([], ['key', 'module', 'path', 'section'])
            if line['module'] in installed
        }

    def action_open(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.url, 'target': 'new'}

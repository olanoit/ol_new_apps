# -*- coding: utf-8 -*-
"""Aplicación web instalable del portal de obra (requerimiento CREVAL v1.0,
4.11): la página, su manifiesto (ícono en la pantalla de inicio, pantalla
completa y nombre de la empresa) y el service worker, servido desde
``/obra/app/`` para que su alcance sea el del portal."""
import json

from odoo import http
from odoo.http import request
from odoo.tools.misc import file_path

STATIC = '/al_construction_portal/static/app/'


class ConstructionPortalApp(http.Controller):

    def _company(self):
        # sudo: el nombre y el color de la empresa del sitio, públicos.
        return request.env['res.company'].sudo().search([], limit=1, order='id')

    @http.route(['/obra/app', '/obra/app/'], type='http', auth='public', methods=['GET'],
                sitemap=False)
    def app(self, **kw):
        company = self._company()
        return request.render('al_construction_portal.portal_app', {
            'company_name': company.name, 'color': company.primary_color or '#714B67',
            'static': STATIC})

    @http.route('/obra/app/manifest.webmanifest', type='http', auth='public', methods=['GET'],
                sitemap=False)
    def manifest(self, **kw):
        company = self._company()
        data = {
            'name': '%s · Portal de obra' % company.name,
            'short_name': 'Obra',
            'start_url': '/obra/app/',
            'scope': '/obra/app/',
            'display': 'standalone',
            'background_color': '#F2F3F5',
            'theme_color': company.primary_color or '#714B67',
            'lang': 'es',
            'icons': [
                {'src': STATIC + 'icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
                {'src': STATIC + 'icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
            ],
        }
        return request.make_response(json.dumps(data), headers=[
            ('Content-Type', 'application/manifest+json')])

    @http.route('/obra/app/sw.js', type='http', auth='public', methods=['GET'], sitemap=False)
    def service_worker(self, **kw):
        with open(file_path('al_construction_portal/static/app/sw.js'), encoding='utf-8') as fh:
            content = fh.read()
        return request.make_response(content, headers=[
            ('Content-Type', 'text/javascript'), ('Service-Worker-Allowed', '/obra/app/'),
            ('Cache-Control', 'no-cache')])

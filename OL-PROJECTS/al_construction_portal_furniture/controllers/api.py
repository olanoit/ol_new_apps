# -*- coding: utf-8 -*-
"""Servicios JSON de las funciones de campo de mobiliario del portal de obra
(paquete 1.22, etapa 2), con el mismo patrón que los del portal: token del
portal, errores en JSON y dato mal formado como 422."""
from odoo import http
from odoo.http import request

from odoo.addons.al_construction_portal.controllers.api import PREFIX, _body, portal_api


class ConstructionPortalFurnitureApi(http.Controller):

    def _service(self):
        return request.env['construction.portal.service']

    @http.route(PREFIX + '/furniture/module-reception', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    @portal_api
    def module_reception(self, **kw):
        return self._service().module_reception(_body())

    @http.route(PREFIX + '/furniture/replacement', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    @portal_api
    def replacement(self, **kw):
        return self._service().replacement(_body())

    @http.route(PREFIX + '/furniture/measure', type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False)
    @portal_api
    def measure(self, **kw):
        return self._service().measure(_body())

    @http.route(PREFIX + '/furniture/stage-progress', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    @portal_api
    def stage_progress(self, **kw):
        return self._service().stage_progress(_body())

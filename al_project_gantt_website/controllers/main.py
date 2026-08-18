# -*- coding: utf-8 -*-
"""Controladores de la página de Gantt del sitio web.

Todas las rutas exigen **usuario interno autenticado**: ``auth='user'`` cubre la
autenticación, y el chequeo explícito de ``user.share`` y del grupo cubre el
resto (un usuario de portal está autenticado, pero no debe entrar).

Aquí no hay lógica de datos: se delega en ``project.project.get_gantt_data()``.
"""
import logging

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

GROUP_GANTT_USER = 'al_project_gantt_base.group_gantt_user'


class GanttWebsiteController(http.Controller):

    def _ensure_internal_gantt_user(self):
        """Usuario interno con el grupo del Gantt, o 403.

        Es intencionalmente redundante con ``al.gantt.data._check_gantt_access``:
        la capa de datos protege el modelo aunque se la llame desde otro sitio,
        y esta protege la ruta antes de tocar el ORM.
        """
        user = request.env.user
        if user._is_public() or user.share:
            _logger.info("Gantt web: acceso denegado a un usuario compartido (%s)", user.login)
            raise Forbidden()
        if not user.has_group(GROUP_GANTT_USER):
            _logger.info("Gantt web: acceso denegado, sin grupo del Gantt (%s)", user.login)
            raise Forbidden()

    @http.route('/gantt', type='http', auth='user', website=True, sitemap=False)
    def gantt_page(self, **kwargs):
        """Página con el contenedor del diagrama. Los datos los pide el JS."""
        self._ensure_internal_gantt_user()
        return request.render('al_project_gantt_website.gantt_page', {})

    # En Odoo 19 `type='json'` es un alias obsoleto de `type='jsonrpc'`.
    @http.route('/gantt/data', type='jsonrpc', auth='user', website=True)
    def gantt_data(self, project_ids=None, options=None, **kwargs):
        """Único punto de datos de esta interfaz: delega en el módulo base."""
        self._ensure_internal_gantt_user()
        return request.env['project.project'].get_gantt_data(
            project_ids=project_ids, options=options or {},
        )

    @http.route('/gantt/apply', type='jsonrpc', auth='user', website=True)
    def gantt_apply(self, changeset=None, **kwargs):
        """Escritura desde la página. El permiso real por tarea lo comprueba
        el módulo base; aquí solo se filtra el acceso a la ruta."""
        self._ensure_internal_gantt_user()
        return request.env['project.project'].apply_gantt_changes(changeset=changeset or {})

    @http.route('/gantt/baseline', type='jsonrpc', auth='user', website=True)
    def gantt_baseline(self, project_ids=None, name=None, **kwargs):
        """Captura una línea base de los proyectos indicados."""
        self._ensure_internal_gantt_user()
        return request.env['al.gantt.data'].create_baseline(project_ids or [], name)

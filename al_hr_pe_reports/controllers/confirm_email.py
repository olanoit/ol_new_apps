# -*- coding: utf-8 -*-
"""Confirmación pública de recepción de la boleta de pago.

Port del controller v18 (``hr_voucher/controllers/confirm_email.py``) con
una mejora de seguridad: la ruta v18 era ``/payslip_line/<id>`` con el id
pelado (cualquiera podía confirmar boletas ajenas enumerando ids); ahora
la URL lleva un token HMAC-SHA256 derivado de ``database.secret``
(``ir.config_parameter``) que se valida con ``consteq`` antes de tocar el
registro. Las páginas de respuesta se generan inline (sin dependencia de
``website`` ni templates QWeb públicos).
"""
import logging

from markupsafe import Markup, escape

from odoo import fields, http
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)

_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            background-color: #f6f6f6;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }}
        .boleta-card {{
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 32px 40px;
            max-width: 480px;
            text-align: center;
        }}
        .boleta-card h2 {{ margin: 0 0 12px 0; color: #333; }}
        .boleta-card p {{ margin: 0; color: #777; }}
    </style>
</head>
<body>
    <div class="boleta-card">
        <h2>{title}</h2>
        <p>{message}</p>
    </div>
</body>
</html>"""


class BoletaConfirmController(http.Controller):

    @staticmethod
    def _page(title, message, status=200):
        html = _PAGE.format(title=escape(title), message=escape(message))
        return request.make_response(
            Markup(html), status=status,
            headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route('/boleta/confirmar/<int:payslip_id>/<string:token>',
                type='http', auth='public', methods=['GET'], csrf=False)
    def confirm_voucher(self, payslip_id, token, **kwargs):
        """Marca la boleta como recibida si el token HMAC es válido."""
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id).exists()
        if not payslip or not consteq(
                token, payslip._get_voucher_confirm_token()):
            _logger.info(
                'Confirmación de boleta rechazada: id=%s token inválido.',
                payslip_id)
            return self._page(
                'Enlace no válido',
                'El enlace de confirmación no es válido o ha caducado. '
                'Comuníquese con Gestión Humana.',
                status=404)
        if payslip.is_verified:
            return self._page(
                '¡Usted ya confirmó su boleta!',
                'En caso de alguna observación, comuníquese con Gestión '
                'Humana.')
        payslip.write({
            'is_verified': True,
            'date_confirmation': fields.Datetime.now(),
        })
        return self._page(
            '¡Confirmación registrada!',
            'Gracias por confirmar la recepción de su boleta de pago.')

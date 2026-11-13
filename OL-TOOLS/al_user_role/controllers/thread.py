# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.http import request

from odoo.addons.mail.controllers.thread import ThreadController


class AlThreadController(ThreadController):

    def _prepare_message_data(self, post_data, *, thread, from_create=True, **kwargs):
        """"Ocultar Enviar mensaje": en el chatter solo se registran notas.

        Lo que publica el chatter pasa por aquí (``/mail/message/post``); un
        mensaje (``mail.mt_comment``) llega a los seguidores, p. ej. al
        cliente, y una nota (``mail.mt_note``) es interna. Los mensajes de
        Conversaciones (``discuss.channel``) y los correos de los asistentes
        (p. ej. "Enviar por correo" de un pedido) no pasan por este bloqueo.
        """
        res = super()._prepare_message_data(post_data, thread=thread, from_create=from_create, **kwargs)
        if (
            from_create
            and thread._name != 'discuss.channel'
            and res.get('subtype_xmlid', 'mail.mt_note') != 'mail.mt_note'
            and request.env.user._is_internal()
        ):
            restrictions = request.env['al.user.role']._al_ui_restrictions()
            if restrictions and restrictions['hide_send_message']:
                raise AccessError(request.env._(
                    'Su rol no permite enviar mensajes desde el chatter. Puede registrar una nota.'))
        return res

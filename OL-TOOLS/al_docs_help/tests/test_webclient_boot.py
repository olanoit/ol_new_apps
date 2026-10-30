# -*- coding: utf-8 -*-
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestWebclientBoot(HttpCase):
    """El cliente web arranca sin errores de consola: los componentes de la
    barra superior (ayuda, aprobaciones…) se montan al entrar. Los tests de
    Python no renderizan el cliente, así que un import roto (p. ej. un plugin
    que Odoo 20 renombró) solo aparecía en el navegador."""

    def test_webclient_boot(self):
        self.browser_js('/odoo', "console.log('test successful')", ready="odoo.isReady", login='admin', timeout=120)

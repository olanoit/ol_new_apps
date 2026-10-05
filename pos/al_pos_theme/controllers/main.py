from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.addons.point_of_sale.controllers.main import PosController


class AlPosThemeController(PosController):

    @http.route()
    def pos_web(self, config_id=False, from_backend=False, subpath=None, **k):
        """Agrega al contexto del índice los valores de marca de la caja.

        La respuesta de `request.render` es perezosa: el qcontext se puede
        completar aquí antes de que se renderice `point_of_sale.index`.
        """
        response = super().pos_web(config_id=config_id, from_backend=from_backend, subpath=subpath, **k)
        qcontext = getattr(response, "qcontext", None)
        if qcontext and qcontext.get("pos_config_id"):
            config = request.env["pos.config"].sudo().browse(qcontext["pos_config_id"])
            dark = request.cookies.get("pos_color_scheme") == "dark"
            qcontext.update({
                "al_theme_title": config._al_theme_page_title(),
                "al_theme_brand": config._al_theme_brand(),
                "al_theme_favicon": config._al_theme_favicon_src(),
                # Markup: los valores ya vienen saneados (colores validados por
                # regex, nombre sin < > ni saltos) y deben ir sin escapar
                # dentro del <style>, o las comillas se volverían &quot;.
                "al_theme_css_vars": Markup(config._al_theme_css_vars(dark=dark)),
                "al_theme_dark": dark,
            })
        return response

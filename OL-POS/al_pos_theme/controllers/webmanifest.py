import json
import re
from urllib.parse import unquote

from odoo import http
from odoo.http import request
from odoo.tools import file_open
from odoo.tools.image import image_process
from odoo.addons.web.controllers import webmanifest

from ..models.pos_config import AL_THEME_DEFAULTS

# app_id propio: el botón "Instalar App" del PdV apunta a este módulo (ver
# static/src/js/navbar_patch.js), así el icono sale de
# al_pos_theme/static/src/img/icon.svg y no del de point_of_sale.
THEME_APP_ID = "al_pos_theme"
# El ícono del módulo (static/description) es el isotipo de ALTA; la app del
# TPV de cada cliente mantiene la caja registradora neutra y, en iOS, el ícono
# de Punto de venta.
THEME_APP_ICON = "/al_pos_theme/static/src/img/icon.svg"
THEME_APP_ICON_PNG = "point_of_sale/static/description/icon.png"


class WebManifest(webmanifest.WebManifest):

    def _al_theme_config_from_path(self, path):
        if match := re.search(r"pos/ui/(\d+)", unquote(path or "")):
            config = request.env["pos.config"].sudo().browse(int(match[1])).exists()
            return config
        return request.env["pos.config"]

    def _get_scoped_app_name(self, app_id):
        if app_id == THEME_APP_ID:
            config = self._al_theme_config_from_path(request.params.get("path"))
            if config:
                return config._al_theme_page_title()
        return super()._get_scoped_app_name(app_id)

    def _get_scoped_app_icons(self, app_id):
        if app_id == THEME_APP_ID:
            return [{"src": THEME_APP_ICON, "sizes": "any", "type": "image/svg+xml"}]
        return super()._get_scoped_app_icons(app_id)

    @http.route()
    def scoped_app_icon_png(self, app_id, add_padding=False):
        if app_id != THEME_APP_ID:
            return super().scoped_app_icon_png(app_id, add_padding=add_padding)
        with file_open(THEME_APP_ICON_PNG, "rb") as file:
            image = image_process(file.read(), size=(180, 180), expand=True, colorize=(255, 255, 255), padding=16)
        return request.make_response(image, headers=[("Content-Type", "image/png")])

    @http.route()
    def scoped_app(self, app_id, path="", app_name=""):
        response = super().scoped_app(app_id, path=path, app_name=app_name)
        if app_id == THEME_APP_ID and response.qcontext:
            # El icono iOS por defecto es el de Odoo: se usa el PNG del tema.
            response.qcontext["apple_touch_icon"] = f"/scoped_app_icon_png?app_id={THEME_APP_ID}"
        return response

    @http.route()
    def scoped_app_manifest(self, app_id, path, app_name=""):
        response = super().scoped_app_manifest(app_id, path, app_name=app_name)
        if app_id != THEME_APP_ID:
            return response
        # Reemplaza el púrpura Odoo (#714B67) por los colores de la caja.
        manifest = json.loads(response.data)
        config = self._al_theme_config_from_path(path)
        if config:
            manifest["theme_color"] = config._al_theme_color("al_theme_color_primary")
            manifest["background_color"] = config._al_theme_color("al_theme_color_background")
        else:
            manifest["theme_color"] = AL_THEME_DEFAULTS["al_theme_color_primary"]
            manifest["background_color"] = AL_THEME_DEFAULTS["al_theme_color_background"]
        return request.make_json_response(manifest, {"Content-Type": "application/manifest+json"})

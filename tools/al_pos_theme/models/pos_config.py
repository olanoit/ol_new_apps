import base64
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.mimetypes import guess_mimetype

# Valores por defecto del sistema de diseño (deben coincidir con
# static/src/scss/_variables.scss). Paleta neutra, sin marca de cliente:
# primario azul de acción, secundario pizarra (títulos), acento celeste.
AL_THEME_DEFAULTS = {
    "al_theme_color_primary": "#2563EB",
    "al_theme_color_secondary": "#1E293B",
    "al_theme_color_accent": "#0EA5E9",
    "al_theme_color_background": "#F8FAFC",
}
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Ningún campo del tema viaja en el payload del PdV: todo se entrega en la
# página índice (ver controllers/main.py), que el servidor siempre renderiza
# fresca, mientras que pos.config puede venir de IndexedDB (sesión abierta).
# Además así los binarios (logo/favicon) no inflan el payload.
AL_THEME_PAYLOAD_EXCLUDED = (
    "al_theme_brand_name", "al_theme_logo", "al_theme_favicon",
    *AL_THEME_DEFAULTS,
)
# Icono por defecto (pestaña del navegador y barra del teléfono): el del
# módulo. Sin logo de caja ni de compañía no hay logo por defecto: se muestra
# el nombre de la marca como texto (ver navbar.scss).
DEFAULT_FAVICON = "/al_pos_theme/static/description/icon.svg"
# Variante del icono para la barra en modo oscuro (baldosa clara sobre el
# fondo oscuro).
DEFAULT_ICON_INVERSE = "/al_pos_theme/static/src/img/icon_inverse.svg"


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in rgb)


def _mix(color, other, weight):
    """Mezcla `color` con `other` (peso 0..1 de `other`), como mix() de SCSS."""
    a, b = _hex_to_rgb(color), _hex_to_rgb(other)
    return _rgb_to_hex(tuple(x * (1 - weight) + y * weight for x, y in zip(a, b)))


def _luminance(color):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _hex_to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


DARK_BG = "#0F172A"  # $alpt-dark-bg en _variables.scss


def _readable_on(color, background, minimum=4.5):
    """Aclara `color` (mezclando con blanco) hasta contraste AA sobre
    `background`. Se usa en modo oscuro: un primario de marca pensado para
    fondo claro (p.ej. #0F766E) queda ilegible como texto sobre el fondo oscuro."""
    for _ in range(12):
        if _contrast(color, background) >= minimum:
            break
        color = _mix(color, "#FFFFFF", 0.12)
    return color


def _on_color(color):
    """Texto legible sobre `color`: blanco o pizarra.

    Blanco mientras alcance 4:1 (los azules de marca suelen usarse con texto
    blanco aunque el pizarra dé unas décimas más de contraste); si no, el de
    mayor contraste — protege un primario claro elegido por el usuario.
    """
    dark = "#0F172A"
    if _contrast(color, "#FFFFFF") >= 4.0:
        return "#FFFFFF"
    return "#FFFFFF" if _contrast(color, "#FFFFFF") >= _contrast(color, dark) else dark


class PosConfig(models.Model):
    _inherit = "pos.config"

    al_theme_brand_name = fields.Char(
        string="Nombre de la marca",
        help="Nombre que se muestra en la pestaña del navegador, en la app instalada y en "
             "los mensajes del sistema. Si está vacío, se usa el nombre de la compañía.",
    )
    al_theme_logo = fields.Image(
        string="Logo de la marca",
        max_width=512,
        max_height=512,
        help="Logo de la barra superior y de la pantalla de reposo. Si está vacío, se usa el "
             "logo de la compañía y, si tampoco hay, el nombre de la marca.",
    )
    al_theme_favicon = fields.Image(
        string="Icono del navegador",
        max_width=128,
        max_height=128,
        help="Icono de la pestaña del navegador. Si está vacío, se usa el icono del módulo.",
    )
    al_theme_color_primary = fields.Char(
        string="Color primario", default=AL_THEME_DEFAULTS["al_theme_color_primary"],
    )
    al_theme_color_secondary = fields.Char(
        string="Color secundario", default=AL_THEME_DEFAULTS["al_theme_color_secondary"],
    )
    al_theme_color_accent = fields.Char(
        string="Color de acento", default=AL_THEME_DEFAULTS["al_theme_color_accent"],
    )
    al_theme_color_background = fields.Char(
        string="Color de fondo", default=AL_THEME_DEFAULTS["al_theme_color_background"],
    )

    @api.constrains(*AL_THEME_DEFAULTS)
    def _check_al_theme_colors(self):
        # Además de validar la entrada, esto evita inyectar CSS arbitrario:
        # los colores se escriben tal cual dentro de un <style> en el índice.
        for config in self:
            for fname in AL_THEME_DEFAULTS:
                value = config[fname]
                if value and not HEX_COLOR_RE.match(value):
                    raise ValidationError(_(
                        "%(field)s debe ser un color hexadecimal como #2563EB (se recibió %(value)s).",
                        field=self._fields[fname].string, value=value,
                    ))

    # ------------------------------------------------------------------
    # Valores de marca para las páginas índice (PdV y pantalla de cliente)
    # ------------------------------------------------------------------
    def _al_theme_color(self, fname):
        self.ensure_one()
        value = self[fname]
        return value if value and HEX_COLOR_RE.match(value) else AL_THEME_DEFAULTS[fname]

    def _al_theme_brand(self):
        self.ensure_one()
        return self.al_theme_brand_name or self.company_id.name or "POS"

    def _al_theme_page_title(self):
        self.ensure_one()
        return f"{self._al_theme_brand()} · {self.name}"

    @staticmethod
    def _al_theme_data_uri(b64_value):
        if not b64_value:
            return ""
        raw = base64.b64decode(b64_value)
        return f"data:{guess_mimetype(raw)};base64,{b64_value.decode() if isinstance(b64_value, bytes) else b64_value}"

    def _al_theme_logo_src(self, inverse=False):
        """Logo como data URI (funciona sin conexión: la página índice queda
        en caché del service worker). Cadena: logo de la caja -> logo de la
        compañía (si no es el genérico) -> sin logo (cadena vacía: se muestra
        el nombre de la marca como texto).

        `inverse` se mantiene por compatibilidad de la firma: un logo subido
        se usa igual en ambos fondos."""
        self.ensure_one()
        config = self.sudo()
        if config.al_theme_logo:
            return self._al_theme_data_uri(config.al_theme_logo)
        company = config.company_id
        if company.logo_web and not company.uses_default_logo:
            return self._al_theme_data_uri(company.logo_web)
        return ""

    def _al_theme_favicon_src(self):
        self.ensure_one()
        favicon = self.sudo().al_theme_favicon
        return self._al_theme_data_uri(favicon) if favicon else DEFAULT_FAVICON

    def _al_theme_css_vars(self, dark=False, with_logo=True):
        """Declaraciones CSS de la marca de esta caja.

        Sólo se derivan valores de colores ya validados por regex, y el nombre
        de marca se serializa escapando comillas/backslash, así que el
        resultado es seguro dentro de un <style>.
        """
        self.ensure_one()
        primary = self._al_theme_color("al_theme_color_primary")
        secondary = self._al_theme_color("al_theme_color_secondary")
        accent = self._al_theme_color("al_theme_color_accent")
        background = self._al_theme_color("al_theme_color_background")
        if dark:
            # Modo oscuro: primario/acento aclarados hasta AA sobre el fondo
            # oscuro; hover = más claro (no más oscuro) y los "subtle" se
            # mezclan con el fondo oscuro, no con blanco.
            primary = _readable_on(primary, DARK_BG)
            accent = _readable_on(accent, DARK_BG)
            hover, active = _mix(primary, "#FFFFFF", 0.12), _mix(primary, "#FFFFFF", 0.22)
            primary_subtle = _mix(primary, DARK_BG, 0.80)
            accent_subtle = _mix(accent, DARK_BG, 0.80)
        else:
            hover, active = _mix(primary, "#000000", 0.15), _mix(primary, "#000000", 0.25)
            primary_subtle = _mix(primary, "#FFFFFF", 0.88)
            accent_subtle = _mix(accent, "#FFFFFF", 0.88)
        declarations = {
            "--alpt-primary": primary,
            "--alpt-primary-rgb": "%d, %d, %d" % _hex_to_rgb(primary),
            "--alpt-primary-hover": hover,
            "--alpt-primary-active": active,
            "--alpt-primary-subtle": primary_subtle,
            "--alpt-on-primary": _on_color(primary),
            "--alpt-secondary": secondary,
            "--alpt-secondary-rgb": "%d, %d, %d" % _hex_to_rgb(secondary),
            "--alpt-on-secondary": _on_color(secondary),
            "--alpt-accent": accent,
            "--alpt-accent-rgb": "%d, %d, %d" % _hex_to_rgb(accent),
            "--alpt-accent-subtle": accent_subtle,
            "--alpt-on-accent": _on_color(accent),
        }
        if not dark:
            # En modo oscuro el fondo lo define _tokens.scss (paleta oscura).
            declarations["--alpt-bg"] = background
        if with_logo:
            # Logo y nombre llevan comillas: sólo se emiten en el índice del
            # PdV, donde el controller los marca como Markup (sin escapar).
            logo = self._al_theme_logo_src(inverse=dark)
            # Teléfono: sólo el isotipo en la barra (favicon de la caja o el
            # del módulo), ver navbar.xml.
            icon = self._al_theme_favicon_src()
            if dark and icon == DEFAULT_FAVICON:
                icon = DEFAULT_ICON_INVERSE
            declarations["--alpt-logo-icon"] = f'url("{icon}")'
            # Pantalla de reposo: siempre sobre el degradado secundario → primario.
            logo_inverse = logo if dark else self._al_theme_logo_src(inverse=True)
            declarations["--alpt-logo-inverse"] = f'url("{logo_inverse}")' if logo_inverse else "none"
            # Variable propia (no `--navbar-logo` directo): el modo oscuro de
            # pos_enterprise redefine `--navbar-logo` sobre `.pos-logo` con el
            # logo de Odoo; branding.scss la reasigna desde ésta con más
            # especificidad.
            declarations["--alpt-logo"] = f'url("{logo}")' if logo else "none"
            # Sin logo se muestra el nombre de marca como texto (ver navbar.scss).
            declarations["--alpt-brand-text-display"] = "none" if logo else "block"
            brand = self._al_theme_brand().replace("\\", "\\\\").replace('"', '\\"')
            brand = re.sub(r"[<>\n\r]", "", brand)
            declarations["--alpt-brand-name"] = f'"{brand}"'
        return "".join(f"{key}: {value};" for key, value in declarations.items())

    # ------------------------------------------------------------------
    # Integración con la carga de datos del PdV y la pantalla de cliente
    # ------------------------------------------------------------------
    @api.model
    def _load_pos_data_read(self, records, config):
        # pos.config se lee con todos sus campos ([] = sin filtro).
        read_records = super()._load_pos_data_read(records, config)
        for record in read_records:
            for fname in AL_THEME_PAYLOAD_EXCLUDED:
                record.pop(fname, None)
        return read_records

    def _get_customer_display_data(self):
        data = super()._get_customer_display_data()
        data.update({
            "al_theme_title": self._al_theme_page_title(),
            "al_theme_favicon": self._al_theme_favicon_src(),
            "al_theme_css_vars": self._al_theme_css_vars(with_logo=False),
        })
        return data

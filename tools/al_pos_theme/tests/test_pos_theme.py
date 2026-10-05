import json

from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.al_pos_theme.models.pos_config import DARK_BG, AL_THEME_PAYLOAD_EXCLUDED, _contrast


@tagged("post_install", "-at_install")
class TestPosThemeConfig(TransactionCase):
    """Lógica de marca de pos.config: validación, CSS emitido y payload."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["pos.config"].create({"name": "Caja tema test"})
        cls.company = cls.config.company_id
        # Marca neutra: sin logo de compañía se muestra el nombre como texto.
        cls.company.logo = False

    def test_defaults(self):
        # Sin marca de cliente: nombre de la compañía y paleta neutra.
        self.assertFalse(self.config.al_theme_brand_name)
        self.assertEqual(self.config.al_theme_color_primary, "#2563EB")
        self.assertEqual(self.config._al_theme_page_title(), f"{self.company.name} · Caja tema test")

    def test_invalid_color_rejected(self):
        # Además de validar, impide inyectar CSS en el <style> del índice.
        for value in ("red", "#12345", "#0F766E; } body { display:none", "url(x)"):
            with self.assertRaises(ValidationError, msg=value):
                self.config.al_theme_color_primary = value

    def test_css_vars_light(self):
        css = self.config._al_theme_css_vars()
        self.assertIn("--alpt-primary: #2563EB;", css)
        self.assertIn("--alpt-bg: #F8FAFC;", css)
        # Azul de acción (5.2:1 con blanco): texto blanco en botones primarios.
        self.assertIn("--alpt-on-primary: #FFFFFF;", css)
        self.assertIn(f'--alpt-brand-name: "{self.company.name}";', css)
        # Sin logo propio ni de compañía: no hay logo por defecto de cliente,
        # se muestra el nombre de la marca como texto.
        self.assertIn("--alpt-logo: none;", css)
        self.assertIn("--alpt-logo-inverse: none;", css)
        self.assertIn("--alpt-brand-text-display: block;", css)
        # Teléfono: icono del módulo en la barra.
        self.assertIn('--alpt-logo-icon: url("/al_pos_theme/static/description/icon.svg");', css)
        self.assertNotIn("--navbar-logo", css, "el logo va en --alpt-logo (ver branding.scss)")

    def test_css_vars_dark_contrast(self):
        # Un primario oscuro elegido para fondo claro se aclara hasta AA en oscuro.
        self.config.al_theme_color_primary = "#1E293B"
        css = self.config._al_theme_css_vars(dark=True)
        primary = css.split("--alpt-primary: ")[1].split(";")[0]
        self.assertGreaterEqual(_contrast(primary, DARK_BG), 4.5)
        self.assertNotIn("--alpt-bg:", css, "en oscuro el fondo lo define _tokens.scss")
        # Oscuro: icono del módulo con baldosa oscura en el teléfono.
        self.assertIn("/al_pos_theme/static/src/img/icon_inverse.svg", css)

    def test_company_logo_is_used(self):
        # Sin logo de caja, el de la compañía (data URI: funciona sin conexión).
        self.company.logo = self.env.ref("base.main_company").logo or \
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        css = self.config._al_theme_css_vars()
        self.assertIn('--alpt-logo: url("data:image/', css)
        self.assertIn("--alpt-brand-text-display: none;", css)

    def test_brand_name_is_escaped(self):
        self.config.al_theme_brand_name = 'Farma "X" </style><script>'
        css = self.config._al_theme_css_vars()
        self.assertNotIn("<", css)
        self.assertNotIn(">", css)
        self.assertIn('--alpt-brand-name: "Farma \\"X\\" /stylescript";', css)

    def test_customer_display_vars_have_no_quotes(self):
        # Se escapan en QWeb (no son Markup): no deben llevar comillas.
        data = self.config._get_customer_display_data()
        self.assertEqual(data["al_theme_title"], f"{self.company.name} · Caja tema test")
        self.assertNotIn('"', data["al_theme_css_vars"])

    def test_theme_fields_not_in_pos_payload(self):
        records = self.env["pos.config"]._load_pos_data_read(self.config, self.config)
        for fname in AL_THEME_PAYLOAD_EXCLUDED:
            self.assertNotIn(fname, records[0])


@tagged("post_install", "-at_install")
class TestPosThemeWebManifest(HttpCase):
    """La PWA "Instalar app" no debe mostrar el nombre ni los colores del sistema base."""

    def test_scoped_app_manifest(self):
        config = self.env["pos.config"].create({"name": "Caja PWA"})
        # Sesión anónima: sin ella el servidor de test no sabe qué base usar
        # (hay varias en el clúster) y responde 404 "No database".
        self.authenticate(None, None)
        response = self.url_open(
            f"/web/manifest.scoped_app_manifest?app_id=al_pos_theme&path=%2Fpos%2Fui%2F{config.id}"
        )
        self.assertEqual(response.status_code, 200)
        manifest = json.loads(response.content)
        self.assertEqual(manifest["name"], f"{config.company_id.name} · Caja PWA")
        self.assertEqual(manifest["theme_color"], "#2563EB")
        self.assertNotIn("714B67", json.dumps(manifest).upper())
        self.assertTrue(manifest["icons"][0]["src"].startswith("/al_pos_theme/"))

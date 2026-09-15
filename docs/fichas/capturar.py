#!/usr/bin/env python3
"""Ayudante de capturas para las fichas de los módulos (Playwright + Chrome).

Uso típico, desde un script propio de cada módulo::

    import sys; sys.path.insert(0, 'docs/fichas')
    from capturar import Captura

    with Captura('al_l10n_pe_retention') as c:
        c.abrir('/odoo/action-al_l10n_pe_retention.action_retention_payments')
        c.foto('01-efectuadas')                      # vista completa
        c.abrir_registro('account.payment', 20)
        c.foto('02-pago', selector='.o_form_sheet_bg')

Las imágenes quedan en ``<módulo>/static/description/screenshots/<nombre>.png``
y en el YAML se referencian como ``screenshots/<nombre>.png``.

Variables de entorno: ``FICHAS_URL`` (por defecto http://127.0.0.1:19730),
``FICHAS_DB`` (ol_pe_v19), ``FICHAS_USER`` / ``FICHAS_PASSWORD`` (admin/admin).
"""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = os.environ.get('FICHAS_URL', 'http://127.0.0.1:19730')
DB = os.environ.get('FICHAS_DB', 'ol_pe_v19')
USER = os.environ.get('FICHAS_USER', 'admin')
PASSWORD = os.environ.get('FICHAS_PASSWORD', 'admin')
CHROME = os.environ.get('FICHAS_CHROME', '/usr/bin/google-chrome')

# 1440×900 a escala 1: nítido en la ficha (máx. 1120 px de ancho) sin pesar
# demasiado en el repositorio.
VIEWPORT = {'width': 1440, 'height': 900}


class Captura:
    def __init__(self, module, viewport=None, lang=None):
        self.module = module
        self.viewport = viewport or VIEWPORT
        self.out = ROOT / module / 'static' / 'description' / 'screenshots'
        self.out.mkdir(parents=True, exist_ok=True)

    # -- sesión ---------------------------------------------------------
    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            executable_path=CHROME, args=['--no-sandbox'])
        # Hora de Lima y español: sin esto las horas salen desfasadas y los
        # selectores de fecha, en formato inglés.
        self.page = self.browser.new_page(
            viewport=self.viewport, timezone_id='America/Lima', locale='es-PE')
        self.page.set_default_timeout(20000)
        self.login()
        return self

    def __exit__(self, *exc):
        self.browser.close()
        self._pw.stop()

    def login(self):
        page = self.page
        page.goto('%s/web/login?db=%s' % (URL, DB))
        form = page.locator('form.oe_login_form')
        form.locator('input[name=login]').fill(USER)
        form.locator('input[name=password]').fill(PASSWORD)
        form.locator('button[type=submit]').click()
        page.wait_for_url('**/odoo**')
        self.esperar()

    # -- navegación -----------------------------------------------------
    def esperar(self, ms=900):
        """Espera a que el cliente web termine de cargar y a que se asiente."""
        try:
            self.page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:  # noqa: BLE001 - el long-polling no siempre deja «idle»
            pass
        self.page.wait_for_timeout(ms)

    def abrir(self, path, ms=1200):
        """``path`` relativo: ``/odoo/action-<xmlid>``, ``/odoo/<modelo>/<id>``…"""
        self.page.goto(URL + path)
        self.esperar(ms)

    def abrir_accion(self, xmlid, ms=1200):
        self.abrir('/odoo/action-%s' % xmlid, ms)

    def abrir_registro(self, model, res_id, ms=1200):
        self.abrir('/odoo/%s/%s' % (model, res_id), ms)

    def clic(self, selector, ms=900):
        self.page.locator(selector).first.click()
        self.esperar(ms)

    def texto(self, text, ms=900):
        """Clic en el primer elemento visible con ese texto exacto."""
        self.page.get_by_text(text, exact=True).first.click()
        self.esperar(ms)

    def js(self, script):
        return self.page.evaluate(script)

    # -- fotos ----------------------------------------------------------
    def foto(self, name, selector=None, full_page=False, padding=0, recortar=True,
             clip=None):
        """Guarda la captura. Con ``selector`` recorta a ese elemento
        (p. ej. ``.modal-content``, ``.o_form_sheet_bg``, ``.o_list_renderer``);
        con ``clip`` (``{'x', 'y', 'width', 'height'}``), a esa zona de la
        pantalla —útil para un bloque de Ajustes.

        Antes aparta el ratón (un tooltip colado estropea la imagen) y, con
        ``recortar``, quita el fondo liso sobrante por abajo: una lista de dos
        filas no necesita 700 px vacíos."""
        self.page.mouse.move(self.viewport['width'] - 2, self.viewport['height'] - 2)
        self.page.wait_for_timeout(250)
        path = self.out / ('%s.png' % name)
        if clip:
            self.page.screenshot(path=str(path), clip=clip)
        elif selector:
            element = self.page.locator(selector).first
            if padding:
                box = element.bounding_box()
                clip = {
                    'x': max(box['x'] - padding, 0),
                    'y': max(box['y'] - padding, 0),
                    'width': box['width'] + 2 * padding,
                    'height': box['height'] + 2 * padding,
                }
                self.page.screenshot(path=str(path), clip=clip)
            else:
                element.screenshot(path=str(path))
        else:
            self.page.screenshot(path=str(path), full_page=full_page)
        if recortar:
            _recortar_fondo(path)
        print('captura', path.relative_to(ROOT))
        return 'screenshots/%s.png' % name


def _recortar_fondo(path, margen=28, minimo=260):
    """Quita por abajo las filas del mismo color que la última (fondo liso)."""
    from PIL import Image

    image = Image.open(path).convert('RGB')
    width, height = image.size
    pixels = image.load()
    background = pixels[width // 2, height - 1]

    def fila_lisa(y):
        return all(
            max(abs(a - b) for a, b in zip(pixels[x, y], background)) < 6
            for x in range(0, width, 4))

    bottom = height - 1
    while bottom > minimo and fila_lisa(bottom):
        bottom -= 1
    new_height = min(height, bottom + margen)
    if new_height < height - margen:
        image.crop((0, 0, width, new_height)).save(path, optimize=True)
    else:
        image.save(path, optimize=True)

"""Pago real de punta a punta desde Odoo en la tienda de prueba de Izipay
(Playwright + Chrome).

Antes: servidor de prueba en marcha y enlace de pago de
``preparar_sandbox.py``. Uso::

    python -I docs/izipay/validar_sandbox.py '<enlace>' <tarjeta> <prefijo_capturas>

Tarjetas de prueba oficiales (vencimiento futuro cualquiera, CVV 123):
aprobada Visa 4970100000000055; rechazada por fondos insuficientes
4970100000000071. Con ``REINTENTO=4970100000000055`` en el entorno, tras el
rechazo se reintenta con esa tarjeta en el mismo formulario.
"""
import os
import sys

from playwright.sync_api import sync_playwright

URL, CARD, TAG = sys.argv[1:4]
RETRY = os.environ.get('REINTENTO')


def fill_card(page, card):
    def field(cls):
        return page.frame_locator(f'.kr-popin-wrapper .kr-{cls} iframe, .kr-{cls} iframe').first.locator('input').first
    field('pan').fill(card)
    field('expiry').fill('12/30')
    field('security-code').fill('123')
    holder = page.locator('input.kr-card-holder-name, .kr-card-holder-name input')
    if holder.count() and holder.first.is_visible():
        holder.first.fill('ROSA QUISPE')


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1280, 'height': 900}, locale='es-PE', timezone_id='America/Lima')
    page.on('dialog', lambda dialog: dialog.dismiss())
    page.goto(URL, wait_until='networkidle', timeout=90000)
    izipay = page.locator('input[name=o_payment_radio][data-provider-code=izipay]')
    if izipay.count():
        izipay.first.check()
    page.wait_for_timeout(800)
    page.screenshot(path=f'{TAG}_1_pago.png')
    page.locator('button[name=o_payment_submit_button]').click()
    page.locator('.kr-pan iframe').first.wait_for(state='visible', timeout=60000)
    page.wait_for_timeout(1500)
    fill_card(page, CARD)
    page.wait_for_timeout(800)
    page.screenshot(path=f'{TAG}_2_formulario.png')
    page.locator('.kr-payment-button').first.click()
    if RETRY:
        page.locator('.kr-form-error').first.wait_for(state='visible', timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=f'{TAG}_3_rechazo.png')
        print('Rechazo:', ' '.join(page.locator('.kr-form-error').first.inner_text().split()))
        fill_card(page, RETRY)
        page.locator('.kr-payment-button').first.click()
    try:
        page.wait_for_url('**/payment/status**', timeout=90000)
        page.wait_for_load_state('networkidle')
    except Exception:
        pass
    page.wait_for_timeout(4000)
    page.screenshot(path=f'{TAG}_4_resultado.png', full_page=True)
    print('URL final:', page.url[:150])
    main = page.locator('main')
    print('Texto:', ' '.join(main.inner_text().split())[:400] if main.count() else '')
    browser.close()

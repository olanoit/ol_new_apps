"""Pago real de punta a punta contra el sandbox de Niubiz (Playwright + Chrome).

Requiere un servidor de prueba en 127.0.0.1:19730 con el proveedor Niubiz en modo
de prueba (credenciales públicas del sandbox, en const.py) y un enlace de
/payment/pay firmado. Uso::

    python docs/niubiz/validar_sandbox_e2e.py <referencia> <tarjeta> <MMAA> <cvv> <prefijo> <url_pago>

Tarjetas de prueba del sandbox: aprobada Visa 4551708161768059 (03/28, 111);
rechazada 4041650444437904 (código 116, fondos insuficientes).
"""
import sys
from playwright.sync_api import sync_playwright
ref, card, exp, cvv, tag, URL = sys.argv[1:7]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 1280, 'height': 900}, locale='es-PE')
    pg.on('dialog', lambda d: d.dismiss())
    pg.goto(URL, wait_until='networkidle', timeout=90000)
    pg.locator('input[name=o_payment_radio]').first.check(); pg.wait_for_timeout(500)
    pg.locator('button[name=o_payment_submit_button]').click()
    pg.wait_for_url('**/payment/niubiz/landing**', timeout=60000); pg.wait_for_load_state('networkidle')
    pg.locator('#o_niubiz_pay_btn').click()
    fr = None
    for _ in range(40):
        fr = next((f for f in pg.frames if 'visanet.html' in f.url), None)
        if fr and fr.locator('text=Tarjeta de crédito y débito').count(): break
        pg.wait_for_timeout(500)
    pg.screenshot(path=f'{tag}_1_modal.png')
    fr.locator('text=Tarjeta de crédito y débito').click()
    fr.locator('#payment-continue').click()
    fr.locator('#number').wait_for(timeout=20000)
    fr.locator('#number').type(card, delay=40)
    fr.locator('#expiry').type(exp, delay=60)
    fr.locator('#cvc').type(cvv, delay=60)
    for fid, val in (('name', 'Rosa'), ('lastname', 'Quispe'), ('email', 'demo.niubiz@example.com')):
        if not fr.locator(f'#{fid}').input_value():
            fr.locator(f'#{fid}').fill(val)
    pg.wait_for_timeout(800)
    pg.screenshot(path=f'{tag}_2_tarjeta.png')
    fr.locator('button[type=submit]:visible').click()
    try:
        pg.wait_for_url('**/payment/status**', timeout=90000)
    except Exception:
        pass
    pg.wait_for_timeout(5000)
    pg.screenshot(path=f'{tag}_3_resultado.png', full_page=True)
    print('URL final:', pg.url[:150])
    print('Texto:', ' '.join(pg.inner_text('main').split())[:400] if pg.locator('main').count() else '')
    b.close()

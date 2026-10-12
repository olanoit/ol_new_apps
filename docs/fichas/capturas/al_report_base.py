"""Captura del PDF de la ficha de al_report_base: account.move B001-00000002 (factura de la obra DEMO PLAN).

Uso: python3 docs/fichas/capturas/al_report_base.py [id]  (por defecto 26958)
"""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests  # noqa: E402
from capturar import DB, PASSWORD, ROOT, URL, USER, module_dir  # noqa: E402

M = 'al_report_base'
RES_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 26958

session = requests.Session()
session.post(f'{URL}/web/session/authenticate', json={
    'jsonrpc': '2.0', 'params': {'db': DB, 'login': USER, 'password': PASSWORD}})
pdf = session.get(f'{URL}/report/pdf/al_l10n_pe_invoice.report_cpe_invoice_a4_main/{RES_ID}').content
out = module_dir(M) / 'static' / 'description' / 'screenshots'
(out / 'tmp.pdf').write_bytes(pdf)
# 110 ppp: una hoja A4 de 910 px de ancho, como el resto de las fichas
subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', '-f', '1', str(out / 'tmp.pdf'),
                str(out / '01-factura-a4')], check=True)
(out / 'tmp.pdf').unlink()
print('captura', (out / '01-factura-a4.png').relative_to(ROOT))
